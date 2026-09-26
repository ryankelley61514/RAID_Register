import os
import secrets
from pathlib import Path

from database import db, close_db
from constants import RAID_TYPES, STATUSES, PRIORITIES
from routes.projects import bp as projects_bp
from routes.raid import bp as raid_bp
from routes.changelog import bp as changelog_bp
from routes.api import bp as api_bp

from flask import Flask, abort, render_template, request, session
from werkzeug.exceptions import HTTPException


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

    app.teardown_appcontext(close_db)

    @app.cli.command('init-db')
    def init_db():
        """Create missing tables and indexes for the selected database."""
        db().initialize()
        print(f"{app.config['DATABASE_BACKEND']} schema initialized.")

    @app.before_request
    def csrf_protection():
        if request.path == '/api' or request.path.startswith('/api/'):
            return  # API routes are read-only and do not use form sessions.
        if 'csrf_token' not in session:
            session['csrf_token'] = secrets.token_hex(32)
        if request.method == 'POST' and not secrets.compare_digest(
            session['csrf_token'], request.form.get('csrf_token', '')
        ):
            abort(400, 'Invalid form token. Refresh the page and try again.')

    @app.context_processor
    def template_globals():
        return dict(raid_types=RAID_TYPES, statuses=STATUSES, priorities=PRIORITIES)

    @app.errorhandler(HTTPException)
    def error_page(error):
        if request.path == '/api' or request.path.startswith('/api/'):
            response = error.get_response()
            response.data = app.json.dumps({'error': {'code': error.code, 'message': error.description}})
            response.content_type = 'application/json'
            return response
        return render_template('error.html', error=error), error.code

    for blueprint in (projects_bp, raid_bp, changelog_bp, api_bp):
        app.register_blueprint(blueprint)

    return app


if __name__ == '__main__':
    create_app().run()
