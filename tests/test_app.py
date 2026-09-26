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

    def test_json_write_lifecycle(self):
        created = self.client.post('/api/projects', json={'name': 'API write'})
        self.assertEqual(created.status_code, 201)
        project = created.headers['Location']
        other = self.client.post('/api/projects', json={'name': 'Other'}).headers['Location']
        changed = self.client.patch(project, json={'description': 'Changed'})
        self.assertEqual(changed.status_code, 200)
        self.assertEqual(changed.get_json()['project']['name'], 'API write')
        for kind, key, payload in [('raid', 'raid_item', {'title': 'Risk', 'kind': 'Risk'}),
                                   ('changelog', 'changelog_entry', {'title': 'Kickoff'})]:
            result = self.client.post(project + '/' + kind, json=payload)
            self.assertEqual(result.status_code, 201)
            location = result.headers['Location']
            record = result.get_json()[key]
            self.assertEqual(self.client.get(location).get_json()[key], record)
            wrong = other + '/' + kind + '/' + str(record['id'])
            self.assertEqual(self.client.patch(wrong, json={'title': 'Wrong'}).status_code, 404)
            self.assertEqual(self.client.delete(wrong).status_code, 404)
            updated = self.client.patch(location, json={'title': 'Updated'})
            self.assertEqual(updated.status_code, 200)
            self.assertEqual(updated.get_json()[key]['title'], 'Updated')
            self.assertEqual(updated.get_json()[key]['created_at'], record['created_at'])
            deleted = self.client.delete(location)
            self.assertEqual(deleted.status_code, 204)
            self.assertEqual(deleted.data, b'')
            self.assertEqual(self.client.get(location).status_code, 404)
            self.assertEqual(self.client.post(project + '/' + kind, json=payload).status_code, 201)
        self.assertEqual(self.client.delete(project).status_code, 204)
        self.assertEqual(self.client.get(project).status_code, 404)
        connection = Database(self.app.config)
        try:
            for table in ('raid_items', 'changelog_entries'):
                self.assertEqual(connection.execute(f'SELECT COUNT(*) AS n FROM {table}').fetchone()['n'], 0)
        finally:
            connection.close()

    def test_json_write_validation(self):
        for payload in (None, [], {}, {'name': None}, {'name': ' '}, {'name': 5},
                        {'name': 'x' * 201}, {'name': 'Test', 'id': 1}):
            result = self.client.post('/api/projects', data=__import__('json').dumps(payload), content_type='application/json')
            self.assertEqual(result.status_code, 400)
            self.assertTrue(result.is_json)
        self.assertEqual(self.client.post('/api/projects', data='{}').status_code, 415)
        self.assertEqual(self.client.post('/api/projects', data='{', content_type='application/json').status_code, 400)
        project = self.client.post('/api/projects', json={'name': 'Valid'}).headers['Location']
        for payload in ({'kind': 'Invalid', 'title': 'X'}, {'kind': 'Risk', 'title': 'X', 'priority': 'Invalid'}):
            self.assertEqual(self.client.post(project + '/raid', json=payload).status_code, 400)
        self.assertEqual(self.client.patch(project, json={'name': ''}).status_code, 400)
        self.assertEqual(self.client.get(project).get_json()['project']['name'], 'Valid')
        self.assertEqual(self.client.post('/api/projects/999/raid', json={'title': 'X', 'kind': 'Risk'}).status_code, 404)

    def test_json_api(self):
        self.assertEqual(self.client.get('/api/projects').get_json(), {'projects': []})
        project = self.create_project('API project')
        api = '/api' + project
        self.assertEqual(self.client.get(api + '/raid').get_json(), {'raid_items': []})
        self.assertEqual(self.client.get(api + '/changelog').get_json(), {'changelog_entries': []})
        self.post(project + '/raid/new', kind='Risk', title='Delivery', status='Open', priority='High')
        self.post(project + '/changelog/new', title='Kickoff', body='Started')
        response = self.client.get('/api/projects')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_json)
        data = response.get_json()['projects'][0]
        self.assertEqual(data['name'], 'API project')
        self.assertRegex(data['created_at'], r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$')
        expanded = self.client.get(api).get_json()['project']
        self.assertEqual({key: expanded[key] for key in data}, data)
        for path, collection, singular in [('raid', 'raid_items', 'raid_item'),
                                           ('changelog', 'changelog_entries', 'changelog_entry')]:
            records = self.client.get(api + '/' + path).get_json()[collection]
            self.assertEqual(len(records), 1)
            self.assertEqual(expanded[collection], records)
            detail = self.client.get(api + '/' + path + '/' + str(records[0]['id']))
            self.assertEqual(detail.get_json()[singular], records[0])
            other = self.create_project('Other')
            wrong_parent = self.client.get('/api' + other + '/' + path + '/' + str(records[0]['id']))
            self.assertEqual(wrong_parent.status_code, 404)
            self.assertEqual(wrong_parent.get_json()['error']['code'], 404)

    def test_list_search_and_sort(self):
        from flask import template_rendered
        contexts = []
        def capture(sender, template, context, **extra):
            contexts.append(context)
        template_rendered.connect(capture, self.app)
        self.addCleanup(template_rendered.disconnect, capture, self.app)
        first = self.create_project('Zulu')
        self.create_project('Alpha')
        response = self.client.get('/?sort=name')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row['name'] for row in contexts[-1]['projects']], ['Alpha', 'Zulu'])
        self.client.get('/?q=ZUL&sort=name_desc')
        self.assertEqual([row['name'] for row in contexts[-1]['projects']], ['Zulu'])
        self.client.get('/?q=%25')
        self.assertEqual(contexts[-1]['projects'], [])
        self.client.get('/?sort=invalid')
        self.assertEqual(contexts[-1]['selected_sort'], 'newest')
        for title, priority in [('Beta', 'High'), ('Alpha', 'Low')]:
            self.post(first + '/raid/new', kind='Risk', title=title, description='Delivery', owner='Sam', status='Open', priority=priority)
            self.post(first + '/changelog/new', title=title, body='Milestone')
        response = self.client.get(first + '?raid_sort=priority&change_q=beta')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row['priority'] for row in contexts[-1]['items']], ['High', 'Low'])
        self.assertEqual([row['title'] for row in contexts[-1]['changes']], ['Beta'])
        for query in ('sam', 'delivery', 'risk', 'open'):
            self.client.get(first, query_string={'raid_q': query, 'raid_sort': 'title', 'change_q': 'milestone'})
            self.assertEqual([row['title'] for row in contexts[-1]['items']], ['Alpha', 'Beta'])
            self.assertEqual(len(contexts[-1]['changes']), 2)
        response = self.client.get(first + '?raid_q=missing&change_q=missing')
        self.assertIn(b'No matching RAID records', response.data)
        self.assertIn(b'No matching changelog entries', response.data)
        self.assertEqual(contexts[-1]['raid_total'], 2)

    def test_project_api_includes_only_its_children(self):
        first = self.create_project('First')
        second = self.create_project('Second')
        empty = self.client.get('/api' + second).get_json()['project']
        self.assertEqual(empty['raid_items'], [])
        self.assertEqual(empty['changelog_entries'], [])
        for project in (first, second):
            for title in ('Earlier', 'Later'):
                self.post(project + '/raid/new', kind='Risk', title=title, status='Open', priority='High')
                self.post(project + '/changelog/new', title=title)
        for project in (first, second):
            result = self.client.get('/api' + project).get_json()['project']
            for collection in ('raid_items', 'changelog_entries'):
                self.assertEqual([item['title'] for item in result[collection]], ['Later', 'Earlier'])
                for item in result[collection]:
                    self.assertEqual(item['project_id'], result['id'])
                    self.assertTrue(item['created_at'].endswith('Z'))

    def test_json_api_errors_and_read_only_methods(self):
        for path in ('/api/missing', '/api/projects/999', '/api/projects/999/raid', '/api/projects/999/changelog'):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.get_json()['error']['code'], 404)
        for method in ('put', 'patch', 'delete'):
            response = getattr(self.client, method)('/api/projects')
            self.assertEqual(response.status_code, 405)
            self.assertEqual(response.get_json()['error']['code'], 405)
            self.assertIn('GET', response.headers['Allow'])

    def test_swagger_documentation_matches_api(self):
        response = self.client.get('/api/openapi.json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_json)
        spec = response.get_json()
        response.close()
        self.assertEqual(spec['openapi'], '3.0.3')
        routes = {re.sub(r'<int:(\w+)>', r'{\1}', rule.rule)
                  for rule in self.app.url_map.iter_rules()
                  if rule.rule.startswith('/api/projects')}
        self.assertEqual(set(spec['paths']), routes)
        project = self.create_project('Documentation test')
        self.post(project + '/raid/new', kind='Risk', title='Schedule', status='Open', priority='High')
        self.post(project + '/changelog/new', title='Started')
        for path, operations in spec['paths'].items():
            url = path.replace('{project_id}', project.rsplit('/', 1)[-1]).replace('{item_id}', '1').replace('{entry_id}', '1')
            result = self.client.get(url)
            self.assertEqual(result.status_code, 200)
            payload = result.get_json()
            schema = operations['get']['responses']['200']['content']['application/json']['schema']
            self.assertEqual(set(schema['required']), set(payload))
            for key, wrapper in schema['properties'].items():
                records = payload[key] if wrapper.get('type') == 'array' else [payload[key]]
                reference = wrapper['items'] if wrapper.get('type') == 'array' else wrapper
                fields = spec['components']['schemas'][reference['$ref'].rsplit('/', 1)[-1]]
                for record in records:
                    self.assertEqual(set(fields['required']), set(record))
                    for field, definition in fields['properties'].items():
                        if 'enum' in definition:
                            self.assertIn(record[field], definition['enum'])
        docs = self.client.get('/api/docs')
        self.assertEqual(docs.status_code, 200)
        self.assertIn(b'SwaggerUIBundle', docs.data)
        self.assertIn(b'/api/openapi.json', docs.data)


if __name__ == '__main__':
    unittest.main()
