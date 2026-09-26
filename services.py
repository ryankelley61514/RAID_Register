"""Shared validation, lookups, CRUD and transaction boundaries for web and API routes."""
from contextlib import contextmanager
from constants import RAID_TYPES, STATUSES, PRIORITIES
from database import db


class ValidationError(ValueError):
    pass


class RecordNotFound(LookupError):
    pass


# Field definitions: maximum length, required/nonblank, default, allowed values.
PROJECT_FIELDS = {'name': (200, True, None, None), 'description': (10000, False, '', None)}
RAID_FIELDS = {
    'kind': (20, True, None, RAID_TYPES), 'title': (200, True, None, None),
    'description': (10000, False, '', None), 'owner': (200, False, '', None),
    'status': (20, True, 'Open', STATUSES), 'priority': (10, True, 'Medium', PRIORITIES),
}
CHANGE_FIELDS = {'title': (200, True, None, None), 'body': (10000, False, '', None)}


def validate(data, definitions, partial=False):
    if not isinstance(data, dict) or not data:
        raise ValidationError('Provide a nonempty object of field values.')
    if set(data) - set(definitions):
        raise ValidationError('Unknown or read-only fields: ' + ', '.join(sorted(set(data) - set(definitions))))
    values = {}
    for name, (limit, required, default, choices) in definitions.items():
        if partial and name not in data:
            continue
        value = data.get(name, default)
        if not isinstance(value, str):
            raise ValidationError(f'{name} must be a string.')
        value = value.strip()
        if len(value) > limit or (required and not value):
            raise ValidationError(f'{name} must be nonblank when required and at most {limit} characters.')
        if choices and value not in choices:
            raise ValidationError(f'Invalid {name}. Allowed values: ' + ', '.join(choices))
        values[name] = value
    return values


CHILDREN = {'raid': ('raid_items', RAID_FIELDS), 'changelog': ('changelog_entries', CHANGE_FIELDS)}


def child_definition(kind):
    if kind not in CHILDREN:
        raise RecordNotFound('Record type not found.')
    return CHILDREN[kind]


@contextmanager
def transaction():
    connection = db()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def get_project(project_id):
    record = db().execute('SELECT * FROM projects WHERE id=?', (project_id,)).fetchone()
    if record is None:
        raise RecordNotFound('Project not found.')
    return record


def list_projects(with_counts=False):
    if with_counts:
        return db().execute('SELECT p.*, (SELECT COUNT(*) FROM raid_items r WHERE r.project_id=p.id) AS raid_count, (SELECT COUNT(*) FROM changelog_entries c WHERE c.project_id=p.id) AS change_count FROM projects p ORDER BY p.id DESC').fetchall()
    return db().execute('SELECT * FROM projects ORDER BY id DESC').fetchall()


def list_children(project_id, kind):
    get_project(project_id)
    table, _ = child_definition(kind)
    return db().execute(f'SELECT * FROM {table} WHERE project_id=? ORDER BY id DESC', (project_id,)).fetchall()


def get_child(project_id, kind, record_id):
    get_project(project_id)
    table, _ = child_definition(kind)
    record = db().execute(f'SELECT * FROM {table} WHERE id=? AND project_id=?', (record_id, project_id)).fetchone()
    if record is None:
        raise RecordNotFound('Record not found in this project.')
    return record


def create_project(data):
    values = validate(data, PROJECT_FIELDS)
    with transaction() as connection:
        record_id = connection.create_project((values['name'], values['description']))
        record = get_project(record_id)
    return record


def update_project(project_id, data, partial=True):
    with transaction() as connection:
        get_project(project_id)
        values = validate(data, PROJECT_FIELDS, partial)
        assignments = ', '.join(name + '=?' for name in values)
        connection.execute(f'UPDATE projects SET {assignments} WHERE id=?', tuple(values.values()) + (project_id,))
        record = get_project(project_id)
    return record


def delete_project(project_id):
    with transaction() as connection:
        get_project(project_id)
        connection.execute('DELETE FROM projects WHERE id=?', (project_id,))


def create_child(project_id, kind, data):
    with transaction() as connection:
        get_project(project_id)
        table, fields = child_definition(kind)
        values = validate(data, fields)
        values['project_id'] = project_id
        record_id = connection.create_child(table, values)
        record = get_child(project_id, kind, record_id)
    return record


def update_child(project_id, kind, record_id, data, partial=True):
    with transaction() as connection:
        get_child(project_id, kind, record_id)
        table, fields = child_definition(kind)
        values = validate(data, fields, partial)
        assignments = ', '.join(name + '=?' for name in values)
        connection.execute(f'UPDATE {table} SET {assignments} WHERE id=? AND project_id=?', tuple(values.values()) + (record_id, project_id))
        record = get_child(project_id, kind, record_id)
    return record


def delete_child(project_id, kind, record_id):
    with transaction() as connection:
        get_child(project_id, kind, record_id)
        table, _ = child_definition(kind)
        connection.execute(f'DELETE FROM {table} WHERE id=? AND project_id=?', (record_id, project_id))
