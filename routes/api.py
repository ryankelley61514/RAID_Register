"""Api routes."""
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, render_template, request, url_for

import services
from routes.helpers import json_data

bp = Blueprint('api', __name__)


def api_record(record):
    data = dict(record)
    created = data.get('created_at')
    if created is not None:
        if isinstance(created, str):
            created = datetime.fromisoformat(created)
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        data['created_at'] = created.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')
    return data

@bp.get('/api/openapi.json')
def api_spec():
    return current_app.send_static_file('openapi.json')

@bp.get('/api/docs')
def api_docs():
    return render_template('api_docs.html')

@bp.get('/api/projects')
def api_projects():
    projects = services.list_projects()
    return jsonify(projects=[api_record(project) for project in projects])

@bp.get('/api/projects/<int:project_id>')
def api_project(project_id):
    return project_response(services.get_project_details(project_id))


def project_response(details):
    project = api_record(details)
    project['raid_items'] = [api_record(item) for item in details['raid_items']]
    project['changelog_entries'] = [api_record(entry) for entry in details['changelog_entries']]
    return jsonify(project=project)


@bp.get('/api/projects/<int:project_id>/raid')
def api_raid_items(project_id):
    items = services.list_children(project_id, 'raid')
    return jsonify(raid_items=[api_record(item) for item in items])

@bp.get('/api/projects/<int:project_id>/raid/<int:item_id>')
def api_raid_item(project_id, item_id):
    item = services.get_child(project_id, 'raid', item_id)
    return jsonify(raid_item=api_record(item))

@bp.get('/api/projects/<int:project_id>/changelog')
def api_changelog_entries(project_id):
    entries = services.list_children(project_id, 'changelog')
    return jsonify(changelog_entries=[api_record(entry) for entry in entries])

@bp.get('/api/projects/<int:project_id>/changelog/<int:entry_id>')
def api_changelog_entry(project_id, entry_id):
    entry = services.get_child(project_id, 'changelog', entry_id)
    return jsonify(changelog_entry=api_record(entry))



@bp.post('/api/projects')
def api_create_project():
    project = services.create_project(json_data())
    return project_response(services.project_details(project)), 201, {'Location': url_for('api.api_project', project_id=project['id'])}


@bp.patch('/api/projects/<int:project_id>')
def api_update_project(project_id):
    project = services.update_project(project_id, json_data())
    return project_response(services.project_details(project))


@bp.delete('/api/projects/<int:project_id>')
def api_delete_project(project_id):
    services.delete_project(project_id)
    return '', 204


CHILD_KEYS = {'raid': 'raid_item', 'changelog': 'changelog_entry'}


@bp.post('/api/projects/<int:project_id>/raid', defaults={'kind': 'raid'})
@bp.post('/api/projects/<int:project_id>/changelog', defaults={'kind': 'changelog'})
def api_create_child(project_id, kind):
    key = CHILD_KEYS[kind]
    record = services.create_child(project_id, kind, json_data())
    record_id = record['id']
    endpoint, id_name = ('api.api_raid_item', 'item_id') if kind == 'raid' else ('api.api_changelog_entry', 'entry_id')
    location = url_for(endpoint, project_id=project_id, **{id_name: record_id})
    return jsonify({key: api_record(record)}), 201, {'Location': location}


@bp.route('/api/projects/<int:project_id>/raid/<int:item_id>', methods=['PATCH', 'DELETE'], defaults={'kind': 'raid'})
@bp.route('/api/projects/<int:project_id>/changelog/<int:entry_id>', methods=['PATCH', 'DELETE'], defaults={'kind': 'changelog'})
def api_modify_child(project_id, kind, item_id=None, entry_id=None):
    record_id = item_id if kind == 'raid' else entry_id
    if request.method == 'DELETE':
        services.delete_child(project_id, kind, record_id)
        return '', 204
    record = services.update_child(project_id, kind, record_id, json_data())
    return jsonify({CHILD_KEYS[kind]: api_record(record)})
