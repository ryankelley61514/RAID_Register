"""Api routes."""
from datetime import datetime, timezone

from flask import Blueprint, abort, current_app, jsonify, render_template

from database import db
from routes.helpers import project_or_404

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
    projects = db().execute('SELECT * FROM projects ORDER BY id DESC').fetchall()
    return jsonify(projects=[api_record(project) for project in projects])

@bp.get('/api/projects/<int:project_id>')
def api_project(project_id):
    project = api_record(project_or_404(project_id))
    items = db().execute('SELECT * FROM raid_items WHERE project_id=? ORDER BY id DESC', (project_id,)).fetchall()
    entries = db().execute('SELECT * FROM changelog_entries WHERE project_id=? ORDER BY id DESC', (project_id,)).fetchall()
    project['raid_items'] = [api_record(item) for item in items]
    project['changelog_entries'] = [api_record(entry) for entry in entries]
    return jsonify(project=project)

@bp.get('/api/projects/<int:project_id>/raid')
def api_raid_items(project_id):
    project_or_404(project_id)
    items = db().execute('SELECT * FROM raid_items WHERE project_id=? ORDER BY id DESC', (project_id,)).fetchall()
    return jsonify(raid_items=[api_record(item) for item in items])

@bp.get('/api/projects/<int:project_id>/raid/<int:item_id>')
def api_raid_item(project_id, item_id):
    project_or_404(project_id)
    item = db().execute('SELECT * FROM raid_items WHERE project_id=? AND id=?', (project_id, item_id)).fetchone()
    if item is None:
        abort(404)
    return jsonify(raid_item=api_record(item))

@bp.get('/api/projects/<int:project_id>/changelog')
def api_changelog_entries(project_id):
    project_or_404(project_id)
    entries = db().execute('SELECT * FROM changelog_entries WHERE project_id=? ORDER BY id DESC', (project_id,)).fetchall()
    return jsonify(changelog_entries=[api_record(entry) for entry in entries])

@bp.get('/api/projects/<int:project_id>/changelog/<int:entry_id>')
def api_changelog_entry(project_id, entry_id):
    project_or_404(project_id)
    entry = db().execute('SELECT * FROM changelog_entries WHERE project_id=? AND id=?', (project_id, entry_id)).fetchone()
    if entry is None:
        abort(404)
    return jsonify(changelog_entry=api_record(entry))

