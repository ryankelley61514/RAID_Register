"""Generate new schemas and additive migrations from field definitions."""
import re
from field_definitions import FIELDS


def identifier(name):
    if not re.fullmatch(r'[a-z][a-z0-9_]*', name):
        raise ValueError(f'Invalid field identifier: {name}')
    if name in ('id', 'project_id', 'created_at'):
        raise ValueError(f'Reserved field identifier: {name}')
    return '[' + name + ']'


def literal(value, backend):
    return ('N' if backend == 'sqlserver' else '') + "'" + value.replace("'", "''") + "'"


def column(name, definition, backend, adding=False):
    quoted = identifier(name)
    if definition['type'] != 'string':
        raise ValueError('Only string fields are supported.')
    length = definition['max_length']
    if not isinstance(length, int) or not 1 <= length <= 1000000:
        raise ValueError('Invalid field length.')
    sql_type = 'TEXT' if backend == 'sqlite' else f'NVARCHAR({length if length <= 4000 else "MAX"})'
    default = definition['default']
    # Retired columns remain nullable so inserts can omit them later.
    result = f'{quoted} {sql_type} NULL'
    if adding and definition['required'] and default is None:
        raise ValueError(f'{name}: supply a valid default to backfill a new required field.')
    if default is not None:
        if not isinstance(default, str) or len(default) > length or (definition['required'] and not default.strip()):
            raise ValueError(f'{name}: invalid default.')
        if definition['choices'] and default not in definition['choices']:
            raise ValueError(f'{name}: default is not an allowed choice.')
        result += ' DEFAULT ' + literal(default, backend)
    if definition['choices']:
        result += f' CHECK ({quoted} IN (' + ','.join(literal(v, backend) for v in definition['choices']) + '))'
    return result


def statements(backend):
    sqlserver = backend == 'sqlserver'
    for table, fields in FIELDS.items():
        target = ('dbo.' if sqlserver else '') + table
        parts = ['id INT IDENTITY(1,1) PRIMARY KEY' if sqlserver else 'id INTEGER PRIMARY KEY AUTOINCREMENT']
        if table != 'projects':
            parts.append('project_id INT NOT NULL REFERENCES ' + ('dbo.' if sqlserver else '') + 'projects(id) ON DELETE CASCADE')
        parts.extend(column(name, definition, backend) for name, definition in fields.items())
        parts.append('created_at DATETIME2(0) NOT NULL DEFAULT SYSUTCDATETIME()' if sqlserver else 'created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP')
        create = f'CREATE TABLE {target} (' + ', '.join(parts) + ')'
        yield f"IF OBJECT_ID(N'{target}', N'U') IS NULL BEGIN {create}; END" if sqlserver else create.replace('CREATE TABLE', 'CREATE TABLE IF NOT EXISTS', 1)
    for table, index in [('raid_items', 'raid_project_idx'), ('changelog_entries', 'changelog_project_idx')]:
        if sqlserver:
            yield f"IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='{index}' AND object_id=OBJECT_ID(N'dbo.{table}')) CREATE INDEX {index} ON dbo.{table}(project_id)"
        else:
            yield f'CREATE INDEX IF NOT EXISTS {index} ON {table}(project_id)'
