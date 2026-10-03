"""Datenschutz- und Integritätsgrenzen ohne echte sensible Testdaten."""
from __future__ import annotations

import os
import io
import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from medizinanders import gates, pipeline
from medizinanders.demo import artifact_fixture, fixture_contents, write_role_fixture
from medizinanders.storage import (Blocked, atomic_json, data_root, digest,
                                  project_path, read_json, repo_root)


class DataSecurityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ma-security-demo-")
        self.env = patch.dict(os.environ, {"MA_DATA_DIR": self.tmp.name})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_data_root_cannot_be_repository_or_nested_folder(self):
        repo = repo_root()
        for candidate in (repo, repo / "projects", repo / "nested/production"):
            with self.subTest(path=candidate), patch.dict(os.environ, {"MA_DATA_DIR": str(candidate)}):
                with self.assertRaises(Blocked):
                    data_root()

    def test_project_id_cannot_escape_local_root(self):
        for pid in ("../../outside", "/tmp/private", "MA-20261003-001/../..", "MA-20261003-1", "ma-20261003-001"):
            with self.subTest(pid=pid), self.assertRaises(Blocked):
                project_path(pid)

    def test_production_rejects_demo_content_even_if_flag_was_forged(self):
        root, state = pipeline.new_project("Eine wirkliche Themenidee")
        artifact = artifact_fixture("A01", state["projekt_id"], fixture_contents("a" * 64)["A01"])
        artifact["beispiel"] = False
        with self.assertRaises(Blocked):
            pipeline.put_artifact(root, state, artifact)
        self.assertEqual(state["artifacts"], {})

    def test_demo_helper_cannot_write_into_production_project(self):
        root, state = pipeline.new_project("Eine wirkliche Themenidee")
        result = pipeline.dispatch(root, state, "gamma")
        job = state["jobs"][result["job_id"]]
        with self.assertRaises(Blocked):
            write_role_fixture(root, state, job)
        self.assertFalse((Path(result["job_path"]) / "output/A01.json").exists())

    def test_demo_g0_cannot_enable_production(self):
        demo_root, demo = pipeline.new_project("DEMO", beispiel=True)
        gates.approve(demo_root, demo, "G0", "DEMO Operator", demo_simulate=True)
        root, production = pipeline.new_project("Ein echtes Thema")
        self.assertTrue(gates.operating_valid(demo))
        self.assertFalse(gates.operating_valid(production))
        self.assertFalse((Path(self.tmp.name) / "G0.json").exists())

    def test_verified_source_cannot_point_outside_worker_output(self):
        root, state = pipeline.new_project("DEMO", beispiel=True)
        gamma = pipeline.dispatch(root, state, "gamma")
        job = state["jobs"][gamma["job_id"]]
        write_role_fixture(root, state, job)
        pipeline.complete_job(root, state, job["job_id"])
        research = pipeline.dispatch(root, state, "research")
        job = state["jobs"][research["job_id"]]
        write_role_fixture(root, state, job)
        external = Path(self.tmp.name) / "outside-demo-source.txt"
        external.write_text("DEMO: kein Geheimnis, außerhalb des erlaubten Workeroutputs", encoding="utf-8")
        path = Path(research["job_path"]) / "output/A02.json"
        artifact = read_json(path)
        artifact["inhalt"]["originalquellen"][0].update(lokaler_pfad=str(external), sha256=digest(external))
        atomic_json(path, artifact)
        with self.assertRaises(Blocked):
            pipeline.complete_job(root, state, job["job_id"])
        self.assertNotIn("A02", state["artifacts"])

    def test_verified_source_symlink_cannot_escape_worker_output(self):
        root, state = pipeline.new_project("DEMO", beispiel=True)
        gamma = pipeline.dispatch(root, state, "gamma")
        job = state["jobs"][gamma["job_id"]]
        write_role_fixture(root, state, job)
        pipeline.complete_job(root, state, job["job_id"])
        research = pipeline.dispatch(root, state, "research")
        job = state["jobs"][research["job_id"]]
        write_role_fixture(root, state, job)
        external = Path(self.tmp.name) / "external-demo.txt"
        external.write_text("DEMO: außerhalb liegende Textdatei", encoding="utf-8")
        output = Path(research["job_path"]) / "output"
        symlink = output / "sources/escape.txt"
        symlink.symlink_to(external)
        path = output / "A02.json"
        artifact = read_json(path)
        artifact["inhalt"]["originalquellen"][0].update(lokaler_pfad="sources/escape.txt", sha256=digest(external))
        atomic_json(path, artifact)
        with self.assertRaises(Blocked):
            pipeline.complete_job(root, state, job["job_id"])

    def test_review_cannot_be_simulated_for_production(self):
        root, state = pipeline.new_project("Echte Themenidee")
        with self.assertRaises(Blocked):
            gates.record_review(root, state, "medical", name="DEMO", qualification="DEMO",
                                evidence="DEMO", checklist={c: True for c in gates.CHECKLISTS["medical"]},
                                demo_simulate=True)

    def test_production_paths_have_private_directory_permissions(self):
        root, _ = pipeline.new_project("Echte Themenidee")
        self.assertEqual(root.stat().st_mode & 0o777, 0o700)
        self.assertEqual((root / "sources").stat().st_mode & 0o777, 0o700)
        self.assertEqual((root / "review").stat().st_mode & 0o777, 0o700)

    def test_gitignore_excludes_sensitive_and_media_paths(self):
        isolated = Path(self.tmp.name) / "ignore-contract"
        isolated.mkdir()
        (isolated / ".gitignore").write_bytes((repo_root() / ".gitignore").read_bytes())
        subprocess.run(["git", "init", "--quiet", str(isolated)], check=True, capture_output=True)
        paths = [".env", ".env.production", "credentials.json", "cookies.txt", "tokens.json",
                 "projects/MA-20261003-001/state.json", "sources/original.pdf", "private/patient.json",
                 "preview.mp4", "audio.wav", "recording.mov", "browser-profiles/Profile1/Cookies"]
        result = subprocess.run(["git", "check-ignore", "--no-index", "--stdin"], cwd=isolated,
                                input="\n".join(paths) + "\n", capture_output=True, text=True, check=False)
        ignored = set(result.stdout.splitlines())
        self.assertEqual(ignored, set(paths), "Sensible Produktions-/Credential-/Medienpfade müssen ignoriert sein")

    def test_no_openai_api_dependency_or_upload_client(self):
        pyproject = (repo_root() / "pyproject.toml").read_text(encoding="utf-8")
        self.assertNotIn('"openai', pyproject)
        self.assertNotIn("google-api-python-client", pyproject)
        sources = "\n".join(p.read_text(encoding="utf-8") for p in (repo_root() / "src/medizinanders").glob("*.py"))
        self.assertNotIn("videos().insert", sources)
        self.assertNotIn("upload_to_youtube(", sources)

    def test_operator_config_keeps_g0_placeholders_blocked(self):
        target = Path(self.tmp.name) / "operator.yaml"
        target.write_bytes((repo_root() / "config/operator.example.yaml").read_bytes())
        with self.assertRaises(Blocked):
            gates.operator_config()
        _, production = pipeline.new_project("Echte Themenidee")
        self.assertFalse(gates.operating_valid(production))

    def test_real_approval_review_upload_and_publication_require_operator_terminal(self):
        from medizinanders import cli
        root, state = pipeline.new_project("Echte Themenidee")
        commands = [["approve", "G0"], ["approve", "G1", "--project", state["projekt_id"]],
                    ["review-record", state["projekt_id"], "--kind", "medical"],
                    ["youtube-record", state["projekt_id"]], ["published", state["projekt_id"]]]
        for command in commands:
            with self.subTest(command=command), patch("sys.stdin.isatty", return_value=False):
                buffer = io.StringIO()
                with redirect_stdout(buffer):
                    code = cli.main(command)
                self.assertEqual(code, 2)
                self.assertIn("interaktives Operator-Terminal", buffer.getvalue())
        saved = read_json(root / "state.json")
        self.assertEqual(saved["gates"], {})
        self.assertEqual(saved["reviews"], {})
        self.assertNotIn("A11", saved["artifacts"])

    def test_operator_confirmation_requires_exact_binding_token(self):
        from medizinanders.cli import confirm
        with patch("medizinanders.cli.ask", side_effect=["DEMO Operator", "FREIGABE G1 wrong"]), redirect_stdout(io.StringIO()):
            with self.assertRaises(Blocked):
                confirm("G1", {"artifacts": [], "policy": "DEMO"})

    def test_absolute_source_id_is_rejected_before_any_copy_or_destination_write(self):
        root, state = pipeline.new_project("DEMO", beispiel=True)
        gamma = pipeline.dispatch(root, state, "gamma")
        job = state["jobs"][gamma["job_id"]]
        write_role_fixture(root, state, job)
        pipeline.complete_job(root, state, job["job_id"])
        research = pipeline.dispatch(root, state, "research")
        job = state["jobs"][research["job_id"]]
        write_role_fixture(root, state, job)
        output = Path(research["job_path"]) / "output/A02.json"
        artifact = read_json(output)
        outside_destination = Path(self.tmp.name) / "DEMO-escaped-source"
        artifact["inhalt"]["originalquellen"][0]["quelle_id"] = str(outside_destination)
        atomic_json(output, artifact)
        before = copy.deepcopy(state)
        with patch("medizinanders.pipeline.shutil.copyfile", wraps=shutil.copyfile) as copier:
            with self.assertRaises(Blocked):
                pipeline.complete_job(root, state, job["job_id"])
        copier.assert_not_called()
        self.assertFalse(outside_destination.exists())
        self.assertEqual(state, before)
        self.assertFalse(any(p.is_file() for p in (root / "sources").rglob("*")))

    def test_projects_symlink_cannot_escape_data_root_on_project_creation_or_lookup(self):
        outside = tempfile.TemporaryDirectory(prefix="ma-outside-demo-")
        self.addCleanup(outside.cleanup)
        target = Path(outside.name)
        (Path(self.tmp.name) / "projects").symlink_to(target, target_is_directory=True)
        with self.assertRaises(Blocked):
            pipeline.new_project("DEMO", beispiel=True)
        self.assertEqual(list(target.iterdir()), [])
        pid = "MA-20261003-001"
        (target / pid).mkdir()
        # Deliberately outside the application datastore: independent fixture IO.
        (target / pid / "state.json").write_text(json.dumps({"beispiel": True, "DEMO": "outside dummy state"}), encoding="utf-8")
        with self.assertRaises(Blocked):
            project_path(pid)

    def test_projects_symlink_cannot_send_production_files_into_repository(self):
        (Path(self.tmp.name) / "projects").symlink_to(repo_root(), target_is_directory=True)
        with patch("medizinanders.pipeline.atomic_json") as writer:
            with self.assertRaises(Blocked):
                pipeline.new_project("DEMO", beispiel=True)
        writer.assert_not_called()

    def test_free_api_and_cli_imports_of_a07_to_a12_are_blocked(self):
        from medizinanders import cli
        root, state = pipeline.new_project("DEMO", beispiel=True)
        before = copy.deepcopy(state)
        for number in range(7, 13):
            aid = f"A{number:02d}"
            artifact = read_json(repo_root() / "templates" / f"{aid}.json")
            artifact.update(projekt_id=state["projekt_id"], beispiel=True)
            with self.subTest(aid=aid), self.assertRaises(Blocked):
                pipeline.put_artifact(root, state, artifact)
            source = Path(self.tmp.name) / f"DEMO-{aid}.json"
            atomic_json(source, artifact)
            capture = io.StringIO()
            with redirect_stdout(capture):
                result = cli.main(["import", state["projekt_id"], "--file", str(source)])
            self.assertEqual(result, 2)
            self.assertIn("A01–A06", capture.getvalue())
            self.assertEqual(state, before)
            self.assertEqual(read_json(root / "state.json"), before)
            self.assertFalse((root / "artifacts" / aid).exists())


class ProjectStorageSymlinkSecurityTests(unittest.TestCase):
    """Lokale DEMO-Fixtures: kein umgeleiteter Produktionsschritt darf schreiben."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ma-path-demo-")
        self.outside = tempfile.TemporaryDirectory(prefix="ma-outside-path-demo-")
        self.addCleanup(self.outside.cleanup)
        self.addCleanup(self.tmp.cleanup)
        self.env = patch.dict(os.environ, {"MA_DATA_DIR": self.tmp.name})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.data = Path(self.tmp.name)
        self.target = Path(self.outside.name)

    def project(self, *, editorial=False, qa=False):
        root, state = pipeline.new_project("DEMO: synthetic path-safety fixture", beispiel=True)
        if editorial:
            for role, outputs in (("gamma", ["A01"]), ("research", ["A02"]),
                                  ("alpha", ["A03"]), ("beta", ["A04", "A05", "A06"])):
                result = pipeline.dispatch(root, state, role)
                job = state["jobs"][result["job_id"]]
                write_role_fixture(root, state, job)
                pipeline.complete_job(root, state, job["job_id"])
                pipeline.stage_candidates(root, state, outputs)
        if qa:
            result = pipeline.dispatch(root, state, "qa-red-team")
            job = state["jobs"][result["job_id"]]
            write_role_fixture(root, state, job)
            pipeline.complete_job(root, state, job["job_id"])
        return root, state

    def redirect(self, root, folder):
        existing = root / folder
        shutil.rmtree(existing)
        existing.symlink_to(self.target, target_is_directory=True)

    def assert_blocked_without_write(self, action, state):
        before = copy.deepcopy(state)
        with self.assertRaises(Blocked):
            action()
        self.assertEqual(state, before)
        self.assertEqual(list(self.target.iterdir()), [], "Kein umgeleitetes Ziel darf neue Dateien erhalten")

    def test_jobs_symlink_is_rejected_before_worker_files_are_created(self):
        root, state = self.project()
        self.redirect(root, "jobs")
        self.assert_blocked_without_write(lambda: pipeline.dispatch(root, state, "gamma"), state)

    def test_review_symlink_is_rejected_before_packet_generation(self):
        from medizinanders.handoffs import review_packets
        root, state = self.project(editorial=True)
        self.redirect(root, "review")
        self.assert_blocked_without_write(lambda: review_packets(root, state), state)

    def test_freeze_symlink_is_rejected_before_snapshot_copy(self):
        from medizinanders.validation import preflight
        root, state = self.project(editorial=True, qa=True)
        report = preflight(root, state)
        self.redirect(root, "freeze")
        self.assert_blocked_without_write(lambda: pipeline.freeze(root, state, report), state)

    def test_handoff_symlink_is_rejected_before_invideo_files(self):
        from medizinanders.handoffs import invideo_handoff
        root, state = self.project(editorial=True)
        self.redirect(root, "handoff")
        self.assert_blocked_without_write(lambda: invideo_handoff(root, state), state)

    def test_qa_symlink_is_rejected_before_media_inspector_starts(self):
        root, state = self.project()
        preview = root / "08_produktion/inbox/preview.mp4"
        preview.write_bytes(b"DEMO: synthetic non-video payload, never rendered")
        self.redirect(root, "10_qa")
        with patch("medizinanders.media.inspect_video") as inspector:
            self.assert_blocked_without_write(lambda: pipeline.process_preview(root, state, preview), state)
        inspector.assert_not_called()

    def test_analytics_symlink_is_rejected_before_copy_even_with_receipt_testdouble(self):
        from medizinanders.cli import analytics
        root, state = self.project()
        fixture = self.data / "DEMO_analytics.json"
        fixture.write_text('{"beispiel": true, "DEMO": "synthetic input, no channel metrics"}', encoding="utf-8")
        self.redirect(root, "12_analytics")
        with patch("medizinanders.pipeline.publication_valid", return_value=True), \
             patch("medizinanders.cli.shutil.copyfile", wraps=shutil.copyfile) as copier:
            self.assert_blocked_without_write(lambda: analytics(root, state, fixture), state)
        copier.assert_not_called()

    def test_project_lookup_rejects_redirected_and_nested_unknown_symlinks(self):
        for folder in ("jobs", "review", "freeze", "handoff", "10_qa", "12_analytics"):
            root, state = self.project()
            self.redirect(root, folder)
            with self.subTest(folder=folder), self.assertRaises(Blocked):
                project_path(state["projekt_id"])
        root, state = self.project()
        nested = root / "DEMO_extra/subdir"
        nested.mkdir(parents=True)
        (nested / "redirect").symlink_to(self.target, target_is_directory=True)
        with self.assertRaises(Blocked):
            project_path(state["projekt_id"])
        self.assertEqual(list(self.target.iterdir()), [])

    def test_storage_writers_and_lock_reject_file_symlinks_and_preserve_outside_bytes(self):
        from medizinanders.storage import lock, write_text
        operations = {"text": lambda p: write_text(p, "DEMO new content"),
                      "json": lambda p: atomic_json(p, {"DEMO": "new content"}),
                      "json-exclusive": lambda p: atomic_json(p, {"DEMO": "new content"}, exclusive=True)}
        for name, action in operations.items():
            outside = self.target / (name + ".txt")
            outside.write_text("DEMO outside sentinel", encoding="utf-8")
            link = self.data / (name + ".txt")
            link.symlink_to(outside)
            with self.subTest(operation=name), self.assertRaises(Blocked):
                action(link)
            self.assertEqual(outside.read_text(encoding="utf-8"), "DEMO outside sentinel")
        outside = self.target / "lock.txt"
        outside.write_text("DEMO outside lock sentinel", encoding="utf-8")
        link = self.data / "DEMO.lock"
        link.symlink_to(outside)
        with self.assertRaises(Blocked):
            with lock(link):
                self.fail("Ein umgeleiteter Lock darf nicht erworben werden")
        self.assertEqual(outside.read_text(encoding="utf-8"), "DEMO outside lock sentinel")

    def test_storage_writers_reject_redirected_parent_directory(self):
        from medizinanders.storage import lock, write_text
        directory = self.data / "DEMO_redirect"
        directory.symlink_to(self.target, target_is_directory=True)
        for action in (lambda: write_text(directory / "text.txt", "DEMO"),
                       lambda: atomic_json(directory / "data.json", {"DEMO": True})):
            with self.subTest(action=action), self.assertRaises(Blocked):
                action()
        with self.assertRaises(Blocked):
            with lock(directory / "DEMO.lock"):
                self.fail("Ein umgeleiteter Lock darf nicht erworben werden")
        self.assertEqual(list(self.target.iterdir()), [])

    def test_jobs_symlink_into_repository_stub_is_rejected_before_copying_prompts(self):
        root, state = self.project()
        repo_stub = self.target / "DEMO_REPOSITORY_STUB"
        repo_stub.mkdir()
        shutil.rmtree(root / "jobs")
        (root / "jobs").symlink_to(repo_stub, target_is_directory=True)
        before = copy.deepcopy(state)
        with patch.dict(os.environ, {"MA_REPO_DIR": str(repo_stub)}), self.assertRaises(Blocked):
            pipeline.dispatch(root, state, "gamma")
        self.assertEqual(state, before)
        self.assertEqual(list(repo_stub.iterdir()), [])

    def test_operator_and_g0_file_symlinks_are_never_written(self):
        from medizinanders.storage import lock, write_text
        for name in ("operator.yaml", "G0.json", ".operator.lock"):
            outside = self.target / (name + ".DEMO")
            outside.write_text("DEMO outside operator sentinel", encoding="utf-8")
            path = self.data / name
            path.symlink_to(outside)
            with self.subTest(path=name), self.assertRaises(Blocked):
                if name == "operator.yaml":
                    write_text(path, "DEMO: rewritten operator")
                elif name == "G0.json":
                    atomic_json(path, {"DEMO": "no real authorization"})
                else:
                    with lock(path):
                        self.fail("Ein umgeleiteter Operator-Lock darf nicht erworben werden")
            self.assertEqual(outside.read_text(encoding="utf-8"), "DEMO outside operator sentinel")


class RepositoryHistorySecurityTests(unittest.TestCase):
    """Erreichbare Git-Historie bleibt prüfpflichtig nach einer Index-Löschung.

    Alle Commits entstehen ausschließlich in einem temporären DEMO-Repository.
    Token-Muster werden erst zur Laufzeit synthetisch zusammengesetzt; es gibt
    keine echten Zugangsdaten und keine Verbindung zu einem Remote.
    """
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ma-history-demo-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        scripts = self.root / "scripts"
        scripts.mkdir()
        self.checker = scripts / "check_repository.py"
        shutil.copyfile(repo_root() / "scripts/check_repository.py", self.checker)
        (self.root / "README.md").write_text("DEMO: synthetisches Git-Repository für Historienprüfungen.\n", encoding="utf-8")
        self.git("init", "--quiet")
        self.git("add", "--", "README.md", "scripts/check_repository.py")
        self.git("commit", "--quiet", "-m", "DEMO clean history fixture")

    def git(self, *args):
        return subprocess.run(["git", "-c", "user.name=DEMO History Test", "-c", "user.email=demo@example.invalid",
                               "-c", "commit.gpgsign=false", *args], cwd=self.root,
                              capture_output=True, text=True, check=True)

    def audit(self, *args):
        return subprocess.run([sys.executable, str(self.checker), *args], cwd=self.root,
                              capture_output=True, text=True, check=False, timeout=20)

    def assert_index_clean_and_history_blocked(self, filename):
        for args in ((), ("--staged",)):
            with self.subTest(index_args=args):
                result = self.audit(*args)
                self.assertEqual(result.returncode, 0)
                self.assertIn("Repository-Prüfung: OK", result.stdout)
        history = self.audit("--history")
        self.assertEqual(history.returncode, 1)
        self.assertIn("Repository-Prüfung: BLOCKED", history.stdout)
        self.assertIn(filename, history.stdout)
        return history

    def test_forbidden_operator_in_history_blocks_push_after_only_staged_deletion(self):
        filename = "operator.yaml"
        (self.root / filename).write_text("beispiel: true\nverantwortliche_person: DEMO-SIMULATION\n", encoding="utf-8")
        self.git("add", "--", filename)
        self.git("commit", "--quiet", "-m", "DEMO forbidden operator path fixture")
        self.git("rm", "--quiet", "--", filename)
        # Die Entfernung wird absichtlich nicht committed: nur der Index ist sauber.
        result = self.assert_index_clean_and_history_blocked(filename)
        self.assertNotIn("verantwortliche_person:", result.stdout)

    def test_synthetic_token_pattern_in_history_is_blocked_without_printing_content(self):
        filename = "DEMO_TOKEN_PATTERN.txt"
        synthetic_pattern = ("gh" + "p" + "_" + ("D" * 40)).encode("ascii")
        (self.root / filename).write_bytes(b"DEMO synthetic nonfunctional pattern fixture\n" + synthetic_pattern + b"\n")
        self.git("add", "--", filename)
        self.git("commit", "--quiet", "-m", "DEMO synthetic pattern fixture")
        self.git("rm", "--quiet", "--", filename)
        result = self.assert_index_clean_and_history_blocked(filename)
        self.assertFalse(synthetic_pattern.decode("ascii") in result.stdout,
                         "Die Historienprüfung darf gefundenen Token-Mustertext nicht ausgeben.")
        self.assertFalse(synthetic_pattern.decode("ascii") in result.stderr,
                         "Auch stderr darf gefundenen Token-Mustertext nicht enthalten.")

    def test_clean_reachable_history_and_index_both_pass(self):
        (self.root / "RULES.md").write_text("DEMO: ausschließlich synthetische Regeln, keine Produktionsdaten.\n", encoding="utf-8")
        self.git("add", "--", "RULES.md")
        self.git("commit", "--quiet", "-m", "DEMO second clean fixture commit")
        for args in ((), ("--staged",), ("--history",)):
            with self.subTest(args=args):
                result = self.audit(*args)
                self.assertEqual(result.returncode, 0)
                self.assertIn("Repository-Prüfung: OK", result.stdout)
                self.assertNotIn("BLOCKED", result.stdout)


if __name__ == "__main__":
    unittest.main()
