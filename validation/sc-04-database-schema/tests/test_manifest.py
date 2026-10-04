from __future__ import annotations

import re
import unittest

from schema_contract import ROOT_TABLE_NAMES, metadata
from schema_manifest import QUERY_IDS, ROOTS, VALIDATION_ONLY


class SchemaManifestTests(unittest.TestCase):
    def test_root_manifest_is_complete_and_unique(self) -> None:
        self.assertTrue(VALIDATION_ONLY)
        self.assertEqual(65, len(ROOTS))
        self.assertEqual(65, len({item.root_id for item in ROOTS}))
        self.assertEqual(65, len({item.table for item in ROOTS}))
        self.assertEqual({item.table for item in ROOTS}, ROOT_TABLE_NAMES)

    def test_query_catalog_is_complete_and_unique(self) -> None:
        self.assertEqual(20, len(QUERY_IDS))
        self.assertEqual(20, len(set(QUERY_IDS)))

    def test_identifiers_are_portable_and_within_postgresql_limit(self) -> None:
        names: list[str] = []
        for table in metadata.tables.values():
            names.append(table.name)
            names.extend(item.name for item in table.constraints if item.name)
            names.extend(item.name for item in table.indexes if item.name)
        for name in names:
            self.assertRegex(name, re.compile(r"^[a-z][a-z0-9_]*$"))
            self.assertLessEqual(len(name.encode("ascii")), 63)

    def test_forbidden_plaintext_column_names_are_absent(self) -> None:
        forbidden = {"api_key", "private_key", "password_plain", "session_token"}
        columns = {
            column.name.lower()
            for table in metadata.tables.values()
            for column in table.columns
        }
        self.assertFalse(forbidden & columns)


if __name__ == "__main__":
    unittest.main()
