"""Kurze Operator-Befehle; menschliche Entscheidungen nur interaktiv."""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import shutil
import sys
from pathlib import Path
import yaml

from . import __version__
from . import gates, pipeline
from .storage import (Blocked, atomic_json, current, data_root, digest, ensure_contained, ensure_project_storage, lock, now, object_hash,
                      project_path, read_json, repo_root, write_text)


def output(result):
    print(f"STATUS: {result.get('status', 'OK')}")
    if result.get("blocked_at"):
        print(f"BLOCKED_AT: {result['blocked_at']}")
    for key in ("gate", "role", "job_id", "job_path", "why"):
        if key in result:
            print(f"{key.upper()}: {result[key]}")
    if result.get("next"):
        print("\nNext:")
        for number, item in enumerate(result["next"], 1):
            print(f"{number}. {item}")


def terminal():
    if not sys.stdin.isatty():
        raise Blocked("Echte Bestätigung erfordert ein interaktives Operator-Terminal. Agenten dürfen diese Befehle nicht ausführen. Kein --yes und keine Pipe. DEMO nur --demo-simulate.")


def ask(label, *, required=True, default=None):
    value = input(label + (f" [{default}]" if default is not None else "") + ": ").strip()
    value = value or default
    if required and not value:
        raise Blocked("Pflichtangabe fehlt; keine Entscheidung gespeichert.")
    return value or ""


def yes(label) -> bool:
    value = ask(label + " (ja/nein)").casefold()
    if value not in ("ja", "nein"):
        raise Blocked("Bitte ausdrücklich ja oder nein eingeben; keine Entscheidung gespeichert.")
    return value == "ja"


def confirm(gate: str, binding: dict):
    token = object_hash(binding)[:12]
    print("\n" + gates.DESCRIPTIONS[gate])
    print("\nKonkrete Bindung:\n" + json.dumps(binding, ensure_ascii=False, indent=2))
    name = ask("Dein vollständiger Name")
    exact = f"FREIGABE {gate} {token}"
    if ask(f"Zur persönlichen Bestätigung exakt '{exact}' eingeben") != exact:
        raise Blocked("Bestätigung stimmt nicht; keine Freigabe gespeichert.")
    return name


def setup():
    terminal()
    print("G0-Konfiguration: reale Angaben eintragen. Dieses Setup ist noch keine Betriebsfreigabe.")
    config = {
        "verantwortliche_person": ask("Verantwortliche Person"),
        "umgebung": ask("Verwendete Umgebung (Gerät/OS/Codex-Dienst)"),
        "datenschutz": ask("Geprüfte Datenschutz-/Quellennutzungsregeln und zulässige Speicherung"),
        "speicherort": str(data_root()),
        "tools": ask("Tatsächlich verfügbare/geprüfte Werkzeuge und Einschränkungen"),
        "invideo_moeglichkeiten": ask("Tatsächliche InVideo-Möglichkeiten, Lizenz, Exportgrenzen und Kostenentscheidung"),
        "worker_mode": ask("Worker-Modus native_session oder codex_cli", default="native_session"),
        "web_recherche": yes("Reale Websuche UND Öffnen/Prüfen der Originalquellen verfügbar"),
    }
    if config["worker_mode"] not in ("native_session", "codex_cli"):
        raise Blocked("Worker-Modus ungültig.")
    path = data_root() / "operator.yaml"
    write_text(path, yaml.safe_dump(config, allow_unicode=True, sort_keys=False))
    print(f"Konfiguration: {path}\nPrüfe Rollenprompts und Regeln. Danach: ma approve G0")


def youtube_record(root: Path, state: dict):
    terminal()
    if state["beispiel"]:
        raise Blocked("DEMO führt keinen echten Upload-/Veröffentlichungsnachweis.")
    if not gates.gate_valid(root, state, "G5a"):
        raise Blocked("G5a fehlt oder ist veraltet.")
    name = ask("Name des Menschen, der die konkrete Datei privat hochgeladen hat")
    vid = ask("Tatsächliche YouTube-Video-ID (11 Zeichen)")
    url = ask("Tatsächliche URL")
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", vid) or url not in (f"https://www.youtube.com/watch?v={vid}", f"https://youtu.be/{vid}"):
        raise Blocked("Video-ID und reale YouTube-URL stimmen nicht überein.")
    if not yes("Video ist tatsächlich hochgeladen und ausschließlich privat"):
        raise Blocked("Nur ein tatsächliches privates Video ist zulässig.")
    if not yes("Uploaddatei ist exakt die durch G5a gebundene SHA-256-Datei"):
        raise Blocked("Falsche Uploaddatei.")
    ai_required = yes("KI-Kennzeichnung ist nach tatsächlichem Inhalt/Plattformregeln erforderlich")
    ai_set = yes("KI-Kennzeichnung auf YouTube tatsächlich gesetzt")
    if ai_required and not ai_set:
        raise Blocked("Erforderliche KI-Kennzeichnung fehlt.")
    kids = yes("Zielgruppe tatsächlich als für Kinder eingestuft")
    kids_reason = ask("Begründung der Zielgruppenentscheidung")
    ads = yes("Bezahlte Werbung/Produktplatzierung vorhanden")
    ads_set = yes("Werbekennzeichnung auf der Plattform tatsächlich gesetzt")
    if ads and not ads_set:
        raise Blocked("Erforderliche Werbekennzeichnung fehlt.")
    content = {"final_sha256": state["media"]["final"]["sha256"], "video_id": vid, "url": url, "sichtbarkeit": "private",
               "veroeffentlicht_am": None, "ki_kennzeichnung": {"erforderlich": ai_required, "gesetzt": ai_set, "nachweis": f"Reale Plattformentscheidung durch {name}, {now()}"},
               "zielgruppe": {"fuer_kinder": kids, "begruendung": kids_reason},
               "werbung": {"enthaelt_bezahlte_werbung": ads, "kennzeichnung_gesetzt": ads_set, "details": ask("Werbeentscheidung/Begründung")}}
    pipeline.generate(root, state, "A11", content, author=name, status="produziert")
    pipeline.stage_candidates(root, state, ["A11"])
    from .handoffs import playback_checklist
    playback_checklist(root, state)


def published(root: Path, state: dict):
    terminal()
    if state["beispiel"] or not gates.gate_valid(root, state, "G5b"):
        raise Blocked("Tatsächliches G5b für diese private Plattformfassung fehlt.")
    authorization = copy.deepcopy(state["gates"]["G5b"])
    name = ask("Name des Menschen, der das Video tatsächlich öffentlich gestellt hat")
    if not yes("Video ist jetzt tatsächlich öffentlich und vollständig erreichbar"):
        raise Blocked("Veröffentlichung nicht bestätigt.")
    content = copy.deepcopy(current(root, state, "A11")["inhalt"])
    content.update(sichtbarkeit="public", veroeffentlicht_am=now())
    pipeline.generate(root, state, "A11", content, author=name, status="veröffentlicht")
    state["publication"] = {"authorization": authorization, "artifact": state["artifacts"]["A11"], "operator": name, "time": now()}


def analytics(root: Path, state: dict, file: Path):
    root = ensure_project_storage(root)
    if not pipeline.publication_valid(root, state):
        raise Blocked("Tatsächliche Veröffentlichung noch nicht dokumentiert.")
    payload = read_json(file)
    source_hash = digest(file)
    dest = ensure_contained(root, root / "12_analytics" / f"input-{source_hash}.json")
    if not dest.exists():
        shutil.copyfile(file, dest)
    content = payload["inhalt"] if "inhalt" in payload else payload
    pipeline.generate(root, state, "A12", content, author="ANALYTICS – reale Dateiimporte")
    state.setdefault("analytics_imports", []).append({"time": now(), "path": str(dest.relative_to(root)), "sha256": source_hash,
                                                     "artifact": state["artifacts"]["A12"]})


def parser():
    p = argparse.ArgumentParser(prog="ma", description="MedizinAnders – lokale Codex-Pipeline mit echten menschlichen Gates")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("setup", help="Reale G0-Betreiberkonfiguration interaktiv erstellen")
    n = sub.add_parser("new", help="Neue Episode anlegen")
    n.add_argument("--thema")
    n.add_argument("--zielgruppe", default="Interessierte Erwachsene, ohne individuelle Beratung")
    n.add_argument("--demo", action="store_true")
    for cmd in ("run", "resume", "status", "validate"):
        c = sub.add_parser(cmd)
        c.add_argument("project")
        if cmd in ("run", "resume"):
            c.add_argument("--execute-workers", action="store_true")
            c.add_argument("--recheck-media", choices=["preview", "final"], help="Neue QA-Revision erzeugen und abhängige Freigaben invalidieren")
        if cmd == "status":
            c.add_argument("--json", action="store_true")
    a = sub.add_parser("approve", help="Konkreten Gate persönlich bestätigen")
    a.add_argument("gate", choices=["G0", *gates.GATE_ARTIFACTS])
    a.add_argument("--project")
    a.add_argument("--demo-simulate", action="store_true")
    a.add_argument("--name", help="Nur für ausdrücklich simulierte DEMO-Freigaben")
    r = sub.add_parser("review-record", help="Tatsächliche Fach-/Video-/Plattformprüfung dokumentieren")
    r.add_argument("project")
    r.add_argument("--kind", choices=list(gates.CHECKLISTS), required=True)
    r.add_argument("--media", choices=["preview", "final"])
    r.add_argument("--stage", choices=["claims", "production"], default="claims", help="Fachprüfung vor G2 oder des konkreten Skripts/Szenenplans vor G3")
    r.add_argument("--demo-simulate", action="store_true")
    i = sub.add_parser("import", help="Geprüfte neue Artefaktversion mit exakten Abhängigkeiten importieren")
    i.add_argument("project")
    i.add_argument("--file", type=Path, required=True)
    i.add_argument("--bump", choices=["patch", "minor", "major"])
    c = sub.add_parser("worker-complete")
    c.add_argument("project")
    c.add_argument("--job", required=True)
    inv = sub.add_parser("invalidate")
    inv.add_argument("project")
    inv.add_argument("--change", choices=list(pipeline.CHANGE_ROUTES), required=True)
    inv.add_argument("--reason", required=True)
    for cmd in ("youtube-record", "published"):
        c = sub.add_parser(cmd)
        c.add_argument("project")
    a = sub.add_parser("analytics")
    a.add_argument("project")
    a.add_argument("--file", type=Path, required=True)
    d = sub.add_parser("demo", help="Synthetischen vollständigen DEMO-Durchlauf ausführen")
    d.add_argument("--data-dir", type=Path)
    d.add_argument("--without-video", action="store_true")
    sub.add_parser("doctor", help="Tatsächlich lokal verfügbare Werkzeuge anzeigen")
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "setup":
            with lock(data_root() / ".operator.lock"):
                setup()
            return 0
        if args.command == "doctor":
            print(json.dumps({"version": __version__, "repository": str(repo_root()), "data": str(data_root()),
                              "tools": {tool: shutil.which(tool) for tool in ("codex", "git", "gh", "ffmpeg", "ffprobe")},
                              "web_search": "Durch realen Codex-Host bei G0 zu bestätigen", "invideo": "manuell", "youtube": "manuell"}, ensure_ascii=False, indent=2))
            return 0
        if args.command == "demo":
            from .demo import run_demo
            result = run_demo(args.data_dir, with_video=not args.without_video)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "new":
            if args.thema:
                thema = args.thema
                zeitlimit = "Vor G1 konkret festlegen"
                kostenlimit = "Keine Kosten ohne persönliche G3-Entscheidung"
            else:
                terminal()
                thema = ask("Themenidee")
                zeitlimit = ask("Zeitlimit für Recherche/Produktion", default="2 Stunden Recherche, Produktion separat prüfen")
                kostenlimit = ask("Kostenlimit", default="0 EUR bis persönlicher Produktionsfreigabe")
            root, state = pipeline.new_project(thema, beispiel=args.demo, zielgruppe=args.zielgruppe, zeitlimit=zeitlimit, kostenlimit=kostenlimit)
            print(f"Projekt: {state['projekt_id']}\nLokaler Speicher: {root}")
            result = pipeline.run(root, state)
            atomic_json(root / "state.json", state)
            output(result)
            return 0
        if args.command == "approve" and args.gate == "G0" and not args.demo_simulate:
            terminal()
            if args.name:
                raise Blocked("--name ist nur für DEMO erlaubt.")
            with lock(data_root() / ".operator.lock"):
                config = gates.operator_config()
                binding = {"policy": pipeline.policy_hash(), "operator_sha256": digest(data_root() / "operator.yaml")}
                print(yaml.safe_dump(config, allow_unicode=True))
                name = confirm("G0", binding)
                gates.approve(None, None, "G0", name)
            print("G0 dokumentiert. Eine neue Episode starten: ma new")
            return 0
        project = getattr(args, "project", None)
        if not project:
            raise Blocked("--project ist erforderlich.")
        root = project_path(project)
        with lock(root / ".state.lock"):
            state = read_json(root / "state.json")
            try:
                if args.command in ("run", "resume"):
                    result = pipeline.run(root, state, execute=args.execute_workers, recheck_media=args.recheck_media)
                    state["last_status"] = result
                    output(result)
                elif args.command == "status":
                    info = {"project": project, "beispiel": state["beispiel"], "artifacts": state["artifacts"],
                                      "gates": {g: gates.gate_valid(root, state, g) for g in ("G0", *gates.GATE_ARTIFACTS)},
                                      "freeze": state["freeze"], "publication": pipeline.publication_valid(root, state)}
                    if args.json:
                        print(json.dumps(info, ensure_ascii=False, indent=2))
                    else:
                        print(f"Projekt: {project}{' (DEMO)' if state['beispiel'] else ''}")
                        print("Gates: " + ", ".join(f"{g}={'gültig' if v else 'offen/veraltet'}" for g, v in info["gates"].items()))
                        result = {"status": "READY", "why": "Nächsten Schritt anhand des aktuellen Zustands ermitteln.", "next": [f"ma resume {project}"]}
                        if not info["gates"]["G0"]:
                            result = pipeline.wait("G0", "Betriebsfreigabe fehlt oder ist veraltet.", ["ma setup", "ma approve G0"])
                        output(result)
                elif args.command == "approve":
                    if args.demo_simulate:
                        if not state["beispiel"]:
                            raise Blocked("Kein DEMO-Projekt; Simulation verboten.")
                        name = args.name or "DEMO – simulierter Operator"
                    else:
                        terminal()
                        if args.name:
                            raise Blocked("--name ist nur für DEMO erlaubt.")
                        binding = gates.prerequisites(root, state, args.gate)
                        name = confirm(args.gate, binding)
                    gates.approve(root, state, args.gate, name, demo_simulate=args.demo_simulate)
                    print(f"{'DEMO-SIMULATION' if args.demo_simulate else 'PERSÖNLICHE FREIGABE'}: {args.gate}. Weiter: ma resume {project}")
                elif args.command == "review-record":
                    media_kind = args.media or ("preview" if args.kind == "preview" else "final")
                    technical_evidence = {}
                    if args.demo_simulate:
                        if not state["beispiel"]:
                            raise Blocked("Keine Review-Simulation in Produktion.")
                        name, qualification, evidence = "DEMO – simulierter Reviewer", "DEMO – keine reale Qualifikation", "DEMO – nur synthetischer Ablaufnachweis"
                        checks = {c: True for c in gates.CHECKLISTS[args.kind]}
                        if args.kind == "technical":
                            technical_evidence = {name: "DEMO: expliziter simulierter Einzelbeleg, keine Messung" for name in gates.missing_technical_checks(root, state, media_kind)}
                        decision = "approved"
                    else:
                        terminal()
                        print(json.dumps(gates.review_binding(root, state, args.kind, media_kind, stage=args.stage), ensure_ascii=False, indent=2))
                        print("Nur die tatsächlich erfolgte Prüfung dokumentieren. Ungeprüfte Punkte bleiben Blocker.")
                        name = ask("Vollständiger Name der tatsächlichen prüfenden Person")
                        qualification = ask("Tatsächliche Fachqualifikation", required=args.kind in ("medical", "legal", "technical"))
                        evidence = ask("Konkreter Nachweis der realen Prüfung (Datum/Dokument/Fundstellen)")
                        checks = {c: yes(c + ": tatsächlich geprüft und bestanden") for c in gates.CHECKLISTS[args.kind]}
                        if args.kind == "technical":
                            technical_evidence = {name: ask(f"Tatsächlicher fachlicher Einzelbeleg für {name}") for name in gates.missing_technical_checks(root, state, media_kind)}
                        decision = "approved" if all(checks.values()) else "rejected"
                        if not yes(f"Die Dokumentation als {decision} ist wahrheitsgemäß"):
                            raise Blocked("Review nicht gespeichert.")
                    gates.record_review(root, state, args.kind, name=name, qualification=qualification, evidence=evidence,
                                        checklist=checks, decision=decision, demo_simulate=args.demo_simulate, which=media_kind, stage=args.stage, technical_evidence=technical_evidence)
                    print("Prüfung dokumentiert. Weiter: ma resume " + project)
                elif args.command == "worker-complete":
                    pipeline.complete_job(root, state, args.job)
                    print("Worker-Output validiert und versioniert. Weiter: ma resume " + project)
                elif args.command == "import":
                    pipeline.put_artifact(root, state, read_json(args.file), bump=args.bump)
                    print("Artefakt importiert; abhängige Artefakte und Freigaben invalidiert.")
                elif args.command == "invalidate":
                    pipeline.invalidate_change(root, state, args.change, args.reason)
                    print("Rückweg angewendet. Weiter: ma resume " + project)
                elif args.command == "validate":
                    print(json.dumps(pipeline.preflight(root, state), ensure_ascii=False, indent=2))
                    if state["freeze"]:
                        pipeline.verify_freeze(root, state)
                elif args.command == "youtube-record":
                    youtube_record(root, state)
                    print("Tatsächlicher privater Upload dokumentiert. Weiter: ma resume " + project)
                elif args.command == "published":
                    published(root, state)
                    print("Menschliche tatsächliche Veröffentlichung dokumentiert.")
                elif args.command == "analytics":
                    analytics(root, state, args.file)
                    print("A12 aus tatsächlichem Dateiimport erzeugt; keine dauerhaften Regeländerungen.")
            finally:
                atomic_json(root / "state.json", state)
        return 0
    except (Blocked, OSError, ValueError, KeyError) as error:
        output({"status": "BLOCKED", "why": str(error), "next": ["Blocker anhand des genannten Artefakts/Reports klären; Dateien niemals im Freeze überschreiben."]})
        return 2
    except (KeyboardInterrupt, EOFError):
        print("Abgebrochen; keine angefragte menschliche Entscheidung gespeichert.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
