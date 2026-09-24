#!/usr/bin/env bash
set -euo pipefail

poc_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
repo_root="$(cd "${poc_root}/../.." && pwd)"
runtime_root="${repo_root}/.poc-runtime/poc-01/debian-online"
evidence_root="${poc_root}/evidence/debian-13"

mkdir -p "${runtime_root}" "${evidence_root}"
python3.13 -m venv "${runtime_root}"
python_bin="${runtime_root}/bin/python"
"${python_bin}" -m pip install --upgrade pip setuptools wheel 2>&1 | tee "${evidence_root}/bootstrap.txt"
"${python_bin}" -m pip install -r "${poc_root}/requirements/all.txt" 2>&1 | tee "${evidence_root}/install.txt"
"${python_bin}" "${poc_root}/scripts/collect_environment.py" > "${evidence_root}/environment.json"
"${python_bin}" "${poc_root}/scripts/verify_imports.py" | tee "${evidence_root}/verification.json"
