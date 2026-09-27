"""SQLite and SQL Server connections with a common result interface."""
from pathlib import Path

import sqlite3
import re
from field_definitions import FIELDS
from schema_builder import statements, column


class Result:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class Database:
    def __init__(self, config):
        self.backend = config.get('DATABASE_BACKEND', 'sqlserver')
        if self.backend == 'sqlite':
            path = Path(config['SQLITE_DATABASE'])
            path.parent.mkdir(parents=True, exist_ok=True)
            self.connection = sqlite3.connect(str(path), timeout=15)
            self.connection.execute('PRAGMA foreign_keys = ON')
            return
        if self.backend != 'sqlserver':
            raise ValueError('DATABASE_BACKEND must be sqlite or sqlserver')
        import pyodbc
        pyodbc.pooling = False
        self.connection = pyodbc.connect(
            config['SQLSERVER_CONNECTION_STRING'],
            timeout=int(config['SQLSERVER_LOGIN_TIMEOUT']),
            autocommit=False,
        )
        self.connection.timeout = int(config['SQLSERVER_COMMAND_TIMEOUT'])

    def execute(self, sql, params=()):
        cursor = self.connection.cursor()
        try:
            if self.backend == 'sqlserver':
                sql = re.sub(r'\b(FROM|INTO|UPDATE) (projects|raid_items|changelog_entries)\b',
                             r'\1 dbo.\2', sql)
            cursor.execute(sql, params)
            rows = []
            if cursor.description:
                columns = [column[0] for column in cursor.description]
                rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
            return Result(rows)
        finally:
            # Fully consume and close results so MARS can remain disabled.
            cursor.close()

    def create_project(self, values):
        return self._insert('projects', tuple(FIELDS['projects']), tuple(values[name] for name in FIELDS['projects']))

    def create_child(self, table, values):
        columns = ('project_id',) + tuple(FIELDS[table])
        return self._insert(table, columns, tuple(values[column] for column in columns))

    def _insert(self, table, columns, parameters):
        """Insert using internal, allowlisted identifiers and return the generated ID."""
        names = ','.join('[' + name + ']' for name in columns)
        placeholders = ','.join('?' for _ in columns)
        if self.backend == 'sqlserver':
            return self.execute(f'INSERT INTO {table}({names}) OUTPUT INSERTED.id VALUES ({placeholders})', parameters).fetchone()['id']
        cursor = self.connection.execute(f'INSERT INTO {table}({names}) VALUES ({placeholders})', parameters)
        try:
            return cursor.lastrowid
        finally:
            cursor.close()

    def initialize(self):
        cursor = self.connection.cursor()
        try:
            for statement in statements(self.backend):
                cursor.execute(statement)
                if self.backend == 'sqlserver':
                    while cursor.nextset():
                        pass
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise
        finally:
            cursor.close()

    def migrate(self, apply=False):
        """Plan/apply missing columns only; never drop columns or alter existing types."""
        plan = []
        for table, fields in FIELDS.items():
            if self.backend == 'sqlite':
                metadata = self.execute(f'PRAGMA table_info({table})').fetchall()
                existing = {row['name'] for row in metadata}
                blocked = [row['name'] for row in metadata if row['notnull'] and row['dflt_value'] is None]
            else:
                metadata = self.execute('SELECT name, is_nullable, default_object_id FROM sys.columns WHERE object_id=OBJECT_ID(?)', ('dbo.' + table,)).fetchall()
                existing = {row['name'] for row in metadata}
                blocked = [row['name'] for row in metadata if not row['is_nullable'] and not row['default_object_id']]
            if not existing:
                raise ValueError('Run init-db before migrate-db.')
            retired_required = set(blocked) - set(fields) - {'id', 'project_id', 'created_at'}
            if retired_required:
                raise ValueError(f'{table}: retired legacy columns {sorted(retired_required)} require a reviewed migration to allow NULL before inserts can omit them. No data was changed.')
            for name, definition in fields.items():
                if name not in existing:
                    target = ('dbo.' if self.backend == 'sqlserver' else '') + table
                    statement = f'ALTER TABLE {target} ADD ' + column(name, definition, self.backend, adding=True)
                    if self.backend == 'sqlserver' and definition['default'] is not None:
                        statement += ' WITH VALUES'
                    plan.append(statement)
        if apply:
            try:
                for statement in plan:
                    self.execute(statement)
                self.commit()
            except Exception:
                self.rollback()
                raise
        return plan

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

    def close(self):
        self.connection.close()


def db():
    """Return the database connection for the current Flask context."""
    from flask import current_app, g

    if 'db' not in g:
        g.db = Database(current_app.config)
    return g.db


def close_db(error=None):
    """Close the connection and discard uncommitted work."""
    from flask import g

    connection = g.pop('db', None)
    if connection is not None:
        connection.close()
