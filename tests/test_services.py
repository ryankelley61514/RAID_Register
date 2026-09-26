import unittest
from unittest.mock import patch

import services


class ServiceTests(unittest.TestCase):
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
        values = services.validate({'title': '  Risk  ', 'kind': 'Risk'}, services.RAID_FIELDS)
        self.assertEqual(values['title'], 'Risk')
        self.assertEqual(values['status'], 'Open')
        self.assertEqual(values['priority'], 'Medium')
        with self.assertRaises(services.ValidationError):
            services.validate({'name': 'Valid', 'id': 1}, services.PROJECT_FIELDS)
        self.assertEqual(services.validate({'description': ''}, services.PROJECT_FIELDS, partial=True), {'description': ''})
