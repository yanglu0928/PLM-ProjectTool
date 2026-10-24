from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from package_windows_pg18_candidate import select_files  # noqa: E402
from verify_windows_unified_extract import ALLOWED_KINDS  # noqa: E402


class PgRuntimeCandidateTests(unittest.TestCase):
    def test_minimal_selection_excludes_poc_and_gui(self) -> None:
        with tempfile.TemporaryDirectory(prefix="plm-pg-package-unit-") as temp:
            root = Path(temp)
            pg = root / "pgsql"
            source = root / "pgvector"
            source.mkdir()
            for relative in ("bin/pg_config.exe", "lib/vector.dll", "share/extension/vector.control",
                             "doc/index.html", "pgAdmin 4/admin.exe", "data/PG_VERSION",
                             "server_license.txt", "commandlinetools_3rd_party_licenses.txt"):
                path = pg / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"fixture")
            (source / "LICENSE").write_bytes(b"fixture")
            digest = hashlib.sha256(b"fixture").hexdigest()
            with patch("package_windows_pg18_candidate.RUNTIME_FILES", {"server_license.txt": digest}), \
                    patch("package_windows_pg18_candidate.CLI_LICENSE_SHA256", digest), \
                    patch("package_windows_pg18_candidate.PGVECTOR_LICENSE_SHA256", digest):
                names = [name for _, name in select_files(pg, source)]
            self.assertEqual(len(names), 6)
            self.assertFalse(any("doc/" in name or "pgAdmin" in name or "data/" in name for name in names))
            self.assertIn("payload/third-party-licenses/pgvector/LICENSE", names)

    def test_private_runtime_file_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="plm-pg-package-unit-") as temp:
            root = Path(temp)
            for name in ("bin", "lib", "share"):
                (root / name).mkdir()
            (root / "bin" / "secrets.key").write_text("synthetic", encoding="ascii")
            with self.assertRaisesRegex(ValueError, "private or cache"):
                select_files(root, root)

    def test_explicit_pg_kind_is_verifiable(self) -> None:
        self.assertIn("WINDOWS_PG18_PGVECTOR_RUNTIME_NON_RELEASE", ALLOWED_KINDS)


if __name__ == "__main__":
    unittest.main()
