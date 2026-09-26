"""Projects routes."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from database import db
from routes.helpers import field, project_or_404

bp = Blueprint('projects', __name__)


@bp.get('/')
def index():
    projects = db().execute('''
        SELECT p.*,
            (SELECT COUNT(*) FROM raid_items r WHERE r.project_id=p.id) AS raid_count,
            (SELECT COUNT(*) FROM changelog_entries c WHERE c.project_id=p.id) AS change_count
        FROM projects p ORDER BY p.id DESC
    ''').fetchall()
    return render_template('index.html', projects=projects)

@bp.route('/projects/new', methods=['GET', 'POST'])
def create_project():
    if request.method == 'POST':
        project_id = db().create_project(
                              (field('name', True, 200), field('description')))
        db().commit()
        flash('Project created.')
        return redirect(url_for('projects.project_detail', project_id=project_id))
    return render_template('project_form.html', project=None)

@bp.get('/projects/<int:project_id>')
def project_detail(project_id):
    project = project_or_404(project_id)
    items = db().execute('SELECT * FROM raid_items WHERE project_id=? ORDER BY id DESC', (project_id,)).fetchall()
    changes = db().execute('SELECT * FROM changelog_entries WHERE project_id=? ORDER BY id DESC', (project_id,)).fetchall()
    return render_template('project.html', project=project, items=items, changes=changes)

@bp.route('/projects/<int:project_id>/edit', methods=['GET', 'POST'])
def edit_project(project_id):
    project = project_or_404(project_id)
    if request.method == 'POST':
        db().execute('UPDATE projects SET name=?, description=? WHERE id=?',
                     (field('name', True, 200), field('description'), project_id))
        db().commit()
        flash('Project updated.')
        return redirect(url_for('projects.project_detail', project_id=project_id))
    return render_template('project_form.html', project=project)

@bp.post('/projects/<int:project_id>/delete')
def delete_project(project_id):
    project_or_404(project_id)
    db().execute('DELETE FROM projects WHERE id=?', (project_id,))
    db().commit()
    flash('Project and its records deleted.')
    return redirect(url_for('projects.index'))

@bp.post('/projects/<int:project_id>/<record_type>/<int:record_id>/delete')
def delete_record(project_id, record_type, record_id):
    project_or_404(project_id)
    tables = {'raid': 'raid_items', 'changelog': 'changelog_entries'}
    if record_type not in tables:
        abort(404)
    cursor = db().execute(f'DELETE FROM {tables[record_type]} WHERE id=? AND project_id=?', (record_id, project_id))
    if not cursor.rowcount:
        abort(404)
    db().commit()
    flash('Record deleted.')
    return redirect(url_for('projects.project_detail', project_id=project_id))

