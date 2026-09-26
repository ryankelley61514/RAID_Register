"""Projects routes."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from database import db
from routes.helpers import field, project_or_404

bp = Blueprint('projects', __name__)

PROJECT_SORTS = {'newest': 'Newest first', 'oldest': 'Oldest first', 'name': 'Name A-Z', 'name_desc': 'Name Z-A'}
RAID_SORTS = {'newest': 'Newest first', 'oldest': 'Oldest first', 'title': 'Title A-Z', 'title_desc': 'Title Z-A', 'kind': 'Type A-Z', 'owner': 'Owner A-Z', 'status': 'Status A-Z', 'priority': 'Priority: high to low', 'priority_asc': 'Priority: low to high'}


def search_records(records, query, fields):
    """Literal, case-insensitive search, consistent across database backends."""
    needle = query.casefold()
    return [record for record in records if any(needle in str(record[field]).casefold() for field in fields)]


def sort_records(records, selected):
    if selected in ('newest', 'oldest'):
        return sorted(records, key=lambda row: row['id'], reverse=selected == 'newest')
    if selected in ('priority', 'priority_asc'):
        rank = {'Low': 0, 'Medium': 1, 'High': 2}
        return sorted(records, key=lambda row: rank[row['priority']], reverse=selected == 'priority')
    field = selected.removesuffix('_desc')
    return sorted(records, key=lambda row: row[field].casefold(), reverse=selected.endswith('_desc'))



@bp.get('/')
def index():
    projects = db().execute('''
        SELECT p.*,
            (SELECT COUNT(*) FROM raid_items r WHERE r.project_id=p.id) AS raid_count,
            (SELECT COUNT(*) FROM changelog_entries c WHERE c.project_id=p.id) AS change_count
        FROM projects p ORDER BY p.id DESC
    ''').fetchall()
    query = request.args.get('q', '').strip()
    selected = request.args.get('sort', 'newest')
    if selected not in PROJECT_SORTS:
        selected = 'newest'
    total = len(projects)
    projects = sort_records(search_records(projects, query, ('name', 'description')), selected)
    return render_template('index.html', projects=projects, query=query, selected_sort=selected, project_sorts=PROJECT_SORTS, total=total)

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
    raid_query = request.args.get('raid_q', '').strip()
    change_query = request.args.get('change_q', '').strip()
    selected = request.args.get('raid_sort', 'newest')
    if selected not in RAID_SORTS:
        selected = 'newest'
    raid_total, change_total = len(items), len(changes)
    items = sort_records(search_records(items, raid_query, ('title', 'description', 'owner', 'kind', 'status', 'priority')), selected)
    changes = search_records(changes, change_query, ('title', 'body'))
    return render_template('project.html', project=project, items=items, changes=changes,
                           raid_query=raid_query, change_query=change_query, selected_sort=selected,
                           raid_sorts=RAID_SORTS, raid_total=raid_total, change_total=change_total)

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

