# Project Ledger

A Flask application for tracking projects with multiple RAID records and changelog entries. Projects, RAID records, and changelog entries can be created, viewed, edited, and deleted through the web interface.

## Run locally (PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m flask --app app init-db
.venv\Scripts\python -m flask --app app run
```

Open http://127.0.0.1:5000.

## Database toggle

Set `DATABASE_BACKEND` to `sqlite` (demo) or `sqlserver` (production) in `instance/config.py`, or use an environment variable. Environment variables take precedence. Restart the app after changing settings and run `init-db` for the selected database. Changing the backend does not copy data between databases. SQL Server remains the local default.

For a local SQLite demo:

```powershell
$env:DATABASE_BACKEND = 'sqlite'
.venv\Scripts\python -m flask --app app init-db
.venv\Scripts\python -m flask --app app run
```

SQLite defaults to `instance/demo.sqlite`. Set `SQLITE_DATABASE` to another path if needed; relative paths are resolved inside `instance/`. To switch back, set `$env:DATABASE_BACKEND = 'sqlserver'` and restart Flask.

## Deploy a demo on Render

1. Push this project to a Git repository accessible to Render.
2. In Render, create a **Blueprint** and select the repository. Render reads `render.yaml`.
3. Deploy the service. The configuration installs `requirements-demo.txt`, selects SQLite, generates a session secret, initializes the schema on startup, and serves Flask through Gunicorn.

For manual Web Service setup, use build command `pip install -r requirements-demo.txt` and start command `python -m flask --app app init-db && gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 'app:create_app()'`. Set `DATABASE_BACKEND=sqlite` and a strong `SECRET_KEY` in Render's environment settings. See [Render's Flask guide](https://render.com/docs/deploy-flask).

The demo starts empty. All visitors share the same projects and can edit or delete them; there are no accounts or access restrictions. Use sample data only.

The supplied Blueprint uses the free plan with an [ephemeral filesystem](https://render.com/docs/free): SQLite data can disappear on restarts, redeploys, or spin-down. For persistent demo data, use a paid service with a [persistent disk](https://render.com/docs/disks), mount it at `/var/data`, and set `SQLITE_DATABASE=/var/data/demo.sqlite`. Keep a single service instance for this SQLite setup.

SQLite mode does not import or require `pyodbc`. For SQL Server hosting, install `requirements.txt` plus a production WSGI server and Microsoft ODBC Driver 18. A hosted service needs a reachable SQL Server endpoint and suitable credentials; `localhost\SQLEXPRESS` and your local Windows identity cannot be used from Render. The demo Blueprint is configured only for SQLite.

## SQL Server connection settings

Requires Microsoft ODBC Driver 18 for SQL Server and a running SQL Server instance. The default connection uses `localhost\SQLEXPRESS`, database `RAID_Register`, and Windows authentication. The Windows account running Flask must have access to the database; `init-db` also requires permission to create tables and indexes.

Edit `instance/config.py` to switch servers or databases, then restart Flask:

```python
SQLSERVER_CONNECTION_STRING = (
    'DRIVER={ODBC Driver 18 for SQL Server};'
    r'SERVER=localhost\SQLEXPRESS;'
    'DATABASE=RAID_Register;Trusted_Connection=yes;'
    'Encrypt=yes;TrustServerCertificate=yes;MARS_Connection=no;'
)
SQLSERVER_COMMAND_TIMEOUT = 0  # No query timeout
SQLSERVER_LOGIN_TIMEOUT = 15  # Connection timeout in seconds
```

`instance/config.py` is ignored by Git. On a fresh checkout, create it using the example above. Defaults live in `config.py`. Environment variables `SQLSERVER_CONNECTION_STRING`, `SQLSERVER_COMMAND_TIMEOUT`, and `SQLSERVER_LOGIN_TIMEOUT` override both files. For example:

```powershell
$env:SQLSERVER_CONNECTION_STRING = 'DRIVER={ODBC Driver 18 for SQL Server};SERVER=other-server;DATABASE=ProjectLedger;Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes;MARS_Connection=no;'
```

The supplied .NET connection string is expressed using [ODBC connection keywords](https://learn.microsoft.com/sql/connect/odbc/dsn-connection-string-attribute). Windows authentication uses `Trusted_Connection=yes`; pooling is disabled in `database.py`, and command timeout is applied to each connection. No password is stored for Windows authentication.

Run `flask --app app init-db` using the virtual environment after selecting an existing database. It creates missing tables and indexes without dropping existing data. Database creation and SQLite data migration are not automatic. Any existing `instance/projects.sqlite` remains untouched; switching connections does not copy records. Use SQL Server backups for the new database.

A local session secret is generated in `instance/secret.key`; you can override it with the `SECRET_KEY` environment variable.

## Data model

- `projects`: name, description, creation timestamp.
- `raid_items`: project, type (Risk, Assumption, Issue, Dependency), title, description/response plan, owner, status, priority, creation timestamp.
- `changelog_entries`: project, title, body, creation timestamp (UTC).

Each project has independent one-to-many relationships with RAID records and changelog entries. Deleting a project deletes its associated records. Changelog entries are manually authored updates, rather than an automatic audit trail.

The app includes form CSRF protection, server-side validation, parameterized database queries, and escaped templates. It is intended for local use; authentication and authorization are not included.

## Tests

```powershell
.venv\Scripts\python -m unittest discover -s tests -v
```

The default run executes unit tests and SQLite integration tests, and skips SQL Server integration tests. To opt in to integration tests, set `$env:RUN_SQLSERVER_TESTS = '1'` before running the command. These tests require database creation privileges on the configured server. Each test creates a uniquely named `raid_test_<uuid>` database, exercises the app, and drops that test database during cleanup. They do not run against your application tables.
