import os
import re
import unittest
import uuid


from app import create_app
from database import Database


@unittest.skipUnless(os.environ.get('RUN_SQLSERVER_TESTS') == '1', 'Set RUN_SQLSERVER_TESTS=1 to run SQL Server integration tests')
class ProjectAppTests(unittest.TestCase):
    def setUp(self):
        import pyodbc
        config = create_app().config
        self.admin = pyodbc.connect(config['SQLSERVER_CONNECTION_STRING'], autocommit=True,
                                    timeout=int(config['SQLSERVER_LOGIN_TIMEOUT']))
        self.database = 'raid_test_' + uuid.uuid4().hex
        self.admin.execute(f'CREATE DATABASE [{self.database}]').close()
        self.addCleanup(self.cleanup_database)
        self.test_config = {
            'TESTING': True, 'SECRET_KEY': 'test-secret', 'DATABASE_BACKEND': 'sqlserver',
        }
        # Build an unambiguous string: ODBC uses the first occurrence of a keyword.
        self.test_config['SQLSERVER_CONNECTION_STRING'] = re.sub(
            r'(?i)(DATABASE|Initial Catalog)=[^;]*;', '', config['SQLSERVER_CONNECTION_STRING'].rstrip(';') + ';'
        ) + f'DATABASE={self.database};'
        self.app = create_app(self.test_config)
        database = Database(self.app.config)
        try:
            database.initialize()
            database.initialize()  # Initialization must be repeatable.
        finally:
            database.close()
        self.client = self.app.test_client()
        self.client.get('/')
        with self.client.session_transaction() as session:
            self.token = session['csrf_token']

    def cleanup_database(self):
        try:
            self.admin.execute(f'ALTER DATABASE [{self.database}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE').close()
            self.admin.execute(f'DROP DATABASE [{self.database}]').close()
        finally:
            self.admin.close()

    def post(self, path, **data):
        return self.client.post(path, data={'csrf_token': self.token, **data})

    def create_project(self, name='Launch'):
        result = self.post('/projects/new', name=name, description='A new project')
        self.assertEqual(result.status_code, 302)
        return result.location

    def test_project_and_child_lifecycle(self):
        project = self.create_project()
        for kind in ('Risk', 'Assumption', 'Issue', 'Dependency'):
            result = self.post(project + '/raid/new', kind=kind, title=kind + ' title',
                               description='Details', owner='Alex', status='Open', priority='High')
            self.assertEqual(result.status_code, 302)
        for title in ('Kickoff', 'Release'):
            self.assertEqual(self.post(project + '/changelog/new', title=title, body='Update').status_code, 302)
        page = self.client.get(project)
        self.assertEqual(page.status_code, 200)
        self.assertIn(b'Dependency title', page.data)
        self.assertIn(b'Release', page.data)
        self.assertIn(b'4 RAID records', self.client.get('/').data)
        for path in ('/edit', '/raid/1/edit', '/changelog/1/edit'):
            self.assertEqual(self.client.get(project + path).status_code, 200)
        self.post(project + '/edit', name='Renamed', description='Changed')
        self.post(project + '/raid/1/edit', kind='Issue', title='Resolved',
                  status='Closed', priority='Low', owner='Sam')
        self.post(project + '/changelog/1/edit', title='Updated kickoff', body='New details')
        page = self.client.get(project).data
        for text in (b'Renamed', b'Resolved', b'Closed', b'Updated kickoff'):
            self.assertIn(text, page)
        self.assertEqual(self.post(project + '/raid/1/delete').status_code, 302)
        self.assertEqual(self.post(project + '/changelog/1/delete').status_code, 302)
        self.assertEqual(self.post(project + '/delete').status_code, 302)
        connection = Database(self.app.config)
        try:
            for table in ('projects', 'raid_items', 'changelog_entries'):
                self.assertEqual(connection.execute(f'SELECT COUNT(*) AS total FROM {table}').fetchone()['total'], 0)
        finally:
            connection.close()

    def test_validation_and_csrf(self):
        self.assertEqual(self.client.post('/projects/new', data={'name': 'No token'}).status_code, 400)
        self.assertEqual(self.post('/projects/new', name='  ').status_code, 400)
        self.assertEqual(self.post('/projects/new', name='x' * 201).status_code, 400)
        project = self.create_project()
        self.assertEqual(self.post(project + '/raid/new', kind='Unknown', title='Test', status='Open', priority='Low').status_code, 400)
        self.assertEqual(self.post(project + '/changelog/new', title='').status_code, 400)
        self.assertEqual(self.client.get(project + '/delete').status_code, 405)
        self.assertEqual(self.client.get('/projects/999').status_code, 404)

    def test_child_records_cannot_be_accessed_through_other_projects(self):
        first = self.create_project('First')
        second = self.create_project('Second')
        self.post(first + '/raid/new', kind='Risk', title='First only', status='Open', priority='Low')
        self.post(first + '/changelog/new', title='Private to first')
        for record_type in ('raid', 'changelog'):
            self.assertEqual(self.client.get(second + f'/{record_type}/1/edit').status_code, 404)
            self.assertEqual(self.post(second + f'/{record_type}/1/edit').status_code, 404)
            self.assertEqual(self.post(second + f'/{record_type}/1/delete').status_code, 404)
        self.assertNotIn(b'First only', self.client.get(second).data)
        self.assertIn(b'First only', self.client.get(first).data)

    def test_persistence_and_html_escaping(self):
        project = self.create_project('<script>alert(1)</script>')
        another_app = create_app(self.test_config)
        page = another_app.test_client().get(project)
        self.assertIn(b'&lt;script&gt;', page.data)
        self.assertNotIn(b'<script>', page.data)


if __name__ == '__main__':
    unittest.main()
