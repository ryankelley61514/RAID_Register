"""Shared validation, lookups, CRUD and transaction boundaries for web and API routes."""
from contextlib import contextmanager
from field_definitions import FIELDS, active_record
from database import db


class ValidationError(ValueError):
    pass


class RecordNotFound(LookupError):
    pass


def validate(data, definitions, partial=False):
    if not isinstance(data, dict) or not data:
        raise ValidationError('Provide a nonempty object of field values.')
    if set(data) - set(definitions):
        raise ValidationError('Unknown or read-only fields: ' + ', '.join(sorted(set(data) - set(definitions))))
    values = {}
    for name, definition in definitions.items():
        limit, required, default, choices = (definition[key] for key in ('max_length', 'required', 'default', 'choices'))
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


CHILDREN = {'raid': 'raid_items', 'changelog': 'changelog_entries'}


def child_definition(kind):
    if kind not in CHILDREN:
        raise RecordNotFound('Record type not found.')
    table = CHILDREN[kind]
    return table, FIELDS[table]


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
    return active_record('projects', record)


def project_details(project):
    """Expand an already-loaded project without querying the parent again."""
    return dict(project, raid_items=_list_children(project['id'], 'raid'),
                changelog_entries=_list_children(project['id'], 'changelog'))


def get_project_details(project_id):
    return project_details(get_project(project_id))


def list_projects(with_counts=False):
    if with_counts:
        return [active_record('projects', row) for row in db().execute('SELECT p.*, (SELECT COUNT(*) FROM raid_items r WHERE r.project_id=p.id) AS raid_count, (SELECT COUNT(*) FROM changelog_entries c WHERE c.project_id=p.id) AS change_count FROM projects p ORDER BY p.id DESC').fetchall()]
    return [active_record('projects', row) for row in db().execute('SELECT * FROM projects ORDER BY id DESC').fetchall()]


def list_children(project_id, kind):
    get_project(project_id)
    return _list_children(project_id, kind)


def _list_children(project_id, kind):
    table, _ = child_definition(kind)
    return [active_record(table, row) for row in db().execute(f'SELECT * FROM {table} WHERE project_id=? ORDER BY id DESC', (project_id,)).fetchall()]


def get_child(project_id, kind, record_id):
    get_project(project_id)
    return _get_child(project_id, kind, record_id)


def _get_child(project_id, kind, record_id):
    table, _ = child_definition(kind)
    record = db().execute(f'SELECT * FROM {table} WHERE id=? AND project_id=?', (record_id, project_id)).fetchone()
    if record is None:
        raise RecordNotFound('Record not found in this project.')
    return active_record(table, record)


def create_project(data):
    values = validate(data, FIELDS['projects'])
    with transaction() as connection:
        record_id = connection.create_project(values)
        record = get_project(record_id)
    return record


def update_project(project_id, data, partial=True):
    with transaction() as connection:
        get_project(project_id)
        values = validate(data, FIELDS['projects'], partial)
        assignments = ', '.join('[' + name + ']=?' for name in values)
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
        record = _get_child(project_id, kind, record_id)
    return record


def update_child(project_id, kind, record_id, data, partial=True):
    with transaction() as connection:
        get_child(project_id, kind, record_id)
        table, fields = child_definition(kind)
        values = validate(data, fields, partial)
        assignments = ', '.join('[' + name + ']=?' for name in values)
        connection.execute(f'UPDATE {table} SET {assignments} WHERE id=? AND project_id=?', tuple(values.values()) + (record_id, project_id))
        record = _get_child(project_id, kind, record_id)
    return record


def delete_child(project_id, kind, record_id):
    with transaction() as connection:
        get_child(project_id, kind, record_id)
        table, _ = child_definition(kind)
        connection.execute(f'DELETE FROM {table} WHERE id=? AND project_id=?', (record_id, project_id))
