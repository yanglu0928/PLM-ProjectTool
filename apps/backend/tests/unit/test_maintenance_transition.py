import unittest
import uuid

from sqlalchemy import create_engine

from plm_assistant.modules.platform.infrastructure.maintenance_transition import (
    PostgresMaintenanceTransition,
)


class MaintenanceTransitionInputTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        self.port = PostgresMaintenanceTransition(self.engine)

    def tearDown(self):
        self.engine.dispose()

    def test_rejects_untrusted_input_before_database_access(self):
        operator = uuid.uuid4()
        for kwargs in (
            {"target": "BROKEN", "expected_version": 0, "operator_id": operator},
            {"target": "MAINTENANCE", "expected_version": True, "operator_id": operator},
            {"target": "MAINTENANCE", "expected_version": 0,
             "operator_id": uuid.UUID(int=0)},
            {"target": "MAINTENANCE", "expected_version": 0,
             "operator_id": operator, "wait_ms": 0},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.port.change(**kwargs)

    def test_rejects_wrong_database(self):
        from plm_assistant.modules.platform.infrastructure.maintenance_admission import (
            MaintenanceAdmissionError,
        )
        with self.assertRaises(MaintenanceAdmissionError) as caught:
            self.port.change(target="MAINTENANCE", expected_version=0,
                             operator_id=uuid.uuid4())
        self.assertEqual(caught.exception.code, "MAINTENANCE_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
