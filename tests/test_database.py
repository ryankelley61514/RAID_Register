import os
import unittest
from unittest.mock import MagicMock, patch

from app import create_app
from database import Database


class DatabaseTests(unittest.TestCase):
    @patch('pyodbc.connect')
    def test_connection_settings_and_result_consumption(self, connect):
        config = {'SQLSERVER_CONNECTION_STRING': 'test-connection',
                  'SQLSERVER_LOGIN_TIMEOUT': 15, 'SQLSERVER_COMMAND_TIMEOUT': 0}
        database = Database(config)
        connect.assert_called_once_with('test-connection', timeout=15, autocommit=False)
        self.assertEqual(connect.return_value.timeout, 0)
        cursor = connect.return_value.cursor.return_value
        cursor.description = [('id',), ('name',)]
        cursor.fetchall.return_value = [(42, 'Project')]
        result = database.execute('SELECT id, name FROM dbo.projects WHERE id=?', (42,))
        self.assertEqual(result.fetchone(), {'id': 42, 'name': 'Project'})
        cursor.execute.assert_called_once_with('SELECT id, name FROM dbo.projects WHERE id=?', (42,))
        cursor.close.assert_called_once()

    @patch('pyodbc.connect')
    def test_failure_closes_cursor_and_schema_failure_rolls_back(self, connect):
        database = Database(create_app({'SECRET_KEY': 'test', 'DATABASE_BACKEND': 'sqlserver'}).config)
        cursor = connect.return_value.cursor.return_value
        cursor.execute.side_effect = RuntimeError('SQL failed')
        with self.assertRaises(RuntimeError):
            database.execute('invalid SQL')
        cursor.close.assert_called_once()
        cursor.close.reset_mock()
        with self.assertRaises(RuntimeError):
            database.initialize()
        connect.return_value.rollback.assert_called_once()
        cursor.close.assert_called_once()

    @patch.dict(os.environ, {'SQLSERVER_CONNECTION_STRING': 'environment-server',
                            'SQLSERVER_COMMAND_TIMEOUT': '30'})
    def test_backend_configuration_overrides(self):
        app = create_app({'SECRET_KEY': 'test'})
        self.assertEqual(app.config['SQLSERVER_CONNECTION_STRING'], 'environment-server')
        self.assertEqual(app.config['SQLSERVER_COMMAND_TIMEOUT'], '30')
        app = create_app({'SECRET_KEY': 'test', 'SQLSERVER_CONNECTION_STRING': 'test-server'})
        self.assertEqual(app.config['SQLSERVER_CONNECTION_STRING'], 'test-server')


if __name__ == '__main__':
    unittest.main()
