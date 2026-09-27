"""Endpoint descriptions stay in JSON; field schemas come from the registry."""
import copy
import json
from pathlib import Path
from field_definitions import FIELDS


def openapi_spec():
    spec = json.loads(Path(__file__).with_name('openapi_base.json').read_text(encoding='utf-8'))
    schemas = spec['components']['schemas']
    for table, model in [('projects', 'Project'), ('raid_items', 'RaidItem'), ('changelog_entries', 'ChangelogEntry')]:
        fields = {}
        for name, definition in FIELDS[table].items():
            item = {'type': definition['type'], 'maxLength': definition['max_length'], 'description': definition['label']}
            if definition['choices']:
                item['enum'] = list(definition['choices'])
            if definition['required']:
                item['minLength'] = 1
            if definition['default'] is not None:
                item['default'] = definition['default']
            fields[name] = item
        properties = {'id': {'type': 'integer'}, **fields,
                      'created_at': {'type': 'string', 'format': 'date-time'}}
        if table != 'projects':
            properties['project_id'] = {'type': 'integer'}
        schemas[model] = {'type': 'object', 'required': list(properties), 'properties': properties}
        required = [name for name, definition in FIELDS[table].items() if definition['required'] and definition['default'] is None]
        for suffix in ('Create', 'Update'):
            schema = {'type': 'object', 'additionalProperties': False, 'minProperties': 1, 'properties': copy.deepcopy(fields)}
            if suffix == 'Create' and required:
                schema['required'] = required
            schemas[model + suffix] = schema
    detail = copy.deepcopy(schemas['Project'])
    for name, model in [('raid_items', 'RaidItem'), ('changelog_entries', 'ChangelogEntry')]:
        detail['required'].append(name)
        detail['properties'][name] = {'type': 'array', 'items': {'$ref': '#/components/schemas/' + model}}
    schemas['ProjectDetail'] = detail
    return spec
