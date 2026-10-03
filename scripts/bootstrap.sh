#!/usr/bin/env bash
set -euo pipefail
ma_repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ma_repo_dir"
python3 -m venv .venv
.venv/bin/python -m pip install -e .
git config core.hooksPath scripts/hooks
printf '%s\n' 'Installation abgeschlossen.' 'Aktivieren: source .venv/bin/activate' 'Umgebung prüfen: ma doctor' 'Betrieb einrichten: ma setup' 'Menschlich freigeben: ma approve G0' 'Erste Episode: ma new'
