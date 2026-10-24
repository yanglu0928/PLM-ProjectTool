"""Maintenance admission refuses unsupported engines and malformed facts."""

import unittest
from datetime import datetime, timezone

from sqlalchemy import create_engine

from plm_assistant.modules.platform.infrastructure.maintenance_admission import (
    MaintenanceAdmissionError, MaintenanceAdmissionSnapshot,
    PostgresMaintenanceAdmission,
)


class MaintenanceAdmissionTests(unittest.TestCase):
    def test_rejects_non_engine_and_non_postgresql(self):
        with self.assertRaises(ValueError):
            PostgresMaintenanceAdmission(object())
        engine = create_engine("sqlite+pysqlite:///:memory:")
        try:
            gate = PostgresMaintenanceAdmission(engine)
            with self.assertRaises(MaintenanceAdmissionError):
                with gate.admit():
                    self.fail("SQLite admitted")
        finally:
            engine.dispose()

    def test_snapshot_requires_aware_timestamp_and_version(self):
        MaintenanceAdmissionSnapshot(0, datetime.now(timezone.utc))
        for version, stamp in ((-1, datetime.now(timezone.utc)),
                               (0, datetime.now())):
            with self.subTest(version=version, stamp=stamp), \
                 self.assertRaises(MaintenanceAdmissionError):
                MaintenanceAdmissionSnapshot(version, stamp)


if __name__ == "__main__":
    unittest.main()
