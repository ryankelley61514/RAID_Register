"""Edit editable string/select fields here. Apply new columns with migrate-db."""


def field(label, *, max_length=200, required=False, default='', form='text',
          choices=None, searchable=True, sortable=False):
    return dict(label=label, type='string', max_length=max_length, required=required,
                default=default, form=form, choices=choices, searchable=searchable,
                sortable=sortable)


FIELDS = {
    'projects': {
        'name': field('Project name', required=True, default=None, sortable=True),
        'owner': field('Owner', sortable=True),
        'description': field('Description', max_length=10000, form='textarea'),
    },
    'raid_items': {
        'title': field('Title', required=True, default=None, sortable=True),
        'kind': field('Type', required=True, default=None, form='select',
                      choices=('Risk', 'Assumption', 'Issue', 'Dependency'), sortable=True),
        'status': field('Status', required=True, default='Open', form='select',
                        choices=('Open', 'In progress', 'Closed'), sortable=True),
        'priority': field('Priority', required=True, default='Medium', form='select',
                          choices=('Low', 'Medium', 'High'), sortable=True),
        'owner': field('Owner', sortable=True),
        'description': field('Description / response plan', max_length=10000, form='textarea'),
    },
    'changelog_entries': {
        'title': field('Title', required=True, default=None),
        'body': field('What changed?', max_length=10000, form='textarea'),
    },
}


def search_fields(table):
    return tuple(name for name, definition in FIELDS[table].items() if definition['searchable'])


def sort_options(table):
    options = {'newest': 'Newest first', 'oldest': 'Oldest first'}
    for name, definition in FIELDS[table].items():
        if not definition['sortable']:
            continue
        if name == 'priority':
            options.update(priority='Priority: high to low', priority_asc='Priority: low to high')
        else:
            options[name] = definition['label'] + ' A-Z'
            options[name + '_desc'] = definition['label'] + ' Z-A'
    return options


def active_record(table, record):
    if record is None:
        return None
    allowed = {'id', 'created_at', 'project_id', 'raid_count', 'change_count'} | set(FIELDS[table])
    return {key: value for key, value in record.items() if key in allowed}
