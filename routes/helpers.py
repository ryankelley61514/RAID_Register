"""Transport-specific request parsing; business validation lives in services."""
from flask import abort, request


def form_data():
    return {key: value for key, value in request.form.items() if key != 'csrf_token'}


def json_data():
    if not request.is_json:
        abort(415, 'Use Content-Type: application/json.')
    return request.get_json()
