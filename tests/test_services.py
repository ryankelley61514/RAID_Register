import unittest
from unittest.mock import patch

import services
from field_definitions import FIELDS


class ServiceTests(unittest.TestCase):
    @patch('services.db')
    def test_project_details_fetch_parent_once(self, get_db):
        connection = get_db.return_value
        connection.execute.return_value.fetchone.return_value = {'id': 1, 'name': 'Project'}
        connection.execute.return_value.fetchall.return_value = []
        result = services.get_project_details(1)
        self.assertEqual(result['raid_items'], [])
        self.assertEqual(result['changelog_entries'], [])
        self.assertEqual(connection.execute.call_count, 3)
        parent_queries = [call for call in connection.execute.call_args_list
                          if 'FROM projects WHERE' in call.args[0]]
        self.assertEqual(len(parent_queries), 1)

    @patch('services.db')
    def test_failed_write_rolls_back(self, get_db):
        connection = get_db.return_value
        connection.execute.return_value.fetchone.return_value = {'id': 1}
        connection.create_child.side_effect = RuntimeError('write failed')
        with self.assertRaisesRegex(RuntimeError, 'write failed'):
            services.create_child(1, 'raid', {'title': 'Risk', 'kind': 'Risk'})
        connection.rollback.assert_called_once()
        connection.commit.assert_not_called()

    def test_validation_without_http_request(self):
        values = services.validate({'title': '  Risk  ', 'kind': 'Risk'}, FIELDS['raid_items'])
        self.assertEqual(values['title'], 'Risk')
        self.assertEqual(values['status'], 'Open')
        self.assertEqual(values['priority'], 'Medium')
        with self.assertRaises(services.ValidationError):
            services.validate({'name': 'Valid', 'id': 1}, FIELDS['projects'])
        self.assertEqual(services.validate({'description': ''}, FIELDS['projects'], partial=True), {'description': ''})
