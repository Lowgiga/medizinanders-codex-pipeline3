"""Menschliche, konkrete Freigaben. CLI übernimmt die interaktive Identitätsbestätigung."""
from __future__ import annotations

import copy
import re
from pathlib import Path
import yaml

from .storage import Blocked, atomic_json, current, data_root, digest, ensure_project_storage, now, object_hash, read_json
from .validation import dependency_check, preflight, qa_check, schema_check

GATE_ARTIFACTS = {"G1": ["A01"], "G2": ["A01", "A02", "A03"],
                  "G3": [f"A{i:02d}" for i in range(1, 8)], "G4": ["A06", "A07", "A08"],
                  "G5a": ["A05", "A06", "A08", "A09", "A10"], "G5b": ["A09", "A10", "A11"]}
PREVIOUS = {"G1": "G0", "G2": "G1", "G3": "G2", "G4": "G3", "G5a": "G4", "G5b": "G5a"}
DESCRIPTIONS = {
    "G0": "Ich übernehme den Betrieb für die konkret konfigurierte Umgebung, Datenschutz, Speicherorte, Werkzeuge und Rollenprompts. Tatsächliche InVideo-Möglichkeiten sind geprüft.",
    "G1": "Ich bestätige Kernfrage, Scope, Zielgruppe, Suchfragen und konkrete Ressourcen. Erst diese Freigabe erlaubt die Recherche.",
    "G2": "Ich habe alle verwendbaren Claims, Originalfundstellen, Gegenbelege, Einschränkungen und Risiken geprüft. Anwendbare echte medizinische/juristische Fachreviews liegen vor.",
    "G3": "Ich bestätige die konkrete Freeze-Revision, A01–A07, Preflight, Rechte und den InVideo-Auftrag. Kosten akzeptiere ich persönlich vor Ausführung. Erst jetzt darf InVideo manuell gestartet werden.",
    "G4": "Ich habe diese tatsächliche Vorschau einschließlich Smartphone-/Hörprüfung geprüft. Stimme, Zahlen, Negationen, Quellen, Bilder, Untertitel, Disclaimer und Synchronisation entsprechen dem Freeze.",
    "G5a": "Ich habe diese konkrete Finaldatei mit SHA-256, SRT, QA und Uploadpaket geprüft. Diese Freigabe erlaubt ausschließlich einen manuellen privaten Upload.",
    "G5b": "Ich habe das verarbeitete private Plattformvideo tatsächlich vollständig geprüft. Video-ID, Sichtbarkeit, Metadaten und Kennzeichnung stimmen. Ich entscheide persönlich über die manuelle Veröffentlichung.",
}
CHECKLISTS = {
    "medical": ["Originalquellen/Fundstellen und Studienparameter tatsächlich geprüft", "Wirksamkeit/Schaden/Diagnostik/Therapie/Dosierung/Prognose geprüft", "Geplante Formulierungen, Unsicherheiten und Gesundheitsentscheidungsrisiken geprüft"],
    "legal": ["Identifizierbare Personen/Unternehmen und Vorwürfe geprüft", "Bild-/Musik-/Stimm-/Zitatrechte und Datenschutz tatsächlich geprüft", "Betroffene Claims/Assets und geplante Formulierungen rechtlich geprüft"],
    "preview": ["Echte Datei vollständig angesehen und angehört", "Echte Smartphone-Prüfung durchgeführt", "Sprechertext, Zahlen, Einheiten, Namen, Aussprache und Negationen gegen Freeze geprüft", "Bilder/Rechte/KI-Illustrationen, Untertitel/Lesbarkeit/Sync höchstens100ms geprüft", "Genau eine CTA, harter Schnitt3s, Ausklang und Disclaimer54–58s exklusiv/schwarz/stumm geprüft", "Musik18dB unter Stimme (15–21dB) aus getrennten Spuren belegt oder Musik entfernt"],
    "final": ["Konkrete Finaldatei vollständig angesehen und angehört", "Echte Smartphone-Prüfung dieser Finaldatei durchgeführt", "Freeze-Text, Zahlen, Negationen, Aussprache und Originalbezüge geprüft", "Eingebrannte MontserratBold52px Untertitel,840pxBreite,Layout,Lesbarkeit und Sync höchstens100ms geprüft", "Genau eine CTA, Schnitt3s, Disclaimer54–58s exklusiv/schwarz/stumm geprüft", "Musikabstand belegt oder Musik entfernt", "SRT mit tatsächlicher Sprache und eingebrannter Fassung identisch", "Uploadtitel, Beschreibung, Thumbnail, Kennzeichnung, Zielgruppe und Werbung bewusst entschieden"],
    "playback": ["Tatsächlich verarbeitete private YouTube-Fassung vollständig angesehen und angehört", "Video-ID/URL/Sichtbarkeit private stimmen", "Bild, Ton, Untertitel/Sync, Disclaimer, Metadaten und Thumbnail auf Plattform geprüft", "KI-Kennzeichnung, Zielgruppe und Werbung auf tatsächlicher Plattform kontrolliert"],
    "technical": ["Jede ausdrücklich nicht_geprueft technische Pflichtprüfung durch reale nachvollziehbare Nachweise ergänzt"],
}


def operator_config() -> dict:
    path = data_root() / "operator.yaml"
    if not path.is_file():
        raise Blocked("Operator-Konfiguration fehlt: ma setup")
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    required = ("verantwortliche_person", "umgebung", "datenschutz", "speicherort", "tools", "invideo_moeglichkeiten", "worker_mode", "web_recherche")
    if not isinstance(config, dict) or any(k not in config for k in required):
        raise Blocked("Operator-Konfiguration unvollständig.")
    for k in required[:6]:
        if not config[k] or "STANDARDVORSCHLAG" in str(config[k]) or "OFFEN" in str(config[k]).upper() or "PLACEHOLDER" in str(config[k]).upper():
            raise Blocked(f"G0-Betreiberentscheidung noch offen: {k}")
    if config["worker_mode"] not in ("native_session", "codex_cli") or not isinstance(config["web_recherche"], bool):
        raise Blocked("Worker-Modus oder Web-Recherche-Fähigkeit ungültig.")
    return config


def operating_valid(state: dict) -> bool:
    from .pipeline import policy_hash
    if state["beispiel"]:
        record = state["gates"].get("G0")
        return bool(record and record.get("simulated") and record.get("binding", {}).get("policy") == policy_hash())
    try:
        operator_config()
        record = read_json(data_root() / "G0.json")
        return (not record["simulated"] and record["binding"] == {"policy": policy_hash(), "operator_sha256": digest(data_root() / "operator.yaml")})
    except (OSError, KeyError, ValueError, Blocked):
        return False


def review_requirements(root: Path, state: dict, *, stage="claims") -> list[str]:
    if "A03" not in state["artifacts"]:
        return []
    a03 = current(root, state, "A03")["inhalt"]
    used = [c for c in a03["claims"] if c["einsatz"] != "nein"]
    # Conservative clinical escalation even when an agent incorrectly sets its boolean to false.
    clinical = re.compile(r"wirksam|wirkung|schad|diagnos|therap|dosier|prognos|nebenwirkung|behandel|heilung|mortal|krank|blutdruck|blutzucker|glukose|cholesterin|insulin|impf|krebs|tumor|symptom|antibiot|medikament|schmerz|sterb|überleben|infekt|herz|lunge|niere", re.I)
    required = set()
    if any(c["medizinisch"] or clinical.search(c["aussage"]) for c in used) or any(r["medizinischer_review"] for r in a03["risiken"]):
        required.add("medical")
    if any(c["rechtsrelevant"] for c in used) or any(r["juristischer_review"] for r in a03["risiken"]):
        required.add("legal")
    if stage == "production" and "A06" in state["artifacts"] and any(a["rechte_status"] != "geklaert" for a in current(root, state, "A06")["inhalt"]["assets"]):
        required.add("legal")
    return sorted(required)


def media_binding(root: Path, state: dict, which: str) -> dict:
    media = state["media"].get(which)
    if not media:
        raise Blocked(f"Echte {which}-Datei fehlt.")
    result = copy.deepcopy(media)
    for pkey, hkey in (("path", "sha256"), ("report", "report_sha256"), ("srt_path", "srt_sha256"), ("srt_report", "srt_report_sha256")):
        if pkey in media:
            path = (root / media[pkey]).resolve()
            if root.resolve() not in path.parents or not path.is_file() or digest(path) != media[hkey]:
                raise Blocked(f"{which}: Datei oder Report verändert. ma resume ausführen; erneut prüfen/freigeben.")
    return result


def review_binding(root: Path, state: dict, kind: str, which=None, *, stage="claims") -> dict:
    from .pipeline import policy_hash
    if kind in ("medical", "legal"):
        aids = ["A01", "A02", "A03"]
        if stage == "production":
            aids += ["A04", "A05", "A06"]
        elif stage != "claims":
            raise Blocked("Fachreview-Stufe muss claims oder production sein.")
        for aid in aids:
            current(root, state, aid)
        return {"policy": policy_hash(), "stage": stage, "artifacts": [state["artifacts"][a] for a in aids]}
    if kind in ("preview", "final", "technical"):
        which = which or ("preview" if kind == "preview" else "final")
        return {"policy": policy_hash(), "media": media_binding(root, state, which), "freeze": state["freeze"]}
    if kind == "playback":
        current(root, state, "A11")
        return {"policy": policy_hash(), "artifact": state["artifacts"]["A11"], "G5a": state["gates"].get("G5a")}
    raise Blocked("Unbekannte Review-Art.")


def review_valid(root: Path, state: dict, kind: str, which=None, *, stage="claims") -> bool:
    key = kind + (f"-{which}" if kind == "technical" else "") + ("-production" if kind in ("medical", "legal") and stage == "production" else "")
    info = state["reviews"].get(key)
    if not info:
        return False
    try:
        record = read_json(root / info["path"])
        if kind == "technical":
            required = missing_technical_checks(root, state, which or "final")
            if set(record.get("technical_evidence", {})) != set(required) or any(not value.strip() for value in record.get("technical_evidence", {}).values()):
                return False
        return (digest(root / info["path"]) == info["sha256"] and record["binding"] == review_binding(root, state, kind, which, stage=stage)
                and record["decision"] == "approved" and record["simulated"] == state["beispiel"]
                and all(record["checklist"].get(c) is True for c in CHECKLISTS[kind]))
    except (OSError, ValueError, KeyError, Blocked):
        return False


def record_review(root: Path, state: dict, kind: str, *, name: str, qualification: str, evidence: str,
                  checklist: dict, decision="approved", demo_simulate=False, which=None, stage="claims", technical_evidence=None):
    root = ensure_project_storage(root)
    if state["beispiel"] != demo_simulate:
        raise Blocked("DEMO-Review und produktiver Review strikt getrennt; nur DEMO darf simuliert werden.")
    if not name.strip() or not evidence.strip() or kind not in CHECKLISTS:
        raise Blocked("Identität und konkreter Nachweis sind erforderlich.")
    if kind in ("medical", "legal", "technical") and not qualification.strip():
        raise Blocked("Reale Fachqualifikation muss dokumentiert sein.")
    if set(checklist) != set(CHECKLISTS[kind]) or any(not isinstance(x, bool) for x in checklist.values()):
        raise Blocked("Review-Checkliste ist unvollständig.")
    if decision not in ("approved", "rejected"):
        raise Blocked("Review-Entscheidung ungültig.")
    if decision == "approved" and not all(checklist.values()):
        raise Blocked("Eine unvollständige Prüfung kann nicht bestätigt werden.")
    which = which or ("preview" if kind == "preview" else "final")
    if kind == "technical" and decision == "approved":
        required = missing_technical_checks(root, state, which)
        if set(technical_evidence or {}) != set(required) or any(not isinstance(v, str) or not v.strip() for v in (technical_evidence or {}).values()):
            raise Blocked("Jede konkrete nicht_geprueft technische Prüfung benötigt einen eigenen tatsächlichen Nachweis.")
    key = kind + (f"-{which}" if kind == "technical" else "") + ("-production" if kind in ("medical", "legal") and stage == "production" else "")
    binding = review_binding(root, state, kind, which, stage=stage)
    record = {"kind": kind, "name": name, "qualification": qualification, "evidence": evidence, "decision": decision,
              "time": now(), "binding": binding, "checklist": checklist, "simulated": demo_simulate,
              "beispiel": state["beispiel"], "projekt_id": state["projekt_id"]}
    if kind == "technical":
        record["technical_evidence"] = technical_evidence or {}
    directory = root / "review" / "records" / key
    path = directory / f"{len(list(directory.glob('*.json'))) + 1:04d}.json"
    atomic_json(path, record, exclusive=True)
    state["reviews"][key] = {"path": str(path.relative_to(root)), "sha256": digest(path)}
    # Review corrections explicitly revoke gates that bound the prior review.
    for gate in list(state["gates"]):
        if gate != "G0" and not gate_valid(root, state, gate):
            state["gates"].pop(gate, None)
    return record


def missing_technical_checks(root: Path, state: dict, which: str) -> list[str]:
    binding = media_binding(root, state, which)
    paths = [("video", binding["report"])]
    if which == "final":
        paths.append(("srt", binding["srt_report"]))
    return [prefix + ":" + c["name"] for prefix, path in paths for c in read_json(root / path).get("pflichtpruefungen", []) if c["status"] == "nicht_geprueft"]


def require_media_qa(root: Path, state: dict, which: str):
    binding = media_binding(root, state, which)
    reports = [read_json(root / binding["report"])]
    if which == "final":
        reports.append(read_json(root / binding["srt_report"]))
    for report in reports:
        checks = report.get("pflichtpruefungen", [])
        if not checks:
            raise Blocked("Technische Pflichtprüfungen fehlen.")
        if any(c["status"] == "fehlgeschlagen" for c in checks):
            raise Blocked("Messbare technische K1-Fehler müssen nachvollziehbar korrigiert werden; kein Review-Override.")
        missing = [c["name"] for c in checks if c["status"] == "nicht_geprueft"]
        if missing and not review_valid(root, state, "technical", which):
            raise Blocked(f"Technische Prüfungen unvollständig ({', '.join(missing)}). Reale Nachweise: ma review-record --kind technical --media {which}")
        for finding in report.get("findings", []):
            if finding.get("offen", True) and finding.get("schwere") in ("K0", "K1"):
                # Only the exact missing-measurement finding can be complemented.
                complemented = (finding["schwere"] == "K1" and finding.get("problem") in
                                {f"{name}: Prüfung nicht vollständig möglich." for name in missing})
                if not complemented:
                    raise Blocked("Technische QA hat einen unabhängigen offenen K0/K1-Blocker; Fachnachweis ersetzt ihn nicht.")


def gate_binding(root: Path, state: dict, gate: str) -> dict:
    from .pipeline import policy_hash, verify_freeze
    for aid in GATE_ARTIFACTS[gate]:
        artifact = current(root, state, aid)
        schema_check(artifact)
        dependency_check(root, state, artifact)
    previous = PREVIOUS[gate]
    prior = state["gates"].get(previous) if previous != "G0" or state["beispiel"] else read_json(data_root() / "G0.json")
    binding = {"policy": policy_hash(), "artifacts": [state["artifacts"][a] for a in GATE_ARTIFACTS[gate]],
               "previous": object_hash(prior) if prior else None}
    if gate in ("G2", "G3"):
        binding["reviews"] = {kind: state["reviews"].get(kind) for kind in review_requirements(root, state)}
    if gate == "G3":
        verify_freeze(root, state)
        binding["freeze"] = state["freeze"]
        binding["handoff"] = directory_hashes(root / "handoff" / "invideo")
        binding["production_reviews"] = {kind: state["reviews"].get(kind + "-production") for kind in review_requirements(root, state, stage="production")}
    if gate in ("G4", "G5a"):
        which = "preview" if gate == "G4" else "final"
        binding["media"] = media_binding(root, state, which)
        binding["review"] = state["reviews"].get(which)
        binding["technical"] = state["reviews"].get(f"technical-{which}")
    if gate == "G5a":
        binding["handoff"] = directory_hashes(root / "handoff" / "youtube", exclude={"PRIVATE_PLAYBACK_CHECKLIST.md"})
    if gate == "G5b":
        binding["playback"] = state["reviews"].get("playback")
    return binding


def directory_hashes(directory: Path, exclude=None) -> dict:
    return {str(p.relative_to(directory)): digest(p) for p in sorted(directory.rglob("*")) if p.is_file() and p.name not in (exclude or set())}


def gate_valid(root: Path, state: dict, gate: str) -> bool:
    if gate == "G0":
        return operating_valid(state)
    record = state["gates"].get(gate)
    if not record or record.get("simulated") != state["beispiel"]:
        return False
    try:
        # Re-evaluate physical review evidence as well as immutable binding metadata.
        if record.get("record_path"):
            saved = read_json(root / record["record_path"])
            if saved != {k: v for k, v in record.items() if k != "record_path"}:
                return False
        return record["binding"] == prerequisites(root, state, gate)
    except (OSError, ValueError, KeyError, Blocked):
        return False


def prerequisites(root: Path, state: dict, gate: str):
    from .pipeline import evidence_validate, verify_freeze
    if gate not in GATE_ARTIFACTS:
        raise Blocked("Unbekannter Gate.")
    if not gate_valid(root, state, PREVIOUS[gate]):
        raise Blocked(f"Voraussetzung {PREVIOUS[gate]} fehlt/ist veraltet.")
    binding = gate_binding(root, state, gate)
    if gate == "G1":
        a01 = current(root, state, "A01")["inhalt"]
        resources = a01["ressourcen"]
        if a01["offene_entscheidungen"] or resources["zeitbudget_stunden"] is None or resources["budget_eur"] is None or not resources["werkzeuge"] or not resources["verantwortliche"]:
            raise Blocked("G1: konkrete Zeit-/Kostenlimits, Werkzeuge, Verantwortliche und offene Entscheidungen fehlen.")
        if a01["format"]["dauer_sekunden"] != 58 or a01["format"]["seitenverhaeltnis"] != "9:16":
            raise Blocked("G1: V1 unterstützt ausschließlich das 58-s-9:16-Standardprofil.")
    if gate in ("G2", "G3"):
        evidence_validate(root, state)
        protocols = current(root, state, "A02")["inhalt"]["suchprotokoll"]
        if not protocols or not any(p["gegenbelege_gesucht"] and p["zeitpunkt"] for p in protocols) or not any(p["retraktionen_geprueft"] and p["zeitpunkt"] for p in protocols):
            raise Blocked("G2: explizite Gegenbelegsuche und Korrektur-/Retraktionsprüfung mit tatsächlichem Protokoll fehlen.")
        for kind in review_requirements(root, state):
            if not review_valid(root, state, kind):
                raise Blocked(f"Echter {kind}-Fachreview fehlt oder ist veraltet.")
        for risk in current(root, state, "A03")["inhalt"]["risiken"]:
            if risk["offen"] and risk["klasse"] in ("K0", "K1") and not (risk["medizinischer_review"] or risk["juristischer_review"]):
                raise Blocked(f"Offener Blocker {risk['risiko_id']}: {risk['beschreibung']}")
    if gate == "G3":
        for kind in review_requirements(root, state, stage="production"):
            if not review_valid(root, state, kind, stage="production"):
                raise Blocked(f"Echter {kind}-Fachreview des konkreten Skripts/Szenenplans fehlt: ma review-record --kind {kind} --stage production")
        preflight(root, state)
        verify_freeze(root, state)
        a07 = current(root, state, "A07")["inhalt"]
        qa_check(a07["preflight"])
        qa_check(a07["qa"])
        if not binding["handoff"]:
            raise Blocked("InVideo-Handoff fehlt.")
        frozen = root / "freeze" / state["freeze"]["revision"] / "invideo"
        if directory_hashes(frozen) != binding["handoff"]:
            raise Blocked("InVideo-Handoff weicht vom Freeze ab.")
    if gate in ("G4", "G5a"):
        which = "preview" if gate == "G4" else "final"
        media = media_binding(root, state, which)
        if gate == "G4":
            a08 = current(root, state, "A08")["inhalt"]
            if a08["preview_sha256"] != media["sha256"] or a08["preview_pfad"] != media["path"]:
                raise Blocked("A08 verweist nicht auf die tatsächlich geprüfte Vorschau.")
        else:
            a09, a10 = [current(root, state, aid)["inhalt"] for aid in ("A09", "A10")]
            if a09["final_sha256"] != media["sha256"] or a09["final_pfad"] != media["path"] or a09["srt_sha256"] != media["srt_sha256"] or a09["srt_pfad"] != media["srt_path"]:
                raise Blocked("A09 verweist nicht auf die tatsächlich geprüfte Final-/SRT-Datei.")
            if a10["datei_sha256"] != media["sha256"] or a10["technischer_report"].get("datei_sha256") != media["sha256"] or a10["technischer_report"] != read_json(root / media["report"]):
                raise Blocked("A10 bezieht sich nicht auf den tatsächlichen technischen Finalreport.")
            qa_check(a10["qa"])
        require_media_qa(root, state, which)
        if not review_valid(root, state, which):
            raise Blocked(f"Echte {which}-Inhalts-/Smartphone-/Hörprüfung fehlt.")
    if gate == "G5b":
        a11 = current(root, state, "A11")["inhalt"]
        if a11["sichtbarkeit"] != "private" or not a11["video_id"] or not a11["url"]:
            raise Blocked("Konkretes tatsächliches privates Plattformvideo fehlt.")
        if a11["final_sha256"] != state["media"]["final"]["sha256"]:
            raise Blocked("Plattformnachweis bezieht sich auf die falsche Finaldatei.")
        if any(a11["ki_kennzeichnung"][k] is None for k in ("erforderlich", "gesetzt")) or a11["zielgruppe"]["fuer_kinder"] is None or any(a11["werbung"][k] is None for k in ("enthaelt_bezahlte_werbung", "kennzeichnung_gesetzt")):
            raise Blocked("KI-/Zielgruppen-/Werbeentscheidungen sind noch offen.")
        if a11["ki_kennzeichnung"]["erforderlich"] and not a11["ki_kennzeichnung"]["gesetzt"] or a11["werbung"]["enthaelt_bezahlte_werbung"] and not a11["werbung"]["kennzeichnung_gesetzt"]:
            raise Blocked("Erforderliche Plattformkennzeichnung fehlt.")
        if not review_valid(root, state, "playback"):
            raise Blocked("Echte Prüfung der verarbeiteten privaten Plattformfassung fehlt.")
    return binding


def approve(root: Path | None, state: dict | None, gate: str, name: str, *, demo_simulate=False):
    from .pipeline import policy_hash, stage_candidates
    if root is not None:
        root = ensure_project_storage(root)
    if not name.strip():
        raise Blocked("Name ist erforderlich.")
    if gate == "G0":
        if demo_simulate:
            if not state or not state["beispiel"]:
                raise Blocked("Simulierte G0 nur in DEMO.")
            record = {"gate": gate, "name": name, "time": now(), "simulated": True,
                      "binding": {"policy": policy_hash()}, "beispiel": True}
            state["gates"][gate] = record
            return record
        operator_config()
        record = {"gate": gate, "name": name, "time": now(), "simulated": False, "beispiel": False,
                  "binding": {"policy": policy_hash(), "operator_sha256": digest(data_root() / "operator.yaml")}}
        history = data_root() / "gates" / "G0"
        atomic_json(history / f"{len(list(history.glob('*.json'))) + 1:04d}.json", record, exclusive=True)
        atomic_json(data_root() / "G0.json", record)
        return record
    if state is None or root is None or state["beispiel"] != demo_simulate:
        raise Blocked("DEMO-Freigaben dürfen ausschließlich simuliert werden; Produktionsfreigaben niemals.")
    # run() prepares immutable candidate versions before a human sees/approves them.
    if any(int(current(root, state, a)["version"].split(".")[0]) == 0 for a in GATE_ARTIFACTS[gate] if a in ("A01", "A03", "A04", "A05", "A06", "A07")):
        raise Blocked("Freigabekandidaten fehlen. Zuerst ma run/ma resume ausführen.")
    binding = prerequisites(root, state, gate)
    record = {"gate": gate, "name": name, "time": now(), "simulated": demo_simulate, "beispiel": state["beispiel"],
              "projekt_id": state["projekt_id"], "description": DESCRIPTIONS[gate], "binding": binding}
    directory = root / "gates" / gate
    path = directory / f"{len(list(directory.glob('*.json'))) + 1:04d}.json"
    atomic_json(path, record, exclusive=True)
    state["gates"][gate] = record | {"record_path": str(path.relative_to(root))}
    return record
