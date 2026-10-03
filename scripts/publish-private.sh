#!/usr/bin/env bash
set -euo pipefail
ma_repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ma_repo_dir"
python3 scripts/check_repository.py --history
[[ -z "$(git status --porcelain)" ]] || { printf '%s\n' 'Vor dem Push alle vorgesehenen Änderungen committen; Arbeitsstand ist nicht sauber.'; exit 2; }
command -v gh >/dev/null || { printf '%s\n' 'GitHub CLI installieren: https://cli.github.com/'; exit 2; }
gh auth status >/dev/null 2>&1 || gh auth login
ma_repo_name="medizinanders-codex-pipeline"
ma_login="$(gh api user --jq .login)"
ma_full_name="$ma_login/$ma_repo_name"
if gh api "repos/$ma_full_name" >/dev/null 2>&1; then
  [[ "$(gh api "repos/$ma_full_name" --jq .private)" == true ]] || { printf '%s\n' 'Remote ist nicht privat; Push blockiert.'; exit 2; }
else
  gh repo create "$ma_repo_name" --private --description 'Codex-native Produktionspipeline für MedizinAnders'
fi
ma_remote="https://github.com/$ma_full_name.git"
if git remote get-url origin >/dev/null 2>&1; then
  [[ "$(git remote get-url origin)" == "$ma_remote" ]] || { printf '%s\n' 'Bestehendes origin gehört nicht zum erwarteten Repo; blockiert.'; exit 2; }
else
  git remote add origin "$ma_remote"
fi
gh auth setup-git
git push -u origin main
gh api "repos/$ma_full_name" --jq '{url: .html_url, private: .private}'
