#!/usr/bin/env python3
"""Prüft nur Git-Dateien und meldet niemals gefundene Secret-Inhalte."""
import argparse
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECRET_PATTERNS = [
    re.compile(rb"github_pat_[A-Za-z0-9_]{30,}"),
    re.compile(rb"gh[pousr]_[A-Za-z0-9]{30,}"),
    re.compile(rb"sk-(?:proj-)?[A-Za-z0-9_-]{30,}"),
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]
FORBIDDEN_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm", ".wav", ".mp3", ".aac", ".pdf", ".csv", ".xlsx", ".pem", ".key", ".p12", ".db", ".sqlite"}
FORBIDDEN_PARTS = {"projects", "production", "sources", "private", "inbox", "freeze", "handoff", "gates", "jobs", "browser-profiles", ".codex"}


def check(staged=False):
    command = ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"] if staged else ["git", "ls-files", "-z"]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, check=True)
    errors = []
    for entry in result.stdout.split(b"\0"):
        if not entry:
            continue
        relative = entry.decode("utf-8")
        path = Path(relative)
        if path.suffix.lower() in FORBIDDEN_SUFFIXES or set(path.parts) & FORBIDDEN_PARTS or path.name.startswith(".env") or path.name in ("auth.json", "operator.yaml"):
            errors.append((relative, "Nicht versionierbare Produktions-/Secret-Datei"))
            continue
        blob = subprocess.run(["git", "show", ":" + relative], cwd=ROOT, capture_output=True, check=True).stdout
        if len(blob) > 2 * 1024 * 1024:
            errors.append((relative, "Unerwartet große Datei (>2 MiB)"))
        if any(pattern.search(blob) for pattern in SECRET_PATTERNS):
            errors.append((relative, "Secret-Muster gefunden; Inhalt wird nicht ausgegeben"))
    return errors


def check_history():
    """Prüft alle erreichbaren Commits, die im Repository ausgeliefert werden können."""
    revisions = subprocess.run(["git", "rev-list", "--all"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.splitlines()
    errors = []
    checked_blobs = set()
    seen_paths = set()
    for revision in revisions:
        tree = subprocess.run(["git", "ls-tree", "-r", "-z", "--full-tree", revision], cwd=ROOT, capture_output=True, check=True).stdout
        for entry in tree.split(b"\0"):
            if not entry:
                continue
            metadata, filename = entry.split(b"\t", 1)
            mode, kind, sha = metadata.split()
            relative = filename.decode("utf-8")
            path = Path(relative)
            if path.suffix.lower() in FORBIDDEN_SUFFIXES or set(path.parts) & FORBIDDEN_PARTS or path.name.startswith(".env") or path.name in ("auth.json", "operator.yaml") or mode == b"120000":
                if relative not in seen_paths:
                    errors.append((relative, "Nicht zulässige Datei/Symlink in Git-Historie; Push blockiert"))
                    seen_paths.add(relative)
            if kind != b"blob" or sha in checked_blobs:
                continue
            checked_blobs.add(sha)
            blob = subprocess.run(["git", "cat-file", "blob", sha.decode()], cwd=ROOT, capture_output=True, check=True).stdout
            if len(blob) > 2 * 1024 * 1024 or any(pattern.search(blob) for pattern in SECRET_PATTERNS):
                errors.append((relative, "Große Datei/Secret-Muster in Git-Historie; Inhalt wird nicht ausgegeben"))
    return errors


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--staged", action="store_true")
    p.add_argument("--history", action="store_true")
    args = p.parse_args()
    findings = check_history() if args.history else check(args.staged)
    for path, why in findings:
        print(path + ": " + why)
    print("Repository-Prüfung: " + ("BLOCKED" if findings else "OK"))
    raise SystemExit(1 if findings else 0)
