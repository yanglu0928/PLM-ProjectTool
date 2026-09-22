#!/usr/bin/env bash
set -euo pipefail

poc_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
repo_root="$(cd "${poc_root}/../.." && pwd)"
artifact_root="${repo_root}/artifacts/poc-01/debian"
wheelhouse="${artifact_root}/wheelhouse"

mkdir -p "${wheelhouse}"
python3.13 -m pip download --dest "${wheelhouse}" -r "${poc_root}/requirements/all.txt"
python3.13 -m pip download --dest "${wheelhouse}" pip setuptools wheel
(
    cd "${wheelhouse}"
    sha256sum ./* > "${artifact_root}/sha256sums.txt"
)
cp -R "${poc_root}/requirements" "${artifact_root}/requirements"
