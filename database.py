"""SQLite and SQL Server connections with a common result interface."""
from pathlib import Path

import sqlite3
import re


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
        return self._insert('projects', ('name', 'description'), values)

    def create_child(self, table, values):
        columns = {
            'raid_items': ('project_id', 'kind', 'title', 'description', 'owner', 'status', 'priority'),
            'changelog_entries': ('project_id', 'title', 'body'),
        }[table]
        return self._insert(table, columns, tuple(values[column] for column in columns))

    def _insert(self, table, columns, parameters):
        """Insert using internal, allowlisted identifiers and return the generated ID."""
        names = ','.join(columns)
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
            if self.backend == 'sqlite':
                cursor.executescript(Path(__file__).with_name('schema_sqlite.sql').read_text())
            else:
                cursor.execute(Path(__file__).with_name('schema.sql').read_text())
                while cursor.nextset():
                    pass
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise
        finally:
            cursor.close()

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
