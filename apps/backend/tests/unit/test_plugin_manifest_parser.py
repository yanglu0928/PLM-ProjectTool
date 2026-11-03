from __future__ import annotations

import json
import unittest

from plm_assistant.modules.plugin.application.manifest_parser import (
    MAX_MANIFEST_BYTES,
    PluginManifestError,
    PluginManifestParser,
)


def valid_manifest() -> dict[str, object]:
    return {
        "schema_version": "plm.plugin.manifest.v1",
        "plugin_id": "com.example.document",
        "name": "Synthetic document plugin",
        "version": "1.2.3",
        "plugin_api_version": "1.0.0",
        "supported_os": ["windows-11", "windows-server-2025"],
        "architecture": "x86_64",
        "entry_point": "src/plugin.py",
        "operations": [
            {"operation_id": "document.render", "output_types": ["DOCX", "PDF"]}
        ],
        "dependencies": [
            {"name": "renderer", "version_spec": ">=1,<2", "kind": "PYTHON"}
        ],
    }


def encode(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


class PluginManifestParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = PluginManifestParser()

    def reject(self, manifest: object, code: str = "PLUGIN_INVALID_MANIFEST") -> None:
        with self.assertRaises(PluginManifestError) as caught:
            self.parser.parse(manifest)  # type: ignore[arg-type]
        self.assertEqual(caught.exception.code, code)

    def test_valid_manifest_returns_immutable_projection_and_stable_hash(self) -> None:
        manifest = valid_manifest()
        parsed = self.parser.parse(encode(manifest))
        self.assertEqual(parsed.plugin_id, "com.example.document")
        self.assertEqual(parsed.entry_point, "src/plugin.py")
        self.assertEqual(parsed.operations[0].operation_id, "document.render")
        self.assertEqual(parsed.operations[0].output_types, ("DOCX", "PDF"))
        self.assertEqual(parsed.dependencies[0].kind, "PYTHON")
        reordered = dict(reversed(list(manifest.items())))
        parsed_again = self.parser.parse(encode(reordered))
        self.assertEqual(parsed.canonical_sha256, parsed_again.canonical_sha256)
        with self.assertRaises(Exception):
            parsed.operations += ()  # frozen dataclass

    def test_unknown_missing_and_future_schema_fields_are_rejected(self) -> None:
        manifest = valid_manifest()
        manifest["unreviewed_permission"] = ["filesystem"]
        self.reject(manifest)
        manifest = valid_manifest()
        del manifest["entry_point"]
        self.reject(manifest)
        manifest = valid_manifest()
        manifest["schema_version"] = "plm.plugin.manifest.v2"
        self.reject(manifest)

    def test_duplicate_json_keys_invalid_utf8_and_non_finite_numbers_are_rejected(self) -> None:
        duplicate = (
            b'{"schema_version":"plm.plugin.manifest.v1",'
            b'"schema_version":"plm.plugin.manifest.v1"}'
        )
        self.reject(duplicate)
        self.reject(b"\xff")
        self.reject(b'{"value":NaN}')
        manifest = valid_manifest()
        manifest["unexpected_float"] = 1.5
        self.reject(manifest)

    def test_bounds_and_recursively_nested_payload_are_enforced(self) -> None:
        self.reject(b"")
        self.reject(b"x" * (MAX_MANIFEST_BYTES + 1))
        deep: object = "x"
        for _ in range(18):
            deep = {"child": deep}
        self.reject(deep)

    def test_plugin_identity_versions_targets_and_architecture_are_strict(self) -> None:
        for field, value in (
            ("plugin_id", "Com.Example"),
            ("plugin_id", "x"),
            ("version", "v1"),
            ("plugin_api_version", "latest"),
            ("supported_os", ["macos-arm64"]),
            ("supported_os", []),
            ("supported_os", ["windows-11", "windows-11"]),
            ("architecture", "arm64"),
        ):
            manifest = valid_manifest()
            manifest[field] = value
            self.reject(manifest)

    def test_entry_point_rejects_absolute_drive_unc_traversal_and_ambiguous_paths(self) -> None:
        for path in (
            "",
            "/etc/plugin.py",
            "../plugin.py",
            "src/../plugin.py",
            "src//plugin.py",
            "./plugin.py",
            "C:/plugin.py",
            "C:plugin.py",
            "\\\\server\\plugin.py",
            "src\\plugin.py",
            "src/plugin.py:stream",
            "src/\x00plugin.py",
        ):
            manifest = valid_manifest()
            manifest["entry_point"] = path
            self.reject(manifest, "PLUGIN_INVALID_ENTRY_POINT")

    def test_operation_shape_uniqueness_and_output_types_are_checked(self) -> None:
        cases = [
            [],
            [{"operation_id": "render", "output_types": []}],
            [{"operation_id": "bad op", "output_types": ["PDF"]}],
            [
                {"operation_id": "render", "output_types": ["PDF"]},
                {"operation_id": "render", "output_types": ["DOCX"]},
            ],
            [{"operation_id": "render", "output_types": ["PDF", "PDF"]}],
            [{"operation_id": "render", "output_types": ["PDF"], "extra": True}],
        ]
        for operations in cases:
            manifest = valid_manifest()
            manifest["operations"] = operations
            self.reject(manifest)

    def test_dependency_shape_unique_name_and_kind_are_checked(self) -> None:
        cases = [
            [{"name": "x", "version_spec": "*", "kind": "NETWORK"}],
            [{"name": "x", "version_spec": " ", "kind": "PYTHON"}],
            [
                {"name": "Renderer", "version_spec": "1", "kind": "PYTHON"},
                {"name": "renderer", "version_spec": "2", "kind": "PYTHON"},
            ],
            [{"name": "x", "version_spec": "1", "kind": "PYTHON", "secret": "no"}],
        ]
        for dependencies in cases:
            manifest = valid_manifest()
            manifest["dependencies"] = dependencies
            self.reject(manifest)

    def test_empty_dependency_list_is_valid_and_json_types_are_strict(self) -> None:
        manifest = valid_manifest()
        manifest["dependencies"] = []
        manifest["name"] = None
        self.reject(manifest)
        manifest = valid_manifest()
        manifest["operations"] = {"operation_id": "render"}
        self.reject(manifest)


if __name__ == "__main__":
    unittest.main()
