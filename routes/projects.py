"""Projects routes."""
from flask import Blueprint, flash, redirect, render_template, request, url_for

import services
from field_definitions import search_fields, sort_options, FIELDS
from routes.helpers import form_data

bp = Blueprint('projects', __name__)

def search_records(records, query, fields):
    """Literal, case-insensitive search, consistent across database backends."""
    needle = query.casefold()
    return [record for record in records if any(needle in str(record[field]).casefold() for field in fields)]


def sort_records(records, selected):
    if selected in ('newest', 'oldest'):
        return sorted(records, key=lambda row: row['id'], reverse=selected == 'newest')
    if selected in ('priority', 'priority_asc'):
        rank = {value: index for index, value in enumerate(FIELDS['raid_items']['priority']['choices'])}
        return sorted(records, key=lambda row: rank[row['priority']], reverse=selected == 'priority')
    field = selected.removesuffix('_desc')
    return sorted(records, key=lambda row: row[field].casefold(), reverse=selected.endswith('_desc'))



@bp.get('/')
def index():
    project_sorts = sort_options('projects')
    projects = services.list_projects(with_counts=True)
    query = request.args.get('q', '').strip()
    selected = request.args.get('sort', 'newest')
    if selected not in project_sorts:
        selected = 'newest'
    total = len(projects)
    projects = sort_records(search_records(projects, query, search_fields('projects')), selected)
    return render_template('index.html', projects=projects, query=query, selected_sort=selected, project_sorts=project_sorts, total=total)

@bp.route('/projects/new', methods=['GET', 'POST'])
def create_project():
    if request.method == 'POST':
        project_id = services.create_project(form_data())['id']
        flash('Project created.')
        return redirect(url_for('projects.project_detail', project_id=project_id))
    return render_template('project_form.html', project=None)

@bp.get('/projects/<int:project_id>')
def project_detail(project_id):
    raid_sorts = sort_options('raid_items')
    project = services.get_project_details(project_id)
    items = project['raid_items']
    changes = project['changelog_entries']
    raid_query = request.args.get('raid_q', '').strip()
    change_query = request.args.get('change_q', '').strip()
    selected = request.args.get('raid_sort', 'newest')
    if selected not in raid_sorts:
        selected = 'newest'
    raid_total, change_total = len(items), len(changes)
    items = sort_records(search_records(items, raid_query, search_fields('raid_items')), selected)
    changes = search_records(changes, change_query, search_fields('changelog_entries'))
    return render_template('project.html', project=project, items=items, changes=changes,
                           raid_query=raid_query, change_query=change_query, selected_sort=selected,
                           raid_sorts=raid_sorts, raid_total=raid_total, change_total=change_total)

@bp.route('/projects/<int:project_id>/edit', methods=['GET', 'POST'])
def edit_project(project_id):
    if request.method == 'POST':
        services.update_project(project_id, form_data(), partial=False)
        flash('Project updated.')
        return redirect(url_for('projects.project_detail', project_id=project_id))
    return render_template('project_form.html', project=services.get_project(project_id))

@bp.post('/projects/<int:project_id>/delete')
def delete_project(project_id):
    services.delete_project(project_id)
    flash('Project and its records deleted.')
    return redirect(url_for('projects.index'))

@bp.post('/projects/<int:project_id>/<record_type>/<int:record_id>/delete')
def delete_record(project_id, record_type, record_id):
    services.delete_child(project_id, record_type, record_id)
    flash('Record deleted.')
    return redirect(url_for('projects.project_detail', project_id=project_id))

