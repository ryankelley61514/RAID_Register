"""Changelog routes."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from database import db
from routes.helpers import field, project_or_404

bp = Blueprint('changelog', __name__)


@bp.route('/projects/<int:project_id>/changelog/new', methods=['GET', 'POST'])
@bp.route('/projects/<int:project_id>/changelog/<int:entry_id>/edit', methods=['GET', 'POST'])
def changelog_form(project_id, entry_id=None):
    project = project_or_404(project_id)
    entry = None
    if entry_id is not None:
        entry = db().execute('SELECT * FROM changelog_entries WHERE id=? AND project_id=?', (entry_id, project_id)).fetchone()
        if entry is None:
            abort(404)
    if request.method == 'POST':
        values = (field('title', True, 200), field('body'))
        if entry is None:
            db().execute('INSERT INTO changelog_entries(title,body,project_id) VALUES (?,?,?)', values + (project_id,))
        else:
            db().execute('UPDATE changelog_entries SET title=?,body=? WHERE id=? AND project_id=?', values + (entry_id, project_id))
        db().commit()
        flash('Changelog entry saved.')
        return redirect(url_for('projects.project_detail', project_id=project_id))
    return render_template('changelog_form.html', project=project, entry=entry)

