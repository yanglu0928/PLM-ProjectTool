from concurrent.futures import ThreadPoolExecutor
import unittest
from unittest.mock import patch

from plm_assistant.entrypoints import password_capacity as module


class ProcessPasswordCapacityTests(unittest.TestCase):
    def test_concurrent_factories_share_one_budget_and_conflict_is_closed(self):
        with patch.object(module, '_capacity', None), patch.object(module, '_slots', None):
            with ThreadPoolExecutor(max_workers=20) as pool:
                budgets = list(pool.map(lambda _: module.get_process_password_capacity(slots=4), range(40)))
            self.assertTrue(all(value is budgets[0] for value in budgets))
            for slots in (8, 16, True, 4.0, '4', 0, 17):
                with self.assertRaisesRegex(ValueError, '^AUTH_PASSWORD_CAPACITY_UNAVAILABLE$'):
                    module.get_process_password_capacity(slots=slots)
            self.assertIs(module.get_process_password_capacity(slots=4), budgets[0])
            self.assertEqual(budgets[0].snapshot(), {'slots': 4, 'active': 0, 'peak': 0})

    def test_invalid_first_configuration_does_not_bind(self):
        with patch.object(module, '_capacity', None), patch.object(module, '_slots', None):
            with self.assertRaises(ValueError):
                module.get_process_password_capacity(slots=True)
            self.assertIsNone(module._capacity)
            self.assertEqual(module.get_process_password_capacity(slots=16).snapshot()['slots'], 16)
