from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from tools.install_windows_current_app_candidate_rehearsal import (
    copy_and_publish,
    mapping_for,
)


def _payload(root: Path) -> tuple[dict[str, str], dict[str, str]]:
    contents = {
        "payload/runtime/python.exe": b"synthetic runtime",
        "payload/frontend/dist/index.html": b"synthetic UI",
    }
    expected: dict[str, str] = {}
    for name, content in contents.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        expected[name] = hashlib.sha256(content).hexdigest()
    return expected, mapping_for(set(expected))


def test_mapping_preserves_payload_tree_under_app() -> None:
    assert mapping_for({"payload/runtime/python.exe"}) == {
        "payload/runtime/python.exe": "app/runtime/python.exe"
    }


def test_mapping_rejects_non_payload_and_casefold_collisions() -> None:
    with pytest.raises(ValueError, match="payload path"):
        mapping_for({"manifest.json"})
    with pytest.raises(ValueError, match="collision"):
        mapping_for({"payload/A.txt", "payload/a.txt"})


def test_atomic_placement_reads_back_hashes_and_never_claims_install(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("tools.install_windows_current_app_candidate_rehearsal.tempfile.gettempdir",
                        lambda: str(tmp_path))
    stage = tmp_path / "stage"
    stage.mkdir()
    expected, mapping = _payload(stage)
    target = tmp_path / "install-synthetic"

    result = copy_and_publish(stage, target, expected, mapping)

    assert result["status"] == "NON_RELEASE_CURRENT_APP_ATOMIC_PLACEMENT_PASS"
    assert result["release_eligible"] is False
    assert result["formal_install_performed"] is False
    assert result["services_changed"] is False
    assert result["database_started"] is False
    assert (target / "app/runtime/python.exe").read_bytes() == b"synthetic runtime"
    assert (target / "app/frontend/dist/index.html").read_bytes() == b"synthetic UI"
    assert all((target / name).is_dir() for name in ("plugins", "data", "logs", "license", "runtime"))


def test_interrupted_copy_only_removes_owned_partial_and_leaves_target_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("tools.install_windows_current_app_candidate_rehearsal.tempfile.gettempdir",
                        lambda: str(tmp_path))
    stage = tmp_path / "stage"
    stage.mkdir()
    expected, mapping = _payload(stage)
    target = tmp_path / "interrupted-install"

    with pytest.raises(RuntimeError, match="interruption"):
        copy_and_publish(stage, target, expected, mapping, fail_after=1)

    assert not target.exists()
    assert not list(tmp_path.glob("plm-current-app-partial-*"))


def test_existing_target_is_preserved_and_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("tools.install_windows_current_app_candidate_rehearsal.tempfile.gettempdir",
                        lambda: str(tmp_path))
    stage = tmp_path / "stage"
    stage.mkdir()
    expected, mapping = _payload(stage)
    target = tmp_path / "existing"
    target.mkdir()
    sentinel = target / "keep.txt"
    sentinel.write_text("preserve", encoding="ascii")

    with pytest.raises(ValueError, match="fresh direct ASCII Temp"):
        copy_and_publish(stage, target, expected, mapping)

    assert sentinel.read_text(encoding="ascii") == "preserve"
