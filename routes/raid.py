"""Web form routes backed by shared services."""
from flask import Blueprint, flash, redirect, render_template, request, url_for
import services
from routes.helpers import form_data

bp = Blueprint('raid', __name__)

@bp.route('/projects/<int:project_id>/raid/new', methods=['GET', 'POST'])
@bp.route('/projects/<int:project_id>/raid/<int:item_id>/edit', methods=['GET', 'POST'])
def raid_form(project_id, item_id=None):
    if request.method == 'POST':
        if item_id is None:
            services.create_child(project_id, 'raid', form_data())
        else:
            services.update_child(project_id, 'raid', item_id, form_data(), partial=False)
        flash('RAID record saved.')
        return redirect(url_for('projects.project_detail', project_id=project_id))
    project = services.get_project(project_id)
    item = services.get_child(project_id, 'raid', item_id) if item_id is not None else None
    return render_template('raid_form.html', project=project, item=item)
