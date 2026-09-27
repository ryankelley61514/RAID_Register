"""Web form routes backed by shared services."""
from flask import Blueprint, flash, redirect, render_template, request, url_for
import services
from routes.helpers import form_data

bp = Blueprint('changelog', __name__)

@bp.route('/projects/<int:project_id>/changelog/new', methods=['GET', 'POST'])
@bp.route('/projects/<int:project_id>/changelog/<int:entry_id>/edit', methods=['GET', 'POST'])
def changelog_form(project_id, entry_id=None):
    if request.method == 'POST':
        if entry_id is None:
            services.create_child(project_id, 'changelog', form_data())
        else:
            services.update_child(project_id, 'changelog', entry_id, form_data(), partial=False)
        flash('Changelog entry saved.')
        return redirect(url_for('projects.project_detail', project_id=project_id))
    project = services.get_project(project_id)
    entry = services.get_child(project_id, 'changelog', entry_id) if entry_id is not None else None
    return render_template('changelog_form.html', project=project, entry=entry)
