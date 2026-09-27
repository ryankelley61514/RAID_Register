# Project RAID Register

A Flask application for tracking projects with multiple RAID records and changelog entries. Projects, RAID records, and changelog entries can be created, viewed, edited, and deleted through the web interface.

## Run locally (PowerShell)

The project list supports case-insensitive name/description search and sorting by name or creation order. Each project's RAID register supports search across title, description, owner, type, status, and priority, with sorting by creation order, title, type, owner, status, or priority. Changelog search matches titles and entry text. With JavaScript enabled, search updates after a short typing pause, and sorting controls update results without a page reload. Requests that become outdated are cancelled; failures leave existing results visible with a retry message. Controls retain keyboard focus. Without JavaScript, forms continue to work through regular navigation. Filters are stored in URL query parameters; RAID and changelog controls preserve each other's filters. Empty the search field to show all records; use the sort dropdown to change ordering. Search treats special characters literally. The JSON API remains unfiltered. Filtering and sorting currently run in memory over the loaded lists, suitable for the app's unpaginated demo; larger datasets should use database-side filtering and pagination.

Routes are organized as Flask Blueprints in `routes/projects.py`, `routes/raid.py`, `routes/changelog.py`, and `routes/api.py` (including Swagger documentation). Shared validation, lookups, CRUD operations, and commit/rollback boundaries live in `services.py`. Web and JSON routes both call these services; `routes/helpers.py` only parses form/JSON requests. Service errors are translated centrally into HTML or JSON HTTP errors; database context helpers live in `database.py`, and field definitions and RAID options in `field_definitions.py`. `app.py` configures the application, registers the Blueprints, and maintains common CSRF protection, error handling, and CLI setup. Public URLs are unchanged; internal endpoint names use Blueprint prefixes, such as `projects.project_detail` and `api.api_docs`.

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

## JSON API

Interactive Swagger UI is available at `/api/docs` (locally, http://127.0.0.1:5000/api/docs). Expand an endpoint, click **Try it out**, enter any required IDs, and click **Execute**. Requests use the same host and selected database as the app.

The OpenAPI 3.0 specification is available at `/api/openapi.json` and generated from `field_definitions.py` and endpoint descriptions in `openapi_base.json`. Field schemas update automatically; edit endpoint descriptions when routes change. Swagger UI 5.17.14 is bundled in `static/vendor/swagger-ui/`, including its license and notices. Both the assets and specification are served locally; interactive documentation does not require internet access. External specification validation is disabled. Include this vendor directory in offline deployments.

These GET endpoints use the configured database (SQLite or SQL Server):

| GET endpoint | JSON response key |
| --- | --- |
| `/api/projects` | `projects` (array) |
| `/api/projects/<project_id>` | `project` (object) |
| `/api/projects/<project_id>/raid` | `raid_items` (array) |
| `/api/projects/<project_id>/raid/<item_id>` | `raid_item` (object) |
| `/api/projects/<project_id>/changelog` | `changelog_entries` (array) |
| `/api/projects/<project_id>/changelog/<entry_id>` | `changelog_entry` (object) |

The project detail endpoint `/api/projects/<project_id>` includes `raid_items` and `changelog_entries` arrays inside the `project` object. These contain all associated records, ordered by newest ID first, or empty arrays when none exist. The project list remains a summary without nested records.

Records include all their stored fields. Collections return newest IDs first, with empty arrays when there are no records. Timestamps use UTC ISO 8601, such as `2026-09-25T12:00:00Z`. Missing projects or records return HTTP 404; unsupported methods return HTTP 405. API HTTP errors use `{"error": {"code": 404, "message": "..."}}`. Child records must belong to the project in the URL.

```powershell
Invoke-RestMethod http://127.0.0.1:5000/api/projects
Invoke-RestMethod http://127.0.0.1:5000/api/projects/1/raid
```

The API has no authentication, like the current web interface. All visitors can read and modify all project data.

## Record fields

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


## JSON API writes

Use `Content-Type: application/json` for POST and PATCH requests.

| Resource | Create (POST) | Edit (PATCH) / delete (DELETE) |
| --- | --- | --- |
| Project | `/api/projects` | `/api/projects/<project_id>` |
| RAID | `/api/projects/<project_id>/raid` | `/api/projects/<project_id>/raid/<item_id>` |
| Changelog | `/api/projects/<project_id>/changelog` | `/api/projects/<project_id>/changelog/<entry_id>` |

Project creation requires `name`; RAID requires `kind` and `title`; changelog requires `title`. Optional text fields default to empty strings; RAID status defaults to `Open` and priority to `Medium`. PATCH changes only supplied fields. Unknown fields, read-only IDs/timestamps, null values, invalid enums, and empty bodies are rejected. Strings are trimmed and use the same length limits as web forms.

Creates return HTTP 201 with the created object and a `Location` header. Updates return HTTP 200 with the updated object. Deletes return HTTP 204 with no body. Missing or incorrectly scoped records return 404, invalid JSON/fields return 400, and non-JSON writes return 415. Deleting a project also deletes its RAID records and changelog entries. Swagger UI supports trying these operations against the active database; writes affect real records.

```powershell
Invoke-RestMethod http://127.0.0.1:5000/api/projects -Method Post -ContentType 'application/json' -Body '{"name":"API project"}'
Invoke-RestMethod http://127.0.0.1:5000/api/projects/1 -Method Patch -ContentType 'application/json' -Body '{"description":"Updated description"}'
Invoke-RestMethod http://127.0.0.1:5000/api/projects/1 -Method Delete
```


## Adding and retiring fields

`field_definitions.py` is the source of truth for editable text, multiline text, and select fields. Definitions drive form controls, shared validation, inserts/updates, searchable/sortable fields, record display, API response fields, and OpenAPI schemas. Restart the app after editing definitions.

For example, add this entry under `FIELDS['projects']`:

```python
'contact': field('Contact', max_length=200, default='', sortable=True),
```

Preview and apply missing columns to each existing database (select the backend first):

```powershell
.venv\Scripts\python -m flask --app app migrate-db
.venv\Scripts\python -m flask --app app migrate-db --apply
```

For a new database, `init-db` generates tables directly from the definitions. `schema_builder.py` generates SQL for both backends; there are no separate SQL schema snapshots to maintain. Migrations add missing columns and backfill defaults; they never drop data. New required fields must have a valid default when migrating existing records. Back up the database and review the preview before applying.

Removing a definition removes the input, API field, and search/sort option. Stored columns and their data remain. Columns created by this version are nullable to permit retirement; requiredness is enforced in the service layer. Older databases may have required columns with no default: retiring those requires a reviewed migration to allow NULL first, and `migrate-db` reports this condition. Column renames, type changes, and changes to existing database constraints are explicit custom migrations, not automatic operations. Dates, numbers, relationships, and custom widgets need additional implementation; the current registry supports string and select fields.
