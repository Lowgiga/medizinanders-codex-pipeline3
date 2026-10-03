"""Integration und Negativtests: Sicherheit entsteht durch harte Blocker."""
from __future__ import annotations

import copy
import io
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from contextlib import redirect_stdout
from unittest.mock import patch

from medizinanders import gates, pipeline
from medizinanders.demo import (artifact_fixture, fixture_contents, run_demo,
                               write_role_fixture)
from medizinanders.storage import (Blocked, artifact_path, atomic_json, current,
                                  digest, object_hash, read_json, repo_root)
from medizinanders.validation import (DEPENDENCIES, DISCLAIMER, dependency_check,
                                     preflight, qa_check, schema_check)


class ProjectCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ma-test-demo-")
        self.env = patch.dict(os.environ, {"MA_DATA_DIR": self.tmp.name})
        self.env.start()
        self.root, self.state = pipeline.new_project("DEMO – synthetische Quellenmarkierung", beispiel=True)

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def worker(self, role):
        result = pipeline.dispatch(self.root, self.state, role)
        job = self.state["jobs"][result["job_id"]]
        write_role_fixture(self.root, self.state, job)
        pipeline.complete_job(self.root, self.state, job["job_id"])
        return job

    def a01(self, *, candidate=True):
        gates.approve(self.root, self.state, "G0", "DEMO Operator", demo_simulate=True)
        self.worker("gamma")
        if candidate:
            pipeline.stage_candidates(self.root, self.state, ["A01"])

    def evidence(self, *, approve_g2=False):
        self.a01()
        gates.approve(self.root, self.state, "G1", "DEMO Operator", demo_simulate=True)
        self.worker("research")
        pipeline.stage_candidates(self.root, self.state, ["A02"])
        self.worker("alpha")
        pipeline.stage_candidates(self.root, self.state, ["A03"])
        if approve_g2:
            gates.approve(self.root, self.state, "G2", "DEMO Operator", demo_simulate=True)

    def editorial(self):
        self.evidence(approve_g2=True)
        self.worker("beta")
        pipeline.stage_candidates(self.root, self.state, ["A04", "A05", "A06"])

    def artifact_update(self, aid, mutate):
        artifact = copy.deepcopy(current(self.root, self.state, aid))
        mutate(artifact["inhalt"])
        return pipeline.put_artifact(self.root, self.state, artifact, bind_inputs=True, internal=True)

    def preflight_change(self, aid, mutate):
        """Isolierter Crosscheck eines neu eingereichten Kandidateninhalts.

        Historische Artefaktdateien bleiben unverändert. Hash-/Dependency-
        Manipulation wird separat mit echten Dateien geprüft.
        """
        values = {a: copy.deepcopy(current(self.root, self.state, a)) for a in DEPENDENCIES if a in self.state["artifacts"]}
        mutate(values[aid]["inhalt"])
        with patch("medizinanders.validation.current", side_effect=lambda root, state, a: values[a]):
            return preflight(self.root, self.state)


class SchemaTests(ProjectCase):
    def test_templates_have_all_common_metadata_and_valid_schemas(self):
        from jsonschema import Draft202012Validator, FormatChecker
        common = {"artefakt_id", "projekt_id", "version", "datum", "autor", "status", "eingaben",
                  "quellen", "offene_punkte", "gesperrt", "sperrgrund", "beispiel", "inhalt"}
        for i in range(1, 13):
            with self.subTest(artifact=i):
                schema = read_json(repo_root() / "schemas" / f"A{i:02d}.schema.json")
                Draft202012Validator.check_schema(schema)
                template = read_json(repo_root() / "templates" / f"A{i:02d}.json")
                self.assertTrue(common.issubset(template))
                self.assertTrue(template["beispiel"])
                self.assertEqual(template["status"], "Entwurf")

    def test_valid_demonstration_artifacts_have_exact_required_contract(self):
        contents = fixture_contents("a" * 64)
        for aid, content in contents.items():
            with self.subTest(aid=aid):
                schema_check(artifact_fixture(aid, self.state["projekt_id"], content))
        self.assertEqual(contents["A05"]["wortzahl"], 104)

    def test_empty_required_field_blocks(self):
        artifact = artifact_fixture("A01", self.state["projekt_id"], fixture_contents("a" * 64)["A01"])
        artifact["inhalt"]["kernfrage"] = "  "
        with self.assertRaises(Blocked):
            schema_check(artifact)

    def test_non_exact_status_is_rejected(self):
        artifact = artifact_fixture("A01", self.state["projekt_id"], fixture_contents("a" * 64)["A01"])
        artifact["status"] = "approved"
        with self.assertRaises(Blocked):
            schema_check(artifact)

    def test_blocked_artifact_and_unresolved_points_stop_use(self):
        artifact = artifact_fixture("A01", self.state["projekt_id"], fixture_contents("a" * 64)["A01"])
        artifact.update(gesperrt=True, sperrgrund="DEMO: ungeklärte Voraussetzung")
        with self.assertRaises(Blocked):
            schema_check(artifact)
        artifact.update(gesperrt=False, sperrgrund="", offene_punkte=["DEMO: noch offen"])
        with self.assertRaises(Blocked):
            schema_check(artifact)

    def test_analytics_null_requires_explanation_and_exactly_one_test(self):
        artifact = read_json(repo_root() / "templates/A12.json")
        artifact["inhalt"]["kennzahlen"]["aufrufe"]["begruendung"] = ""
        with self.assertRaises(Blocked):
            schema_check(artifact)
        artifact = read_json(repo_root() / "templates/A12.json")
        artifact["inhalt"]["naechster_test"] = [{"hypothese": "DEMO"}, {"hypothese": "DEMO"}]
        with self.assertRaises(Blocked):
            schema_check(artifact)


class GateTests(ProjectCase):
    def test_new_project_stops_at_g0_and_no_research_job_exists(self):
        result = pipeline.run(self.root, self.state)
        self.assertEqual((result["status"], result["gate"]), ("WAITING_FOR_HUMAN", "G0"))
        self.assertEqual(self.state["jobs"], {})

    def test_gamma_then_g1_blocks_research(self):
        self.a01(candidate=False)
        result = pipeline.run(self.root, self.state)
        self.assertEqual(result["gate"], "G1")
        self.assertNotIn("A02", self.state["artifacts"])
        self.assertEqual({j["role"] for j in self.state["jobs"].values()}, {"gamma"})
        self.assertEqual(current(self.root, self.state, "A01")["version"], "1.0.0")

    def test_gate_candidate_must_be_prepared_before_operator_approval(self):
        self.a01(candidate=False)
        with self.assertRaises(Blocked):
            gates.approve(self.root, self.state, "G1", "DEMO Operator", demo_simulate=True)

    def test_gate_approval_binds_exact_versions_hashes_and_identity(self):
        self.a01()
        record = gates.approve(self.root, self.state, "G1", "DEMO Operator", demo_simulate=True)
        self.assertEqual(record["name"], "DEMO Operator")
        self.assertTrue(record["time"])
        self.assertEqual(record["binding"]["artifacts"], [self.state["artifacts"]["A01"]])
        self.assertTrue(gates.gate_valid(self.root, self.state, "G1"))
        self.assertFalse((Path(self.tmp.name) / "G0.json").exists())

    def test_missing_previous_gate_cannot_be_skipped(self):
        self.a01()
        self.worker("research")
        self.worker("alpha")
        pipeline.stage_candidates(self.root, self.state, ["A03"])
        with self.assertRaises(Blocked):
            gates.approve(self.root, self.state, "G2", "DEMO Operator", demo_simulate=True)

    def test_gate_name_and_demo_separation_are_mandatory(self):
        self.a01()
        with self.assertRaises(Blocked):
            gates.approve(self.root, self.state, "G1", "", demo_simulate=True)
        with self.assertRaises(Blocked):
            gates.approve(self.root, self.state, "G1", "DEMO Operator", demo_simulate=False)
        root, production = pipeline.new_project("Reale Themenidee")
        for gate in ("G0", "G1"):
            with self.subTest(gate=gate), self.assertRaises(Blocked):
                gates.approve(root, production, gate, "DEMO Operator", demo_simulate=True)

    def test_medical_claim_blocks_g2_and_creates_review_packet(self):
        from medizinanders.handoffs import review_packets
        self.evidence()
        self.artifact_update("A03", lambda a: a["claims"][0].update(medizinisch=True))
        self.assertIn("medical", gates.review_requirements(self.root, self.state))
        review_packets(self.root, self.state)
        packet = (self.root / "review/MEDICAL_REVIEW_PACKET.md").read_text(encoding="utf-8")
        self.assertIn("C-DEMO", packet)
        self.assertIn("Q-DEMO", packet)
        with self.assertRaises(Blocked):
            gates.approve(self.root, self.state, "G2", "DEMO Operator", demo_simulate=True)

    def test_clinical_language_escalates_even_with_false_medical_flag(self):
        self.evidence()
        self.artifact_update("A03", lambda a: a["claims"][0].update(
            aussage="DEMO: Diese Therapiewirkung ist ausschließlich ein Negativtest.", medizinisch=False))
        self.assertIn("medical", gates.review_requirements(self.root, self.state))

    def test_legal_claim_blocks_g2_and_creates_review_packet(self):
        from medizinanders.handoffs import review_packets
        self.evidence()
        self.artifact_update("A03", lambda a: a["claims"][0].update(rechtsrelevant=True))
        review_packets(self.root, self.state)
        self.assertTrue((self.root / "review/LEGAL_REVIEW_PACKET.md").is_file())
        with self.assertRaises(Blocked):
            gates.approve(self.root, self.state, "G2", "DEMO Operator", demo_simulate=True)

    def test_unqualified_or_incomplete_review_cannot_satisfy_gate(self):
        self.evidence()
        self.artifact_update("A03", lambda a: a["claims"][0].update(medizinisch=True))
        checklist = {k: True for k in gates.CHECKLISTS["medical"]}
        with self.assertRaises(Blocked):
            gates.record_review(self.root, self.state, "medical", name="DEMO", qualification="",
                                evidence="DEMO only", checklist=checklist, demo_simulate=True)
        checklist[next(iter(checklist))] = False
        with self.assertRaises(Blocked):
            gates.record_review(self.root, self.state, "medical", name="DEMO", qualification="DEMO Simulation",
                                evidence="DEMO only", checklist=checklist, demo_simulate=True)
        self.assertFalse(gates.review_valid(self.root, self.state, "medical"))

    def test_artifact_hash_tamper_revokes_valid_gate(self):
        self.a01()
        gates.approve(self.root, self.state, "G1", "DEMO Operator", demo_simulate=True)
        path = artifact_path(self.root, self.state["artifacts"]["A01"])
        path.write_text(path.read_text(encoding="utf-8") + " ", encoding="utf-8")
        self.assertFalse(gates.gate_valid(self.root, self.state, "G1"))
        with self.assertRaises(Blocked):
            current(self.root, self.state, "A01")

    def test_external_gate_record_tamper_revokes_valid_gate(self):
        self.a01()
        gates.approve(self.root, self.state, "G1", "DEMO Operator", demo_simulate=True)
        path = self.root / self.state["gates"]["G1"]["record_path"]
        record = read_json(path)
        record["name"] = "Andere DEMO-Identität"
        atomic_json(path, record)
        self.assertFalse(gates.gate_valid(self.root, self.state, "G1"))

    def test_rule_change_requires_new_operating_approval(self):
        self.a01()
        gates.approve(self.root, self.state, "G1", "DEMO Operator", demo_simulate=True)
        with patch("medizinanders.pipeline.policy_hash", return_value="f" * 64):
            self.assertFalse(gates.operating_valid(self.state))
            self.assertFalse(gates.gate_valid(self.root, self.state, "G1"))

    def test_g1_blocks_unknown_limits_missing_owners_and_open_decisions(self):
        self.a01()
        values = copy.deepcopy(current(self.root, self.state, "A01"))
        for change in (lambda a: a["ressourcen"].update(zeitbudget_stunden=None),
                       lambda a: a["ressourcen"].update(budget_eur=None),
                       lambda a: a["ressourcen"].update(zeitbudget_stunden=float("inf")),
                       lambda a: a["ressourcen"].update(budget_eur=float("nan")),
                       lambda a: a["ressourcen"].update(verantwortliche=[]),
                       lambda a: a["ressourcen"].update(werkzeuge=[]),
                       lambda a: a.update(offene_entscheidungen=["DEMO: Budget noch entscheiden"])):
            candidate = copy.deepcopy(values)
            change(candidate["inhalt"])
            with self.subTest(change=change), patch("medizinanders.gates.current", return_value=candidate):
                with self.assertRaises(Blocked):
                    gates.prerequisites(self.root, self.state, "G1")
        # Explizit entschiedenes Nullbudget ist ein Betrag; unbekanntes Budget ist None.
        self.assertEqual(gates.prerequisites(self.root, self.state, "G1")["artifacts"], [self.state["artifacts"]["A01"]])

    def test_gamma_unknown_production_resource_budget_is_schema_valid_but_g1_blocked(self):
        """Worker dürfen unbekannte Budgets ehrlich als null melden; Gate blockiert."""
        self.a01()
        artifact = copy.deepcopy(current(self.root, self.state, "A01"))
        artifact["inhalt"]["ressourcen"].update(zeitbudget_stunden=None, budget_eur=None)
        schema_check(artifact)
        with patch("medizinanders.gates.current", return_value=artifact), self.assertRaises(Blocked):
            gates.prerequisites(self.root, self.state, "G1")

    def test_missing_counterevidence_or_retraction_protocol_blocks_g2(self):
        self.evidence()
        original = current(self.root, self.state, "A02")
        for mutator in (lambda a: a.update(suchprotokoll=[]),
                        lambda a: a["suchprotokoll"][0].update(gegenbelege_gesucht=False),
                        lambda a: a["suchprotokoll"][0].update(retraktionen_geprueft=False),
                        lambda a: a["suchprotokoll"][0].update(zeitpunkt=None)):
            artifact = copy.deepcopy(original)
            mutator(artifact["inhalt"])
            actual = current
            with self.subTest(mutator=mutator), patch("medizinanders.gates.current",
                    side_effect=lambda root, state, aid: artifact if aid == "A02" else actual(root, state, aid)):
                with self.assertRaises(Blocked):
                    gates.prerequisites(self.root, self.state, "G2")

    def test_obvious_blood_pressure_claim_requires_medical_review_despite_false_flag(self):
        self.evidence()
        self.artifact_update("A03", lambda a: a["claims"][0].update(
            aussage="Dieses Mittel senkt den Blutdruck.", medizinisch=False))
        self.assertIn("medical", gates.review_requirements(self.root, self.state))
        with self.assertRaises(Blocked):
            gates.approve(self.root, self.state, "G2", "DEMO SIMULATION", demo_simulate=True)

    def production_review_scenario(self, kind):
        self.evidence()
        self.artifact_update("A03", lambda a: a["claims"][0].update(
            {"medizinisch" if kind == "medical" else "rechtsrelevant": True}))
        arguments = {"name": "DEMO SIMULATED EXPERT", "qualification": "DEMO: no real qualification",
                     "evidence": "DEMO simulation, no actual professional review",
                     "checklist": {c: True for c in gates.CHECKLISTS[kind]}, "demo_simulate": True}
        claim_record = gates.record_review(self.root, self.state, kind, stage="claims", **arguments)
        gates.approve(self.root, self.state, "G2", "DEMO SIMULATION", demo_simulate=True)
        self.worker("beta")
        pipeline.stage_candidates(self.root, self.state, ["A04", "A05", "A06"])
        self.assertTrue(gates.gate_valid(self.root, self.state, "G2"))
        self.assertTrue(gates.review_valid(self.root, self.state, kind, stage="claims"))
        self.assertFalse(gates.review_valid(self.root, self.state, kind, stage="production"))
        self.worker("qa-red-team")
        pipeline.freeze(self.root, self.state, preflight(self.root, self.state))
        with self.assertRaises(Blocked):
            gates.approve(self.root, self.state, "G3", "DEMO SIMULATION", demo_simulate=True)
        production_record = gates.record_review(self.root, self.state, kind, stage="production", **arguments)
        self.assertEqual({r["artefakt_id"] for r in claim_record["binding"]["artifacts"]}, {"A01", "A02", "A03"})
        self.assertEqual({r["artefakt_id"] for r in production_record["binding"]["artifacts"]},
                         {"A01", "A02", "A03", "A04", "A05", "A06"})
        self.assertEqual(production_record["binding"]["stage"], "production")
        self.assertNotEqual(self.state["reviews"][kind], self.state["reviews"][kind + "-production"])
        gates.approve(self.root, self.state, "G3", "DEMO SIMULATION", demo_simulate=True)
        self.assertTrue(gates.gate_valid(self.root, self.state, "G3"))
        self.assertTrue(claim_record["simulated"])
        self.assertTrue(production_record["simulated"])
        self.artifact_update("A05", lambda a: a["titel"].update(text="DEMO: title changed after production review"))
        self.assertTrue(gates.review_valid(self.root, self.state, kind, stage="claims"))
        self.assertTrue(gates.gate_valid(self.root, self.state, "G2"))
        self.assertFalse(gates.review_valid(self.root, self.state, kind, stage="production"))
        self.assertFalse(gates.gate_valid(self.root, self.state, "G3"))

    def test_medical_production_review_is_separate_from_claim_review_and_binds_script(self):
        self.production_review_scenario("medical")

    def test_legal_production_review_is_separate_from_claim_review_and_binds_script(self):
        self.production_review_scenario("legal")


class MediaGateTestdoubleTests(ProjectCase):
    """Erfolgszustände nur mit expliziten DEMO-Testdoubles ohne Render/Upload.

    Die Testdateien sind keine Videodateien. Messungen werden hier bewusst
    gemockt und in jedem Report als DEMO-Simulation bezeichnet. Reale
    FFmpeg-Messungen und der blockierte Standard-Dry-Run sind separate Tests.
    """

    @staticmethod
    def qa_double(path, report_dir=None, font_path=None):
        from medizinanders.media import SRT_CHECKS, VIDEO_CHECKS
        checks = VIDEO_CHECKS if report_dir is not None else SRT_CHECKS
        report = {"ergebnis": "freigabefaehig", "datei_sha256": digest(path), "findings": [],
                  "beispiel": True, "simulation": "DEMO IN-MEMORY TESTDOUBLE; KEINE MESSUNG ODER FREIGABE",
                  "pflichtpruefungen": [{"name": name, "status": "bestanden",
                                         "nachweis": "DEMO Testdouble, kein gemessener Produktionswert"} for name in checks]}
        if report_dir is not None:
            atomic_json(report_dir / "report.json", report)
        return report

    def setUp(self):
        super().setUp()
        self.inspect_mock = patch("medizinanders.media.inspect_video", side_effect=self.qa_double)
        self.srt_mock = patch("medizinanders.media.validate_srt", side_effect=self.qa_double)
        self.inspect = self.inspect_mock.start()
        self.srt_inspect = self.srt_mock.start()
        self.addCleanup(self.inspect_mock.stop)
        self.addCleanup(self.srt_mock.stop)
        self.editorial()
        self.worker("qa-red-team")
        pipeline.freeze(self.root, self.state, preflight(self.root, self.state))
        gates.approve(self.root, self.state, "G3", "DEMO SIMULATION", demo_simulate=True)
        self.preview = self.root / "08_produktion/inbox/preview.mp4"
        self.preview.write_bytes(b"DEMO ONLY: synthetic non-video payload for isolated gate unit tests")
        pipeline.process_preview(self.root, self.state, self.preview)

    def simulated_review(self, kind, *, which=None, decision="approved", technical_evidence=None):
        return gates.record_review(self.root, self.state, kind, name="DEMO SIMULATED OPERATOR",
                                   qualification="DEMO: no real professional qualification",
                                   evidence="DEMO TESTDOUBLE: no actual smartphone/listening/platform examination",
                                   checklist={key: True for key in gates.CHECKLISTS[kind]},
                                   decision=decision, demo_simulate=True, which=which, technical_evidence=technical_evidence)

    def missing_report_checks(self, which, *, video=(), srt=()):
        media = self.state["media"][which]
        for kind, names in (("video", video), ("srt", srt)):
            if not names:
                continue
            path_key = "report" if kind == "video" else "srt_report"
            hash_key = "report_sha256" if kind == "video" else "srt_report_sha256"
            path = self.root / media[path_key]
            report = read_json(path)
            report["ergebnis"] = "pruefung_unvollstaendig"
            for name in names:
                next(c for c in report["pflichtpruefungen"] if c["name"] == name)["status"] = "nicht_geprueft"
                report["findings"].append({"datei": "DEMO unit-test report", "problem": f"{name}: Prüfung nicht vollständig möglich.",
                                           "soll": "DEMO required measurement", "ist": "DEMO measurement unavailable",
                                           "schwere": "K1", "rueckweg": "DEMO individual technical evidence", "offen": True})
            atomic_json(path, report)
            media[hash_key] = digest(path)
        return gates.missing_technical_checks(self.root, self.state, which)

    def reach_g5a(self):
        self.simulated_review("preview")
        gates.approve(self.root, self.state, "G4", "DEMO SIMULATION", demo_simulate=True)
        self.final = self.root / "09_postproduktion/inbox/final.mp4"
        self.final.write_bytes(b"DEMO ONLY: different final unit-test payload, no real export")
        self.srt = self.root / "09_postproduktion/inbox/final.srt"
        self.srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nDEMO\n", encoding="utf-8")
        pipeline.process_final(self.root, self.state, self.final, self.srt)
        self.simulated_review("final")
        result = pipeline.run(self.root, self.state)
        self.assertEqual(result["gate"], "G5a")
        gates.approve(self.root, self.state, "G5a", "DEMO SIMULATION", demo_simulate=True)

    def platform_artifact(self, *, final_hash=None, change=None):
        content = {"final_sha256": final_hash or self.state["media"]["final"]["sha256"],
                   "video_id": "DEMOvideo01", "url": "https://www.youtube.com/watch?v=DEMOvideo01",
                   "sichtbarkeit": "private", "veroeffentlicht_am": None,
                   "ki_kennzeichnung": {"erforderlich": False, "gesetzt": False, "nachweis": "DEMO decisions only"},
                   "zielgruppe": {"fuer_kinder": False, "begruendung": "DEMO testdouble, no real platform decision"},
                   "werbung": {"enthaelt_bezahlte_werbung": False, "kennzeichnung_gesetzt": False,
                               "details": "DEMO: no upload or real advertising decision"}}
        if change:
            change(content)
        pipeline.generate(self.root, self.state, "A11", content, author="DEMO TESTDOUBLE", status="produziert")
        pipeline.stage_candidates(self.root, self.state, ["A11"])
        self.simulated_review("playback")

    def test_success_chain_g4_g5a_g5b_remains_demonstration_and_manual_publication(self):
        self.assertFalse(gates.gate_valid(self.root, self.state, "G4"))
        self.reach_g5a()
        self.platform_artifact()
        gates.approve(self.root, self.state, "G5b", "DEMO SIMULATION", demo_simulate=True)
        for gate in ("G4", "G5a", "G5b"):
            self.assertTrue(gates.gate_valid(self.root, self.state, gate))
            self.assertTrue(self.state["gates"][gate]["simulated"])
        self.assertTrue(all(read_json(self.root / record["path"])["simulated"] for record in self.state["reviews"].values()))
        result = pipeline.run(self.root, self.state)
        self.assertEqual((result["status"], result["gate"]), ("WAITING_FOR_HUMAN", "G5b"))
        self.assertEqual(current(self.root, self.state, "A11")["inhalt"]["sichtbarkeit"], "private")
        self.assertFalse(pipeline.publication_valid(self.root, self.state))
        self.assertNotIn("publication", self.state)

    def test_g4_rejects_a08_for_different_preview_hash(self):
        self.artifact_update("A08", lambda a: a.update(preview_sha256="0" * 64))
        self.simulated_review("preview")
        with self.assertRaises(Blocked):
            gates.approve(self.root, self.state, "G4", "DEMO SIMULATION", demo_simulate=True)

    def test_a10_eligibility_is_updated_only_after_complete_review_and_has_no_human_gate(self):
        self.reach_g5a()
        content = current(self.root, self.state, "A10")["inhalt"]
        self.assertEqual(content["qa"]["ergebnis"], "freigabefaehig")
        self.assertEqual(content["datei_sha256"], digest(self.final))
        self.assertNotIn("G5b", self.state["gates"])

    def test_g5a_rejects_incomplete_a10_assessment_even_with_complete_bound_reviews(self):
        self.reach_g5a()
        self.artifact_update("A10", lambda a: a["qa"].update(ergebnis="pruefung_unvollstaendig"))
        self.assertTrue(gates.review_valid(self.root, self.state, "final"))
        with self.assertRaises(Blocked):
            gates.approve(self.root, self.state, "G5a", "DEMO SIMULATION", demo_simulate=True)

    def test_g5a_rejects_a10_report_for_different_final_hash(self):
        self.reach_g5a()
        self.artifact_update("A10", lambda a: a.update(datei_sha256="0" * 64))
        with self.assertRaises(Blocked):
            gates.approve(self.root, self.state, "G5a", "DEMO SIMULATION", demo_simulate=True)

    def test_modified_final_hash_revokes_g5a_and_playback_and_requires_new_qa(self):
        self.reach_g5a()
        self.platform_artifact()
        gates.approve(self.root, self.state, "G5b", "DEMO SIMULATION", demo_simulate=True)
        self.final.write_bytes(b"DEMO: changed final export bytes, no real media")
        self.assertFalse(gates.gate_valid(self.root, self.state, "G5a"))
        self.assertFalse(gates.gate_valid(self.root, self.state, "G5b"))
        self.assertFalse(gates.review_valid(self.root, self.state, "final"))
        with self.assertRaises(Blocked):
            gates.approve(self.root, self.state, "G5b", "DEMO SIMULATION", demo_simulate=True)
        old_qa = self.state["artifacts"]["A10"]
        pipeline.process_final(self.root, self.state, self.final, self.srt)
        self.assertNotEqual(self.state["artifacts"]["A10"], old_qa)
        self.assertNotIn("A11", self.state["artifacts"])
        self.assertNotIn("G5a", self.state["gates"])
        self.assertTrue(gates.gate_valid(self.root, self.state, "G4"))

    def test_platform_wrong_final_hash_and_public_visibility_block_g5b(self):
        self.reach_g5a()
        self.platform_artifact(final_hash="0" * 64)
        with self.assertRaises(Blocked):
            gates.approve(self.root, self.state, "G5b", "DEMO SIMULATION", demo_simulate=True)
        self.platform_artifact(change=lambda a: a.update(sichtbarkeit="public"))
        with self.assertRaises(Blocked):
            gates.approve(self.root, self.state, "G5b", "DEMO SIMULATION", demo_simulate=True)

    def test_missing_platform_decisions_and_missing_required_labels_block_g5b(self):
        self.reach_g5a()
        for mutate in (lambda a: a["ki_kennzeichnung"].update(erforderlich=None),
                       lambda a: a["ki_kennzeichnung"].update(erforderlich=True, gesetzt=False),
                       lambda a: a["zielgruppe"].update(fuer_kinder=None),
                       lambda a: a["werbung"].update(enthaelt_bezahlte_werbung=None),
                       lambda a: a["werbung"].update(enthaelt_bezahlte_werbung=True, kennzeichnung_gesetzt=False)):
            self.platform_artifact(change=mutate)
            with self.subTest(mutate=mutate), self.assertRaises(Blocked):
                gates.approve(self.root, self.state, "G5b", "DEMO SIMULATION", demo_simulate=True)

    def test_force_recheck_invalidates_cached_media_approvals_without_changing_file(self):
        self.reach_g5a()
        self.platform_artifact()
        gates.approve(self.root, self.state, "G5b", "DEMO SIMULATION", demo_simulate=True)
        before = digest(self.preview)
        previous = self.state["artifacts"]["A08"]
        pipeline.process_preview(self.root, self.state, self.preview, force=True)
        self.assertEqual(digest(self.preview), before)
        self.assertNotEqual(self.state["artifacts"]["A08"], previous)
        for gate in ("G4", "G5a", "G5b"):
            self.assertFalse(gates.gate_valid(self.root, self.state, gate))
        self.assertTrue(gates.gate_valid(self.root, self.state, "G3"))

    def test_force_final_recheck_invalidates_upload_but_preserves_preview_approval(self):
        self.reach_g5a()
        before = digest(self.final)
        previous = self.state["artifacts"]["A09"]
        pipeline.process_final(self.root, self.state, self.final, self.srt, force=True)
        self.assertEqual(digest(self.final), before)
        self.assertNotEqual(self.state["artifacts"]["A09"], previous)
        self.assertFalse(gates.gate_valid(self.root, self.state, "G5a"))
        self.assertTrue(gates.gate_valid(self.root, self.state, "G4"))

    def test_media_environment_change_invalidates_cached_reports(self):
        prior = self.state["artifacts"]["A08"]
        with patch("medizinanders.pipeline.media_environment", return_value={"DEMO": "different tools and font environment"}):
            pipeline.process_preview(self.root, self.state, self.preview)
        self.assertNotEqual(self.state["artifacts"]["A08"], prior)

    def test_analytics_requires_receipt_and_imports_null_without_turning_it_into_zero(self):
        from medizinanders.cli import analytics
        self.reach_g5a()
        self.platform_artifact()
        payload = {"datenquelle": "DEMO synthetic local JSON export", "zeitraum": {"beginn": None, "ende": None, "zeitzone": "UTC"},
                   "kennzahlen": {"aufrufe": {"wert": None, "begruendung": "DEMO: metric absent from synthetic export"}},
                   "beobachtungen": ["DEMO: no views field is present."],
                   "hypothesen": ["DEMO: export selection could explain the missing field."],
                   "naechster_test": {"hypothese": "DEMO: explicit export selection returns a views field.",
                                      "veraenderte_variable": "DEMO: export column selection",
                                      "durchfuehrung": "DEMO: select only the views field in one subsequent fixture export.",
                                      "erfolgskriterium": "DEMO: views field exists or has a documented reason for absence."}}
        input_path = Path(self.tmp.name) / "DEMO_analytics_input.json"
        atomic_json(input_path, payload)
        with self.assertRaises(Blocked):
            analytics(self.root, self.state, input_path)
        self.assertNotIn("A12", self.state["artifacts"])
        policy = pipeline.policy_hash()
        # Unit-test only: isolate importer from publication receipt validation.
        with patch("medizinanders.pipeline.publication_valid", return_value=True):
            analytics(self.root, self.state, input_path)
        result = current(self.root, self.state, "A12")
        self.assertTrue(result["beispiel"])
        self.assertIsNone(result["inhalt"]["kennzahlen"]["aufrufe"]["wert"])
        self.assertEqual(result["inhalt"]["naechster_test"], payload["naechster_test"])
        self.assertEqual(self.state["analytics_imports"][-1]["sha256"], digest(input_path))
        self.assertEqual(pipeline.policy_hash(), policy)
        self.assertNotIn("publication", self.state)

    def test_technical_review_requires_individual_video_and_srt_evidence(self):
        self.reach_g5a()
        missing = self.missing_report_checks("final", video=["audio_bitrate_ziel_384kbps"], srt=["srt_pixelbreite"])
        self.assertEqual(set(missing), {"video:audio_bitrate_ziel_384kbps", "srt:srt_pixelbreite"})
        complete = {key: "DEMO individual simulated evidence; no real measurement" for key in missing}
        invalid = [None, {}, {missing[0]: "DEMO only one check"},
                   complete | {"video:unrelated": "DEMO extra check"}, {key: "  " for key in missing}]
        for evidence in invalid:
            with self.subTest(evidence=evidence), self.assertRaises(Blocked):
                self.simulated_review("technical", which="final", technical_evidence=evidence)
        self.assertFalse(gates.review_valid(self.root, self.state, "technical", "final"))
        self.simulated_review("technical", which="final", technical_evidence=complete)
        self.assertTrue(gates.review_valid(self.root, self.state, "technical", "final"))
        gates.require_media_qa(self.root, self.state, "final")
        self.assertFalse(gates.gate_valid(self.root, self.state, "G5a"))

    def test_unknown_open_k0_k1_cannot_be_overridden_by_a_missing_check_attestation(self):
        missing = self.missing_report_checks("preview", video=["audio_bitrate_ziel_384kbps"])
        path = self.root / self.state["media"]["preview"]["report"]
        base = read_json(path)
        known_problem = "audio_bitrate_ziel_384kbps: Prüfung nicht vollständig möglich."
        cases = [("K0", known_problem), ("K0", "DEMO: independent decoder corruption"),
                 ("K1", "DEMO: independent wrong spoken number"),
                 ("K1", known_problem + " DEMO: additional independent failure")]
        for severity, problem in cases:
            altered = copy.deepcopy(base)
            altered["findings"].append({"datei": "DEMO independent finding", "problem": problem,
                                         "soll": "DEMO no unresolved defect", "ist": "DEMO unresolved defect",
                                         "schwere": severity, "rueckweg": "DEMO fix source/export", "offen": True})
            atomic_json(path, altered)
            self.state["media"]["preview"]["report_sha256"] = digest(path)
            self.simulated_review("technical", which="preview", technical_evidence={
                key: "DEMO simulated individual check only" for key in missing})
            self.assertTrue(gates.review_valid(self.root, self.state, "technical", "preview"))
            with self.subTest(severity=severity, problem=problem), self.assertRaises(Blocked):
                gates.require_media_qa(self.root, self.state, "preview")

    def test_exact_missing_k1_can_be_complemented_without_claiming_human_gate(self):
        missing = self.missing_report_checks("preview", video=["audio_bitrate_ziel_384kbps"])
        with self.assertRaises(Blocked):
            gates.require_media_qa(self.root, self.state, "preview")
        self.simulated_review("technical", which="preview", technical_evidence={
            name: "DEMO individual technical testdouble evidence" for name in missing})
        gates.require_media_qa(self.root, self.state, "preview")
        self.assertFalse(gates.gate_valid(self.root, self.state, "G4"))
        record = read_json(self.root / self.state["reviews"]["technical-preview"]["path"])
        self.assertTrue(record["simulated"])
        self.assertEqual(set(record["technical_evidence"]), set(missing))

    def test_status_after_invalidation_never_replays_stale_publication_steps(self):
        from medizinanders import cli
        import json
        self.reach_g5a()
        self.platform_artifact()
        gates.approve(self.root, self.state, "G5b", "DEMO SIMULATION", demo_simulate=True)
        old_status = pipeline.run(self.root, self.state)
        self.assertTrue(any("öffentlich" in step for step in old_status["next"]))
        self.state["last_status"] = old_status
        pipeline.invalidate_change(self.root, self.state, "export", "DEMO: new final export required")
        atomic_json(self.root / "state.json", self.state)
        capture = io.StringIO()
        with redirect_stdout(capture):
            result = cli.main(["status", self.state["projekt_id"]])
        self.assertEqual(result, 0)
        shown = capture.getvalue()
        self.assertIn("ma resume " + self.state["projekt_id"], shown)
        self.assertNotIn("öffentlich", shown)
        self.assertNotIn("ma published", shown)
        capture = io.StringIO()
        with redirect_stdout(capture):
            self.assertEqual(cli.main(["status", self.state["projekt_id"], "--json"]), 0)
        latest = json.loads(capture.getvalue())
        self.assertFalse(latest["gates"]["G5a"])
        self.assertFalse(latest["gates"]["G5b"])
        self.assertNotIn("last_status", latest)


class PublicationReceiptTestdoubleTests(unittest.TestCase):
    """Reine In-Memory-Regressionen; keine echten Human- oder Uploadrecords."""
    def fixture(self):
        artifact_ref = {"artefakt_id": "A11", "version": "1.1.0", "sha256": "a" * 64}
        prior = {"DEMO": "in-memory G5a binding, not a real approval"}
        authorization = {"gate": "G5b", "simulated": False, "name": "DEMO IN-MEMORY MOCK",
                         "binding": {"DEMO": "not a real authorization", "previous": object_hash(prior)}}
        state = {"beispiel": False, "artifacts": {"A11": artifact_ref}, "gates": {"G5a": prior},
                 "publication": {"artifact": artifact_ref, "authorization": authorization | {"record_path": "DEMO-no-file.json"}}}
        artifact = {"inhalt": {"sichtbarkeit": "public"}}
        return state, artifact, authorization

    def test_receipt_validation_checks_authorization_bytes_artifact_and_actual_visibility(self):
        state, artifact, authorization = self.fixture()
        root = Path("/DEMO-IN-MEMORY-NOT-A-REAL-PROJECT")
        with patch("medizinanders.gates.gate_valid", return_value=True), \
             patch("medizinanders.pipeline.current", return_value=artifact), \
             patch("medizinanders.pipeline.read_json", return_value=authorization):
            self.assertTrue(pipeline.publication_valid(root, state))
            wrong_ref = copy.deepcopy(state)
            wrong_ref["publication"]["artifact"] = copy.deepcopy(wrong_ref["publication"]["artifact"])
            wrong_ref["publication"]["artifact"]["sha256"] = "b" * 64
            self.assertFalse(pipeline.publication_valid(root, wrong_ref))
            artifact["inhalt"]["sichtbarkeit"] = "private"
            self.assertFalse(pipeline.publication_valid(root, state))
            artifact["inhalt"]["sichtbarkeit"] = "public"
            with patch("medizinanders.pipeline.read_json", return_value=authorization | {"name": "DEMO changed receipt"}):
                self.assertFalse(pipeline.publication_valid(root, state))
            with patch("medizinanders.pipeline.read_json", return_value=authorization | {"simulated": True}):
                self.assertFalse(pipeline.publication_valid(root, state))
            with patch("medizinanders.gates.gate_valid", return_value=False):
                self.assertFalse(pipeline.publication_valid(root, state))
            state["gates"]["G5a"] = {"DEMO": "changed prior approval binding"}
            self.assertFalse(pipeline.publication_valid(root, state))

    def test_missing_and_demo_receipts_are_never_real_publication(self):
        state, artifact, authorization = self.fixture()
        root = Path("/DEMO-IN-MEMORY-NOT-A-REAL-PROJECT")
        with patch("medizinanders.gates.gate_valid", return_value=True), \
             patch("medizinanders.pipeline.current", return_value=artifact), \
             patch("medizinanders.pipeline.read_json", side_effect=FileNotFoundError("DEMO missing receipt")):
            self.assertFalse(pipeline.publication_valid(root, state))
        state["beispiel"] = True
        self.assertFalse(pipeline.publication_valid(root, state))
        state.pop("publication")
        self.assertFalse(pipeline.publication_valid(root, state))


class WorkerIntegrityTests(ProjectCase):
    def test_worker_input_context_is_minimal(self):
        self.evidence(approve_g2=True)
        result = pipeline.dispatch(self.root, self.state, "beta")
        job_path = Path(result["job_path"])
        self.assertTrue((job_path / "input/A03.json").is_file())
        self.assertFalse((job_path / "input/A01.json").exists())
        self.assertFalse((job_path / "input/A02.json").exists())
        self.assertFalse((job_path / "input/sources").exists())
        self.assertIn("BETA", (job_path / "AGENTS.md").read_text(encoding="utf-8"))

    def test_worker_input_tamper_blocks_import(self):
        self.a01()
        result = pipeline.dispatch(self.root, self.state, "research")
        job = self.state["jobs"][result["job_id"]]
        write_role_fixture(self.root, self.state, job)
        path = Path(result["job_path"]) / "input/A01.json"
        path.write_text(path.read_text(encoding="utf-8") + " ", encoding="utf-8")
        with self.assertRaises(Blocked):
            pipeline.complete_job(self.root, self.state, job["job_id"])
        self.assertNotIn("A02", self.state["artifacts"])

    def test_stale_worker_context_cannot_be_imported(self):
        self.a01()
        result = pipeline.dispatch(self.root, self.state, "research")
        job = self.state["jobs"][result["job_id"]]
        write_role_fixture(self.root, self.state, job)
        pipeline.invalidate_change(self.root, self.state, "question", "DEMO: geänderte Kernfrage")
        with self.assertRaises(Blocked):
            pipeline.complete_job(self.root, self.state, job["job_id"])

    def test_worker_cannot_claim_human_approved_artifact(self):
        result = pipeline.dispatch(self.root, self.state, "gamma")
        job = self.state["jobs"][result["job_id"]]
        write_role_fixture(self.root, self.state, job)
        path = Path(result["job_path"]) / "output/A01.json"
        artifact = read_json(path)
        artifact["status"] = "freigegeben"
        atomic_json(path, artifact)
        with self.assertRaises(Blocked):
            pipeline.complete_job(self.root, self.state, job["job_id"])

    def test_beta_import_is_atomic_if_later_artifact_invalid(self):
        self.evidence(approve_g2=True)
        result = pipeline.dispatch(self.root, self.state, "beta")
        job = self.state["jobs"][result["job_id"]]
        write_role_fixture(self.root, self.state, job)
        path = Path(result["job_path"]) / "output/A06.json"
        artifact = read_json(path)
        artifact["inhalt"]["szenen"] = []
        atomic_json(path, artifact)
        with self.assertRaises(Blocked):
            pipeline.complete_job(self.root, self.state, job["job_id"])
        for aid in ("A04", "A05", "A06"):
            self.assertNotIn(aid, self.state["artifacts"])
            self.assertFalse((self.root / "artifacts" / aid).exists())

    def test_original_source_tamper_blocks_evidence_and_independent_context(self):
        self.evidence()
        source = current(self.root, self.state, "A02")["inhalt"]["originalquellen"][0]
        path = self.root / source["lokaler_pfad"]
        path.write_text("DEMO: manipulierte Originalkopie", encoding="utf-8")
        with self.assertRaises(Blocked):
            pipeline.evidence_validate(self.root, self.state)
        for job in self.state["jobs"].values():
            if job["role"] == "alpha":
                job["invalidated"] = True
        with self.assertRaises(Blocked):
            pipeline.dispatch(self.root, self.state, "alpha")

    def test_missing_named_red_team_checks_cannot_be_called_complete(self):
        self.editorial()
        result = pipeline.dispatch(self.root, self.state, "qa-red-team")
        job = self.state["jobs"][result["job_id"]]
        write_role_fixture(self.root, self.state, job)
        path = Path(result["job_path"]) / "output/QA.json"
        report = read_json(path)
        report["pflichtpruefungen"] = [c for c in report["pflichtpruefungen"] if c["name"] != "factuality"]
        atomic_json(path, report)
        with self.assertRaises(Blocked):
            pipeline.complete_job(self.root, self.state, job["job_id"])
        self.assertIsNone(self.state["red_team"])

    def test_beta_io_failure_on_second_artifact_rolls_back_state_and_written_files(self):
        self.evidence(approve_g2=True)
        result = pipeline.dispatch(self.root, self.state, "beta")
        job = self.state["jobs"][result["job_id"]]
        write_role_fixture(self.root, self.state, job)
        before = copy.deepcopy(self.state)
        prior = {str(p.relative_to(self.root)): digest(p) for folder in ("artifacts", "sources")
                 for p in (self.root / folder).rglob("*") if p.is_file()}
        write = pipeline.atomic_json
        written = []
        def failing_write(path, value, exclusive=False):
            written.append(Path(path).parent.name)
            if Path(path).parent.name == "A05":
                # Simulate a real post-write failure, not just a validation error.
                with patch("medizinanders.storage.os.fsync", side_effect=OSError("DEMO injected disk failure")):
                    return write(path, value, exclusive=exclusive)
            return write(path, value, exclusive=exclusive)
        with patch("medizinanders.pipeline.atomic_json", side_effect=failing_write), self.assertRaises(Blocked):
            pipeline.complete_job(self.root, self.state, job["job_id"])
        self.assertIn("A04", written)
        self.assertIn("A05", written)
        self.assertEqual(self.state, before)
        self.assertEqual(prior, {str(p.relative_to(self.root)): digest(p) for folder in ("artifacts", "sources")
                               for p in (self.root / folder).rglob("*") if p.is_file()})
        self.assertFalse(self.state["jobs"][job["job_id"]]["completed"])
        self.assertTrue(gates.gate_valid(self.root, self.state, "G2"))

    def test_a03_catalog_forwards_only_referenced_original_metadata_to_beta(self):
        self.a01()
        gates.approve(self.root, self.state, "G1", "DEMO SIMULATION", demo_simulate=True)
        result = pipeline.dispatch(self.root, self.state, "research")
        job = self.state["jobs"][result["job_id"]]
        write_role_fixture(self.root, self.state, job)
        output = Path(result["job_path"]) / "output/A02.json"
        artifact = read_json(output)
        # Reserved .invalid URL: bibliography unit test, no web access is claimed.
        expected_url = "https://example.invalid/DEMO/local-fixture"
        artifact["inhalt"]["originalquellen"][0]["url"] = expected_url
        unused = copy.deepcopy(artifact["inhalt"]["originalquellen"][0])
        unused.update(quelle_id="Q-DEMO-UNUSED", url="https://example.invalid/DEMO/unreferenced",
                      titel="DEMO: unreferenced synthetic local copy")
        artifact["inhalt"]["originalquellen"].append(unused)
        atomic_json(output, artifact)
        pipeline.complete_job(self.root, self.state, job["job_id"])
        pipeline.stage_candidates(self.root, self.state, ["A02"])
        self.worker("alpha")
        pipeline.stage_candidates(self.root, self.state, ["A03"])
        catalog = current(self.root, self.state, "A03")["inhalt"]["quellenkatalog"]
        original = current(self.root, self.state, "A02")["inhalt"]["originalquellen"][0]
        self.assertEqual(catalog, [{key: original[key] for key in ("quelle_id", "url", "titel", "zugriff", "sha256")}])
        gates.approve(self.root, self.state, "G2", "DEMO SIMULATION", demo_simulate=True)
        beta = pipeline.dispatch(self.root, self.state, "beta")
        inputs = Path(beta["job_path"]) / "input"
        beta_claims = read_json(inputs / "A03.json")["inhalt"]
        self.assertEqual(beta_claims["quellenkatalog"][0]["url"], expected_url)
        self.assertNotIn("Q-DEMO-UNUSED", str(beta_claims["quellenkatalog"]))
        self.assertFalse((inputs / "A02.json").exists())
        self.assertFalse((inputs / "sources").exists())
        self.assertNotIn("parameter", beta_claims["quellenkatalog"][0])

    def test_forged_a03_catalog_cannot_override_original_url(self):
        self.evidence()
        before = copy.deepcopy(self.state)
        artifact = copy.deepcopy(current(self.root, self.state, "A03"))
        artifact["inhalt"]["quellenkatalog"][0]["url"] = "https://example.invalid/DEMO/forged"
        with self.assertRaises(Blocked):
            pipeline.put_artifact(self.root, self.state, artifact, bind_inputs=True)
        self.assertEqual(self.state, before)


class PreflightTests(ProjectCase):
    def setUp(self):
        super().setUp()
        self.editorial()

    def test_complete_cross_consistent_fixture_passes(self):
        self.assertEqual(preflight(self.root, self.state)["ergebnis"], "freigabefaehig")

    def test_factual_sentence_without_claim_is_blocked(self):
        with self.assertRaises(Blocked):
            self.preflight_change("A05", lambda a: a["saetze"][2].update(claim_ids=[]))

    def test_unknown_or_unusable_claim_is_blocked(self):
        with self.assertRaises(Blocked):
            self.preflight_change("A05", lambda a: a["saetze"][2].update(claim_ids=["C-NOT-FOUND"]))
        with self.assertRaises(Blocked):
            self.preflight_change("A03", lambda a: a["claims"][0].update(einsatz="nein"))

    def test_factual_title_thumbnail_and_overlay_require_claims(self):
        for field in ("titel", "thumbnail"):
            with self.subTest(field=field), self.assertRaises(Blocked):
                self.preflight_change("A05", lambda a: a[field].update(text="DEMO: angebliche Tatsache", faktisch=True))
        with self.assertRaises(Blocked):
            self.preflight_change("A05", lambda a: a["overlays"].append(
                {"text": "DEMO: faktischer Overlaytext", "faktisch": True, "claim_ids": [], "start": 8, "ende": 10}))

    def test_numbers_without_claim_mapping_are_blocked(self):
        with self.assertRaises(Blocked):
            self.preflight_change("A05", lambda a: a["titel"].update(text="DEMO: 17 Vorlagen"))

    def test_unchecked_original_cannot_support_confirmed_claim(self):
        with self.assertRaises(Blocked):
            self.preflight_change("A02", lambda a: a["originalquellen"][0].update(zugriff="nicht_geprueft"))

    def test_qualifier_must_appear_in_voiceover(self):
        with self.assertRaises(Blocked):
            self.preflight_change("A03", lambda a: a["claims"][0].update(
                status="TEILWEISE", einsatz="nur_mit_einschraenkung", einschraenkungen=["DEMO: ausschließlich nach genauer Prüfung"]))

    def test_second_cta_is_blocked(self):
        with self.assertRaises(Blocked):
            self.preflight_change("A05", lambda a: a["saetze"][0].update(funktion="cta"))

    def test_voiceover_and_subtitle_base_cannot_diverge(self):
        for field in ("sprechertext", "untertitel_basis"):
            with self.subTest(field=field), self.assertRaises(Blocked):
                self.preflight_change("A05", lambda a: a.update({field: a[field] + " Andere Worte."}))

    def test_word_count_is_measured_not_trusted(self):
        with self.assertRaises(Blocked):
            self.preflight_change("A05", lambda a: a.update(wortzahl=110))

    def test_timeline_gap_overlap_and_nonexact_cut_are_blocked(self):
        for altered in (3.001, 2.999):
            with self.subTest(start=altered), self.assertRaises(Blocked):
                self.preflight_change("A06", lambda a: a["szenen"][1].update(start=altered))
        with self.assertRaises(Blocked):
            self.preflight_change("A06", lambda a: a["szenen"][1].update(uebergang="weiche Blende"))

    def test_disclaimer_exact_text_no_music_and_exclusive_interval(self):
        with self.assertRaises(Blocked):
            self.preflight_change("A05", lambda a: a.update(disclaimer="Kein medizinischer Rat."))
        for mutator in (lambda a: a["szenen"][-1].update(start=53.9),
                        lambda a: a["szenen"][-1].update(sprechertext="DEMO"),
                        lambda a: a["szenen"][-1]["audio"].update(musik="DEMO Musik")):
            with self.subTest(mutator=mutator), self.assertRaises(Blocked):
                self.preflight_change("A06", mutator)

    def test_unknown_asset_or_open_rights_block_production(self):
        with self.assertRaises(Blocked):
            self.preflight_change("A06", lambda a: a["szenen"][0].update(assetbedarf=["AS-UNKNOWN"]))
        with self.assertRaises(Blocked):
            self.preflight_change("A06", lambda a: a["assets"].append(
                {"asset_id": "AS-DEMO", "typ": "grafik", "beschreibung": "DEMO Grafik",
                 "rechte_status": "offen", "rechte_beleg": "", "ki_illustration": False}))


class QAAndInvalidationTests(ProjectCase):
    def test_k0_k1_and_missing_checks_prevent_eligibility(self):
        report = {"ergebnis": "freigabefaehig", "findings": [],
                  "pflichtpruefungen": [{"name": "DEMO Pflichtprüfung", "status": "bestanden"}]}
        qa_check(report)
        for severity in ("K0", "K1"):
            altered = copy.deepcopy(report)
            altered["findings"] = [{"datei": "DEMO", "problem": "DEMO Fehler", "soll": "korrekt",
                                     "ist": "falsch", "schwere": severity, "rueckweg": "ALPHA", "offen": True}]
            with self.subTest(severity=severity), self.assertRaises(Blocked):
                qa_check(altered)
        for checks in ([], [{"name": "DEMO", "status": "nicht_geprueft"}],
                       [{"name": "DEMO", "status": "nicht_anwendbar"}]):
            with self.subTest(checks=checks), self.assertRaises(Blocked):
                qa_check(report | {"pflichtpruefungen": checks})

    def test_source_change_returns_to_research_and_revokes_downstream(self):
        self.editorial()
        pipeline.invalidate_change(self.root, self.state, "source", "DEMO: geänderte Originalquelle")
        self.assertEqual(set(self.state["artifacts"]), {"A01"})
        self.assertTrue(gates.gate_valid(self.root, self.state, "G1"))
        self.assertFalse(gates.gate_valid(self.root, self.state, "G2"))
        self.assertTrue(any(j.get("invalidated") for j in self.state["jobs"].values()))

    def test_wording_preserves_claim_approval_but_revokes_script_scene_and_freeze(self):
        self.editorial()
        pipeline.invalidate_change(self.root, self.state, "wording", "DEMO: neue Formulierung")
        self.assertIn("A03", self.state["artifacts"])
        self.assertIn("A04", self.state["artifacts"])
        self.assertNotIn("A05", self.state["artifacts"])
        self.assertNotIn("A06", self.state["artifacts"])
        self.assertTrue(gates.gate_valid(self.root, self.state, "G2"))
        self.assertIsNone(self.state["freeze"])

    def test_meaning_change_returns_to_alpha_and_g2(self):
        self.editorial()
        pipeline.invalidate_change(self.root, self.state, "meaning", "DEMO: geänderte Bedeutung")
        self.assertEqual(set(self.state["artifacts"]), {"A01", "A02"})
        self.assertFalse(gates.gate_valid(self.root, self.state, "G2"))

    def test_new_version_never_inherits_approval(self):
        self.a01()
        gates.approve(self.root, self.state, "G1", "DEMO Operator", demo_simulate=True)
        previous = copy.deepcopy(self.state["artifacts"]["A01"])
        self.artifact_update("A01", lambda a: a.update(nutzen="DEMO: geänderter Lernzweck"))
        self.assertEqual(self.state["artifacts"]["A01"]["version"], "1.1.0")
        self.assertTrue(artifact_path(self.root, previous).is_file())
        self.assertFalse(gates.gate_valid(self.root, self.state, "G1"))

    def test_semantic_change_cannot_be_claimed_as_patch(self):
        self.a01()
        artifact = copy.deepcopy(current(self.root, self.state, "A01"))
        artifact["inhalt"]["kernfrage"] = "DEMO: wesentlich andere Frage?"
        with self.assertRaises(Blocked):
            pipeline.put_artifact(self.root, self.state, artifact, bind_inputs=True, bump="patch")

    def test_stale_dependency_and_unknown_project_are_rejected(self):
        self.evidence()
        artifact = copy.deepcopy(current(self.root, self.state, "A03"))
        artifact["eingaben"][0]["sha256"] = "0" * 64
        with self.assertRaises(Blocked):
            dependency_check(self.root, self.state, artifact)
        artifact = copy.deepcopy(current(self.root, self.state, "A03"))
        artifact["projekt_id"] = "MA-20261003-999"
        with self.assertRaises(Blocked):
            dependency_check(self.root, self.state, artifact)

    def test_direct_import_io_failure_preserves_prior_artifact_and_g1(self):
        self.a01()
        gates.approve(self.root, self.state, "G1", "DEMO SIMULATION", demo_simulate=True)
        before = copy.deepcopy(self.state)
        previous = copy.deepcopy(self.state["artifacts"]["A01"])
        old_bytes = artifact_path(self.root, previous).read_bytes()
        artifact = copy.deepcopy(current(self.root, self.state, "A01"))
        artifact["inhalt"]["nutzen"] = "DEMO: changed purpose, write must fail atomically"
        with patch("medizinanders.storage.os.fsync", side_effect=OSError("DEMO injected final fsync failure")):
            with self.assertRaises((OSError, Blocked)):
                pipeline.put_artifact(self.root, self.state, artifact, bind_inputs=True)
        self.assertEqual(self.state, before)
        self.assertEqual(artifact_path(self.root, previous).read_bytes(), old_bytes)
        self.assertFalse((self.root / "artifacts/A01/1.1.0.json").exists())
        self.assertTrue(gates.gate_valid(self.root, self.state, "G1"))

    def test_cli_import_io_failure_preserves_persisted_artifact_and_g1(self):
        from medizinanders import cli
        self.a01()
        gates.approve(self.root, self.state, "G1", "DEMO SIMULATION", demo_simulate=True)
        atomic_json(self.root / "state.json", self.state)
        before = read_json(self.root / "state.json")
        candidate = copy.deepcopy(current(self.root, self.state, "A01"))
        candidate.update(version="1.1.0", status="Entwurf")
        candidate["inhalt"]["nutzen"] = "DEMO: candidate import must not replace the prior approved version on I/O failure"
        input_file = Path(self.tmp.name) / "DEMO_candidate.json"
        atomic_json(input_file, candidate)
        with patch("medizinanders.pipeline.atomic_json", side_effect=OSError("DEMO artifact write failure")), redirect_stdout(io.StringIO()):
            result = cli.main(["import", self.state["projekt_id"], "--file", str(input_file)])
        self.assertEqual(result, 2)
        after = read_json(self.root / "state.json")
        self.assertEqual(after, before)
        self.assertTrue(gates.gate_valid(self.root, after, "G1"))
        self.assertFalse((self.root / "artifacts/A01/1.1.0.json").exists())


class CompleteDemoTests(ProjectCase):
    def test_complete_dry_run_stops_before_invideo_and_freezes_all_handoffs(self):
        report = run_demo(self.tmp.name, with_video=False)
        root = Path(report["project_path"])
        state = read_json(root / "state.json")
        self.assertEqual(report["status"], "DEMO_COMPLETE")
        human_stops = [e["gate"] for e in report["events"] if e["status"] == "WAITING_FOR_HUMAN"]
        self.assertEqual(human_stops[:3], ["G1", "G2", "G3"])
        self.assertEqual(report["stopped_at"]["blocked_at"], "G3_INVIDEO")
        self.assertFalse(report["real_upload"])
        self.assertFalse(report["real_publication"])
        self.assertEqual(set(state["gates"]), {"G0", "G1", "G2", "G3"})
        self.assertTrue(all(g["simulated"] for g in state["gates"].values()))
        self.assertFalse((Path(self.tmp.name) / "G0.json").exists())
        expected = {"INVIDEO_PROMPT.txt", "SCENE_PLAN.md", "VOICEOVER.txt", "SUBTITLE_BASE.txt",
                    "ASSET_MANIFEST.yaml", "RIGHTS_CHECKLIST.md", "EXPECTED_OUTPUT.md", "OPERATOR_STEPS.md"}
        self.assertTrue(expected.issubset({p.name for p in (root / "handoff/invideo").iterdir()}))
        pipeline.verify_freeze(root, state)
        frozen = root / "freeze" / state["freeze"]["revision"]
        self.assertTrue((frozen / "SHA256SUMS").is_file())
        self.assertFalse((frozen / "gates").exists())
        for i in range(1, 7):
            self.assertTrue((frozen / f"A{i:02d}-{state['artifacts'][f'A{i:02d}']['version']}.json").is_file())

    def test_freeze_hash_tamper_extra_file_and_handoff_tamper_block_g3(self):
        report = run_demo(self.tmp.name, with_video=False)
        root = Path(report["project_path"])
        state = read_json(root / "state.json")
        frozen = root / "freeze" / state["freeze"]["revision"]
        (frozen / "undeclared.txt").write_text("DEMO: zusätzliche Datei", encoding="utf-8")
        with self.assertRaises(Blocked):
            pipeline.verify_freeze(root, state)
        self.assertFalse(gates.gate_valid(root, state, "G3"))
        (frozen / "undeclared.txt").unlink()
        sums = frozen / "SHA256SUMS"
        original = sums.read_bytes()
        sums.write_bytes(original + b"DEMO tamper\n")
        with self.assertRaises(Blocked):
            pipeline.verify_freeze(root, state)
        sums.write_bytes(original)
        prompt = root / "handoff/invideo/INVIDEO_PROMPT.txt"
        prompt.write_text(prompt.read_text(encoding="utf-8") + "DEMO: nachträgliche Änderung", encoding="utf-8")
        self.assertFalse(gates.gate_valid(root, state, "G3"))

    def test_revision_is_never_overwritten_after_new_freeze(self):
        report = run_demo(self.tmp.name, with_video=False)
        root = Path(report["project_path"])
        state = read_json(root / "state.json")
        first = root / "freeze/r001"
        snapshot = {str(p.relative_to(first)): digest(p) for p in first.rglob("*") if p.is_file()}
        pipeline.invalidate_change(root, state, "wording", "DEMO: neuer Sprecherentwurf")
        result = pipeline.dispatch(root, state, "beta")
        job = state["jobs"][result["job_id"]]
        write_role_fixture(root, state, job)
        pipeline.complete_job(root, state, job["job_id"])
        pipeline.stage_candidates(root, state, ["A04", "A05", "A06"])
        result = pipeline.dispatch(root, state, "qa-red-team")
        job = state["jobs"][result["job_id"]]
        write_role_fixture(root, state, job)
        pipeline.complete_job(root, state, job["job_id"])
        pipeline.freeze(root, state, preflight(root, state))
        self.assertEqual(state["freeze"]["revision"], "r002")
        self.assertEqual(snapshot, {str(p.relative_to(first)): digest(p) for p in first.rglob("*") if p.is_file()})
        self.assertFalse(gates.gate_valid(root, state, "G3"))

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "Reale FFmpeg/ffprobe-Werkzeuge fehlen")
    def test_actual_demo_fixture_is_measured_and_never_human_approved(self):
        report = run_demo(self.tmp.name, with_video=True)
        root = Path(report["project_path"])
        state = read_json(root / "state.json")
        self.assertEqual(report["video_fixture"]["status"], "GENERATED_DEMO_FIXTURE")
        self.assertEqual(report["stopped_at"]["gate"], "G4")
        qa = read_json(root / state["media"]["preview"]["report"])
        self.assertEqual(qa["datei_sha256"], digest(root / "08_produktion/inbox/preview.mp4"))
        self.assertTrue(any(f["schwere"] == "K1" and f["offen"] for f in qa["findings"]))
        for gate in ("G4", "G5a", "G5b"):
            self.assertNotIn(gate, state["gates"])
            self.assertFalse(gates.gate_valid(root, state, gate))
            with self.subTest(gate=gate), self.assertRaises(Blocked):
                gates.approve(root, state, gate, "DEMO Operator", demo_simulate=True)
        self.assertNotIn("A11", state["artifacts"])
        self.assertTrue((root / "handoff/youtube/UPLOAD_CHECKLIST.md").is_file())

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "Reale FFmpeg/ffprobe-Werkzeuge fehlen")
    def test_new_final_export_creates_new_qa_and_retains_historical_bytes(self):
        report = run_demo(self.tmp.name, with_video=True)
        root = Path(report["project_path"])
        state = read_json(root / "state.json")
        preview_ref = copy.deepcopy(state["artifacts"]["A08"])
        final_ref = copy.deepcopy(state["artifacts"]["A09"])
        old_report = state["media"]["final"]["report"]
        final = root / "09_postproduktion/inbox/final.mp4"
        # Tatsächlich anderer Exporthash; keine automatische Korrektur oder neue Freigabe.
        with final.open("ab") as stream:
            stream.write(b"\nDEMO changed export fixture\n")
        pipeline.process_final(root, state, final, root / "09_postproduktion/inbox/final.srt")
        self.assertEqual(state["artifacts"]["A08"], preview_ref)
        self.assertNotEqual(state["artifacts"]["A09"]["sha256"], final_ref["sha256"])
        self.assertNotEqual(state["media"]["final"]["report"], old_report)
        self.assertTrue((root / old_report).is_file())
        self.assertTrue(artifact_path(root, final_ref).is_file())
        self.assertFalse(gates.gate_valid(root, state, "G5a"))


if __name__ == "__main__":
    unittest.main()
