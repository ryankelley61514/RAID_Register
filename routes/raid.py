"""Raid routes."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from database import db
from routes.helpers import field, project_or_404
from constants import RAID_TYPES, STATUSES, PRIORITIES

bp = Blueprint('raid', __name__)


@bp.route('/projects/<int:project_id>/raid/new', methods=['GET', 'POST'])
@bp.route('/projects/<int:project_id>/raid/<int:item_id>/edit', methods=['GET', 'POST'])
def raid_form(project_id, item_id=None):
    project = project_or_404(project_id)
    item = None
    if item_id is not None:
        item = db().execute('SELECT * FROM raid_items WHERE id=? AND project_id=?', (item_id, project_id)).fetchone()
        if item is None:
            abort(404)
    if request.method == 'POST':
        kind, status, priority = field('kind'), field('status'), field('priority')
        if kind not in RAID_TYPES or status not in STATUSES or priority not in PRIORITIES:
            abort(400, 'Select a valid type, status, and priority.')
        values = (kind, field('title', True, 200), field('description'), field('owner', limit=200), status, priority)
        if item is None:
            db().execute('INSERT INTO raid_items(kind,title,description,owner,status,priority,project_id) VALUES (?,?,?,?,?,?,?)', values + (project_id,))
        else:
            db().execute('UPDATE raid_items SET kind=?,title=?,description=?,owner=?,status=?,priority=? WHERE id=? AND project_id=?', values + (item_id, project_id))
        db().commit()
        flash('RAID record saved.')
        return redirect(url_for('projects.project_detail', project_id=project_id))
    return render_template('raid_form.html', project=project, item=item)

