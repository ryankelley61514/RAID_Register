"""Shared route lookups and form validation."""
from flask import abort, request

from database import db


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

