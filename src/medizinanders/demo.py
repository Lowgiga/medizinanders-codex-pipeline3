"""Synthetischer Integrationstest; erzeugt niemals reale Human-Freigaben.

Alle Worker-Ausgaben sind deterministische DEMO-Fixtures. Damit wird der
Orchestrator geprüft, nicht die Qualität eines LLMs oder einer Webrecherche.
"""
from __future__ import annotations

import contextlib
import copy
import os
import shutil
import subprocess
from pathlib import Path

from .storage import (Blocked, atomic_json, current, data_root, digest, now,
                      read_json, repo_root, write_text)
from .validation import DISCLAIMER, PHASES, word_count


SOURCE_TEXT = (
    "DEMO://fixture\n"
    "Dies ist ausschließlich eine synthetische lokale Testvorlage.\n"
    "Diese synthetische DEMO-Vorlage enthält eine klare Quellenmarkierung.\n"
    "Keine Aussage über Gesundheit, Menschen, Unternehmen oder reale Studien.\n"
    "DEMO-Korrekturprotokoll: keine Änderungen in dieser einzelnen Fixture.\n"
    "DEMO-Gegenbelegsuche: Die Quellenmarkierung steht sichtbar in Zeile eins.\n"
)

SCRIPT = [
    ("hook", "Woran erkennst du eine sorgfältig gekennzeichnete Vorlage?", False),
    ("open_loop", "Lass uns dafür heute eine rein synthetische DEMO betrachten.", False),
    ("payload", "Diese synthetische DEMO-Vorlage enthält eine klare Quellenmarkierung.", True),
    ("payload", "Stell dir beim Lesen eine einfache Frage: Woher stammt die konkrete Aussage?", False),
    ("payload", "Bitte achte dabei auf den sichtbaren Ursprung und auf die Grenze zwischen einer Beobachtung und einer Vermutung.", False),
    ("payload", "Nimm dir auch Zeit für Gegenargumente und für mögliche Unsicherheiten, bevor du einen Text zur weiteren Prüfung weitergibst.", False),
    ("payload", "Betrachte dieses Beispiel ausschließlich als Übung für den Arbeitsablauf.", False),
    ("verdichtung", "Behalte die Kennzeichnung im Blick und lies jeden Entwurf aufmerksam und mit Ruhe.", False),
    ("cta", "Prüfe beim nächsten Entwurf bewusst die sichtbare Quellenmarkierung.", False),
    ("ausklang", "Danke fürs aufmerksame Mitdenken.", False),
]


def artifact_fixture(aid: str, project_id: str, content: dict) -> dict:
    """Expliziter Entwurf für den normalen Worker-Importer, keine Freigabe."""
    return {"artefakt_id": aid, "projekt_id": project_id, "version": "0.1.0",
            "datum": now(), "autor": f"DEMO-{aid}-FIXTURE", "status": "Entwurf",
            "eingaben": [], "quellen": ["Q-DEMO"] if aid != "A01" else [],
            "offene_punkte": [], "gesperrt": False, "sperrgrund": "",
            "beispiel": True, "inhalt": copy.deepcopy(content)}


def fixture_contents(source_hash: str, source_path="sources/original.txt") -> dict:
    """Vollständige synthetische A01–A06-Nutzlasten ohne medizinische Fakten."""
    sentences = [{"satz_id": f"S{i:02d}", "text": text, "faktisch": factual,
                  "claim_ids": ["C-DEMO"] if factual else [], "funktion": phase}
                 for i, (phase, text, factual) in enumerate(SCRIPT, 1)]
    speech = " ".join(s["text"] for s in sentences)
    publication = lambda text, factual=False: {
        "text": text, "faktisch": factual, "claim_ids": ["C-DEMO"] if factual else []}
    scenes = []
    for i, (phase, start, end) in enumerate(PHASES, 1):
        related = [s for s in sentences if s["funktion"] == phase]
        scenes.append({"szene_id": f"SC{i:02d}", "start": start, "ende": end,
                       "sprechertext": " ".join(s["text"] for s in related), "funktion": phase,
                       "motiv": "schwarz" if phase == "disclaimer" else "DEMO: abstrakte Textgrafik",
                       "assetbedarf": [],
                       "sync_anker": "Exklusiver Disclaimerbeginn" if phase == "disclaimer" else
                                     "Erstes gesprochenes Wort dieser Szene",
                       "overlay": DISCLAIMER if phase == "disclaimer" else "DEMO",
                       "quellenhinweis": "DEMO://fixture, Zeile eins" if phase == "payload" else "",
                       "uebergang": "harter Schnitt" if start == 3 else "Schnitt an der Szenengrenze",
                       "audio": {"musik": "keine", "effekte": "keine",
                                 "mischung": "Vollständige Stille" if phase == "disclaimer" else
                                             "Ruhige deutsche Stimme, keine Imitation, keine Musik"},
                       "claim_ids": ["C-DEMO"] if any(s["faktisch"] for s in related) else []})
    independent_prompt = (
        "DEMO. Rein synthetischer Produktionsauftrag, keine reale Episode. "
        "Erzeuge nur nach menschlichem G3 einen Entwurf: 58 Sekunden, 9:16, "
        "1080 × 1920, 30 fps; Zielprofil lokal prüfen, Exportparameter sind nicht garantiert. "
        "Ruhige erwachsene deutsche Stimme, keine Imitation und keine gespielte ärztliche Autorität. "
        "Keine Musik, kein Gesang, keine Stings. Untertitel Deutsch, Montserrat Bold, 52 px, weiß, "
        "maximal zwei Zeilen und 28 Zeichen je Zeile, 18 Zeichen/Sekunde; Unterkante y=1520. "
        "Sicherer Bildbereich x=90…930, y=192…1536; Quellenhinweise y=1200…1320. "
        "Eine CTA; harter Schnitt exakt bei 3,000 s. Die letzten vier Sekunden sind schwarz, "
        "ohne Stimme und Musik, ausschließlich mit dem vorgegebenen Disclaimer. "
        "Sprechertext vollständig:\n" + speech + "\nSzenen vollständig:\n" +
        "\n".join(f"{s['szene_id']} {s['start']}–{s['ende']} s; {s['funktion']}; "
                  f"Motiv {s['motiv']}; Sprecher: {s['sprechertext']}; Overlay: {s['overlay']}; "
                  f"Quellenhinweis: {s['quellenhinweis']}; Übergang: {s['uebergang']}; "
                  f"Audio: {s['audio']['mischung']}; Sync: {s['sync_anker']}; "
                  "Assets: keine fremden Medien."
                  for s in scenes)
    )
    parameters = {key: "Nicht anwendbar: synthetische Textvorlage, keine klinische Studie."
                  for key in ("population", "design", "vergleich", "endpunkt", "absolute_wirkung",
                              "relative_wirkung", "unsicherheit", "interessenkonflikte", "gueltigkeitsgrenzen")}
    return {
        "A01": {"kernfrage": "DEMO: Wie wird eine Quellenmarkierung in einer synthetischen Vorlage geprüft?",
                "nutzen": "Ausschließlich den technischen Arbeitsablauf demonstrieren.",
                "zielgruppe": "DEMO-Testbetreiber", "scope": ["Synthetische lokale Textvorlage"],
                "ausschluesse": ["Keine Gesundheitsinformation, keine echte Veröffentlichung"],
                "suchfragen": ["Steht die DEMO-Quellenmarkierung tatsächlich in der lokalen Vorlage?"],
                "format": {"plattform": "youtube", "dauer_sekunden": 58,
                           "seitenverhaeltnis": "9:16", "sprache": "de-DE", "stil": "Synthetische DEMO"},
                "ressourcen": {"zeitbudget_stunden": 0, "budget_eur": 0,
                               "werkzeuge": ["Lokale Fixture; kein Webzugriff"],
                               "verantwortliche": ["DEMO-Testsimulation, keine reale Person"],
                               "grenzen": ["Keine echten Kosten akzeptiert"]}, "offene_entscheidungen": []},
        "A02": {"suchprotokoll": [{"suchfrage": "Existiert die Kennzeichnung in der DEMO-Originalkopie?",
                                  "werkzeug": "DEMO: lokales Lesen einer synthetischen Datei, keine Webrecherche",
                                  "zeitpunkt": now(), "ergebnis": "Zeilen eins und drei tatsächlich gelesen.",
                                  "gegenbelege_gesucht": True, "retraktionen_geprueft": True}],
                "originalquellen": [{"quelle_id": "Q-DEMO", "url": "",
                                     "titel": "DEMO://fixture – rein synthetische lokale Textvorlage",
                                     "typ": "primaerquelle", "zugriff": "geprüft", "geoeffnet_am": now(),
                                     "fundstellen": ["Zeile eins: Quellenmarkierung; Zeile drei: Claim"],
                                     "lokaler_pfad": source_path, "sha256": source_hash, "parameter": parameters}],
                "gegenbelege": [], "unsicherheiten": [
                    "Gegenbelege/Korrekturen nur innerhalb der lokalen DEMO-Fixture geprüft; keine reale Webprüfung.",
                    "Diese synthetische Textbeobachtung ist auf keine reale Gesundheitsfrage übertragbar."]},
        "A03": {"faktenmatrix": [{"claim_id": "C-DEMO", "beobachtung": "Kennzeichnung in Zeile eins gelesen."}],
                "claims": [{"claim_id": "C-DEMO", "aussage": SCRIPT[2][1], "status": "BESTÄTIGT", "einsatz": "ja",
                            "belege": [{"quelle_id": "Q-DEMO", "fundstelle": "Zeile eins und Zeile drei"}],
                            "gegenbelege": [], "einschraenkungen": ["Gilt ausschließlich für diese synthetische DEMO-Fixture."],
                            "medizinisch": False, "rechtsrelevant": False}], "risiken": [],
                "psychologie_map": [{"mechanismus": "Aufmerksamkeit auf Herkunft",
                                     "beschreibung": "DEMO: Lesende sollen die Quellenmarkierung bemerken.",
                                     "grenzen": "Keine Angst und keine medizinische Autorität inszenieren."}]},
        "A04": {"profil": "MA-SHORT-58-v1.0", "dramaturgie": [
            {"beat_id": f"B{i:02d}", "funktion": p, "start": s, "ende": e,
             "kernpunkt": DISCLAIMER if p == "disclaimer" else f"DEMO: {p}",
             "claim_ids": ["C-DEMO"] if p == "payload" else []}
            for i, (p, s, e) in enumerate(PHASES, 1)]},
        "A05": {"saetze": sentences, "sprechertext": speech, "wortzahl": word_count(speech),
                "untertitel_basis": speech, "aussprache": [
                    {"begriff": "DEMO", "aussprache": "Demo"}],
                "overlays": [], "titel": publication("DEMO: Eine Vorlage bewusst lesen"),
                "thumbnail": publication("DEMO: Herkunft prüfen"),
                "beschreibung": publication("DEMO. Bitte betrachte dieses synthetische Beispiel ausschließlich als Workflow-Übung."),
                "quellenangaben": [{"quelle_id": "Q-DEMO", "fundstelle": "Zeilen eins und drei",
                                    "text": "Q-DEMO: lokale synthetische Vorlage DEMO://fixture", "url": ""}],
                "cta": publication(next(s["text"] for s in sentences if s["funktion"] == "cta")),
                "disclaimer": DISCLAIMER, "hashtags": ["#DEMO"]},
        "A06": {"szenen": scenes, "assets": [], "invideo_auftrag": independent_prompt},
    }


def write_role_fixture(root: Path, state: dict, job: dict):
    """Schreibt ausschließlich in den zugewiesenen Joboutput."""
    if not state.get("beispiel") or not job.get("beispiel"):
        raise Blocked("DEMO-Fixtures ausschließlich in gekennzeichneten DEMO-Projekten.")
    directory = root / "jobs" / job["job_id"] / "output"
    directory.mkdir(parents=True, exist_ok=True)
    if job["role"] == "qa-red-team":
        atomic_json(directory / "QA.json", {"ergebnis": "freigabefaehig", "findings": [],
                    "pflichtpruefungen": [{"name": name, "status": "bestanden", "art": "technisch",
                                           "nachweis": "DEMO: deterministisches Testdouble, keine reale Human-/Fachprüfung"}
                                          for name in ("factuality", "claim_mapping", "rights", "medical_legal",
                                                       "production", "context_integrity")]})
        return
    source = directory / "sources" / "original.txt"
    write_text(source, SOURCE_TEXT)
    contents = fixture_contents(digest(source))
    for filename in job["output_files"]:
        aid = Path(filename).stem
        artifact = artifact_fixture(aid, state["projekt_id"], contents[aid])
        artifact["eingaben"] = copy.deepcopy(job["input_refs"])
        atomic_json(directory / filename, artifact)


def create_video_fixture(path: Path) -> dict:
    """Erzeugt eine echte kleine Testdatei; bewusst kein Produktionsprofil."""
    binary = shutil.which("ffmpeg")
    if not binary:
        return {"status": "MANUAL_STEP", "why": "ffmpeg fehlt; installieren und ma demo erneut starten."}
    path.parent.mkdir(parents=True, exist_ok=True)
    command = [binary, "-hide_banner", "-nostdin", "-loglevel", "error", "-n",
               "-f", "lavfi", "-i", "color=c=navy:s=160x284:r=30:d=2",
               "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=2",
               "-vf", "drawtext=text='DEMO':fontcolor=white:fontsize=28:x=(w-tw)/2:y=(h-th)/2",
               "-c:v", "libx264", "-threads", "1", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-ac", "2", "-b:a", "128k", "-t", "2", "-movflags", "+faststart",
               "-metadata", "title=DEMO ONLY - deliberately invalid production fixture", str(path)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=40)
    if result.returncode:
        raise Blocked("DEMO-Fixture-Encoding fehlgeschlagen: " + result.stderr[-1500:])
    return {"status": "GENERATED_DEMO_FIXTURE", "path": str(path), "sha256": digest(path),
            "profil": "160x284, 2 s, absichtlich kein MA-SHORT-Profil; keine InVideo-Produktion"}


@contextlib.contextmanager
def _demo_data(data_dir):
    previous = os.environ.get("MA_DATA_DIR")
    if data_dir is not None:
        os.environ["MA_DATA_DIR"] = str(Path(data_dir).expanduser().resolve())
    try:
        yield
    finally:
        if data_dir is not None:
            if previous is None:
                os.environ.pop("MA_DATA_DIR", None)
            else:
                os.environ["MA_DATA_DIR"] = previous


def run_demo(data_dir=None, *, with_video=True) -> dict:
    """Durchläuft echte Jobs/Gates/Freeze bis zum menschlichen Medienblocker.

    G0–G3 werden ausschließlich als DEMO-Simulation protokolliert. G4, G5a
    und G5b werden nicht gesetzt. Es gibt keinen Netzwerkzugriff oder Upload.
    """
    from . import gates, pipeline
    from .handoffs import youtube_handoff
    with _demo_data(data_dir):
        root, state = pipeline.new_project("DEMO – Kennzeichnung einer synthetischen lokalen Vorlage", beispiel=True)
        write_text(root / "DEMO_ONLY.md", "DEMO. Keine echte Episode, keine realen Freigaben, kein Upload.\n")
        events = []
        gates.approve(root, state, "G0", "DEMO-SIMULATION", demo_simulate=True)
        for gate in ("G1", "G2", "G3"):
            while True:
                result = pipeline.run(root, state)
                atomic_json(root / "state.json", state)
                events.append(copy.deepcopy(result))
                if result["status"] == "WAITING_FOR_CODEX":
                    job = state["jobs"][result["job_id"]]
                    write_role_fixture(root, state, job)
                    pipeline.complete_job(root, state, job["job_id"])
                    atomic_json(root / "state.json", state)
                    continue
                if result.get("gate") != gate:
                    raise Blocked(f"DEMO erwartet {gate}, erhalten: {result}")
                break
            gates.approve(root, state, gate, "DEMO-SIMULATION", demo_simulate=True)
            atomic_json(root / "state.json", state)
        handoff = pipeline.run(root, state)
        events.append(handoff)
        if handoff.get("blocked_at") != "G3_INVIDEO":
            raise Blocked("DEMO hat den manuellen InVideo-Handoff nicht erreicht.")
        fixture = {"status": "NOT_REQUESTED"}
        preview_result = None
        if with_video:
            preview = root / "08_produktion/inbox/preview.mp4"
            fixture = create_video_fixture(preview)
            if fixture["status"] == "GENERATED_DEMO_FIXTURE":
                preview_result = pipeline.run(root, state)
                events.append(preview_result)
                if preview_result.get("gate") != "G4":
                    raise Blocked("DEMO muss nach der echten synthetischen Datei bei G4 halten.")
                # Auch Final-QA/Handoff als isoliertes Testfixture prüfen; G4 bleibt gesperrt.
                final = root / "09_postproduktion/inbox/final.mp4"
                shutil.copyfile(preview, final)
                srt = root / "09_postproduktion/inbox/final.srt"
                write_text(srt, "1\n00:00:00,000 --> 00:00:01,000\nDEMO\n")
                pipeline.process_final(root, state, final, srt)
                youtube_handoff(root, state)
                for gate in ("G4", "G5a", "G5b"):
                    if gates.gate_valid(root, state, gate):
                        raise Blocked(f"DEMO darf keine Freigabe {gate} erzeugen.")
        atomic_json(root / "state.json", state)
        report = {"beispiel": True, "projekt_id": state["projekt_id"], "project_path": str(root),
                  "status": "DEMO_COMPLETE", "simulated_gates": ["G0", "G1", "G2", "G3"],
                  "human_gates_unapproved": ["G4", "G5a", "G5b"], "events": events,
                  "freeze_revision": state["freeze"]["revision"], "video_fixture": fixture,
                  "stopped_at": preview_result or handoff, "real_upload": False, "real_publication": False,
                  "explanation": "Deterministische synthetische Worker und QA; keine Webrecherche, keine menschliche Fachprüfung, kein InVideo-Render."}
        atomic_json(root / "DEMO_REPORT.json", report)
        return report
