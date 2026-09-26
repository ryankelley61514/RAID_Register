import tempfile
from pathlib import Path
from unittest.mock import patch

from app import create_app
from database import Database
import test_app


class SQLiteAppTests(test_app.ProjectAppTests):
    __unittest_skip__ = False
    __unittest_skip_why__ = ''

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.test_config = {
            'TESTING': True, 'SECRET_KEY': 'test-secret',
            'DATABASE_BACKEND': 'sqlite',
            'SQLITE_DATABASE': str(Path(self.temp.name) / 'demo.sqlite'),
        }
        self.app = create_app(self.test_config)
        database = Database(self.app.config)
        try:
            database.initialize()
            database.initialize()
        finally:
            database.close()
        self.client = self.app.test_client()
        self.client.get('/')
        with self.client.session_transaction() as session:
            self.token = session['csrf_token']

    def test_sqlite_does_not_import_odbc(self):
        with patch.dict('sys.modules', {'pyodbc': None}):
            database = Database(self.app.config)
            database.close()

    def test_invalid_backend_fails_explicitly(self):
        with self.assertRaisesRegex(ValueError, 'DATABASE_BACKEND'):
            create_app({'DATABASE_BACKEND': 'unknown'})

    def test_init_command(self):
        result = self.app.test_cli_runner().invoke(args=['init-db'])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn('sqlite schema initialized', result.output)
