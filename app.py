import os
import secrets
from pathlib import Path

from database import Database

from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for


RAID_TYPES = ('Risk', 'Assumption', 'Issue', 'Dependency')
STATUSES = ('Open', 'In progress', 'Closed')
PRIORITIES = ('Low', 'Medium', 'High')


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    app.config.from_object('config')
    app.config.from_pyfile('config.py', silent=True)
    for name in ('DATABASE_BACKEND', 'SQLITE_DATABASE', 'SECRET_KEY', 'SQLSERVER_CONNECTION_STRING', 'SQLSERVER_COMMAND_TIMEOUT', 'SQLSERVER_LOGIN_TIMEOUT'):
        if name in os.environ:
            app.config[name] = os.environ[name]
    if test_config:
        app.config.update(test_config)
    backend = app.config['DATABASE_BACKEND'].strip().lower()
    if backend not in ('sqlite', 'sqlserver'):
        raise ValueError('DATABASE_BACKEND must be sqlite or sqlserver')
    app.config['DATABASE_BACKEND'] = backend
    sqlite_path = Path(app.config['SQLITE_DATABASE'])
    if not sqlite_path.is_absolute():
        sqlite_path = Path(app.instance_path) / sqlite_path
    app.config['SQLITE_DATABASE'] = str(sqlite_path)
    if not app.config.get('SECRET_KEY'):
        key_file = Path(app.instance_path) / 'secret.key'
        if not key_file.exists():
            try:
                with key_file.open('x') as key:
                    key.write(secrets.token_hex(32))
            except FileExistsError:
                pass
        app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or key_file.read_text()

    def db():
        if 'db' not in g:
            g.db = Database(app.config)
        return g.db

    @app.teardown_appcontext
    def close_db(error=None):
        connection = g.pop('db', None)
        if connection is not None:
            connection.close()

    @app.cli.command('init-db')
    def init_db():
        """Create missing tables and indexes for the selected database."""
        db().initialize()
        print(f"{app.config['DATABASE_BACKEND']} schema initialized.")

    @app.before_request
    def csrf_protection():
        if 'csrf_token' not in session:
            session['csrf_token'] = secrets.token_hex(32)
        if request.method == 'POST' and not secrets.compare_digest(
            session['csrf_token'], request.form.get('csrf_token', '')
        ):
            abort(400, 'Invalid form token. Refresh the page and try again.')

    @app.context_processor
    def template_globals():
        return dict(raid_types=RAID_TYPES, statuses=STATUSES, priorities=PRIORITIES)

    def project_or_404(project_id):
        project = db().execute('SELECT * FROM projects WHERE id = ?', (project_id,)).fetchone()
        if project is None:
            abort(404)
        return project

    def field(name, required=False, limit=10000):
        value = request.form.get(name, '').strip()
        if (required and not value) or len(value) > limit:
            abort(400, f'{name.replace("_", " ").title()} is required and must be at most {limit} characters.'
                  if required else f'{name.title()} must be at most {limit} characters.')
        return value

    @app.get('/')
    def index():
        projects = db().execute('''
            SELECT p.*,
                (SELECT COUNT(*) FROM raid_items r WHERE r.project_id=p.id) AS raid_count,
                (SELECT COUNT(*) FROM changelog_entries c WHERE c.project_id=p.id) AS change_count
            FROM projects p ORDER BY p.id DESC
        ''').fetchall()
        return render_template('index.html', projects=projects)

    @app.route('/projects/new', methods=['GET', 'POST'])
    def create_project():
        if request.method == 'POST':
            project_id = db().create_project(
                                  (field('name', True, 200), field('description')))
            db().commit()
            flash('Project created.')
            return redirect(url_for('project_detail', project_id=project_id))
        return render_template('project_form.html', project=None)

    @app.get('/projects/<int:project_id>')
    def project_detail(project_id):
        project = project_or_404(project_id)
        items = db().execute('SELECT * FROM raid_items WHERE project_id=? ORDER BY id DESC', (project_id,)).fetchall()
        changes = db().execute('SELECT * FROM changelog_entries WHERE project_id=? ORDER BY id DESC', (project_id,)).fetchall()
        return render_template('project.html', project=project, items=items, changes=changes)

    @app.route('/projects/<int:project_id>/edit', methods=['GET', 'POST'])
    def edit_project(project_id):
        project = project_or_404(project_id)
        if request.method == 'POST':
            db().execute('UPDATE projects SET name=?, description=? WHERE id=?',
                         (field('name', True, 200), field('description'), project_id))
            db().commit()
            flash('Project updated.')
            return redirect(url_for('project_detail', project_id=project_id))
        return render_template('project_form.html', project=project)

    @app.post('/projects/<int:project_id>/delete')
    def delete_project(project_id):
        project_or_404(project_id)
        db().execute('DELETE FROM projects WHERE id=?', (project_id,))
        db().commit()
        flash('Project and its records deleted.')
        return redirect(url_for('index'))

    @app.route('/projects/<int:project_id>/raid/new', methods=['GET', 'POST'])
    @app.route('/projects/<int:project_id>/raid/<int:item_id>/edit', methods=['GET', 'POST'])
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
            return redirect(url_for('project_detail', project_id=project_id))
        return render_template('raid_form.html', project=project, item=item)

    @app.route('/projects/<int:project_id>/changelog/new', methods=['GET', 'POST'])
    @app.route('/projects/<int:project_id>/changelog/<int:entry_id>/edit', methods=['GET', 'POST'])
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
            return redirect(url_for('project_detail', project_id=project_id))
        return render_template('changelog_form.html', project=project, entry=entry)

    @app.post('/projects/<int:project_id>/<record_type>/<int:record_id>/delete')
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
        return redirect(url_for('project_detail', project_id=project_id))

    @app.errorhandler(400)
    @app.errorhandler(404)
    def error_page(error):
        return render_template('error.html', error=error), error.code

    return app


if __name__ == '__main__':
    create_app().run()
