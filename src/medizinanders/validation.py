"""Schema-, Abhängigkeits- und Inhaltsprüfungen. Semantik bleibt unabhängige QA."""
from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker

from .storage import Blocked, canonical, current, read_json, repo_root

DEPENDENCIES = {
    "A01": [], "A02": ["A01"], "A03": ["A01", "A02"], "A04": ["A03"],
    "A05": ["A03", "A04"], "A06": ["A03", "A04", "A05"],
    "A07": ["A01", "A02", "A03", "A04", "A05", "A06"],
    "A08": ["A06", "A07"], "A09": ["A08", "A05", "A06"],
    "A10": ["A09"], "A11": ["A09", "A10"], "A12": ["A11"],
}
DISCLAIMER = "Journalistischer Analyse-Content. Kein medizinischer Rat."
PHASES = [("hook", 0, 3), ("open_loop", 3, 8), ("payload", 8, 41),
          ("verdichtung", 41, 48), ("cta", 48, 52), ("ausklang", 52, 54), ("disclaimer", 54, 58)]
RED_TEAM_CHECKS = {"factuality", "claim_mapping", "rights", "medical_legal", "production", "context_integrity"}


def schema_check(artifact: dict):
    try:
        canonical(artifact)
    except (ValueError, TypeError) as error:
        raise Blocked("Artefakt enthält nicht-JSON-konforme Werte (z.B. NaN/Infinity).") from error
    aid = artifact.get("artefakt_id")
    if aid not in DEPENDENCIES:
        raise Blocked("Unbekanntes Artefakt.")
    schema = read_json(repo_root() / "schemas" / f"{aid}.schema.json")
    problems = sorted(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(artifact), key=lambda x: str(x.path))
    if problems:
        error = problems[0]
        raise Blocked(f"{aid} Schemafehler bei {'/'.join(map(str, error.path))}: {error.message}")
    if artifact["gesperrt"]:
        raise Blocked(f"{aid} gesperrt: {artifact['sperrgrund']}")
    if artifact["offene_punkte"]:
        raise Blocked(f"{aid}: offene Punkte müssen vor produktivem Einsatz geklärt werden.")


def dependency_check(root: Path, state: dict, artifact: dict):
    actual = artifact["eingaben"]
    expected = [state["artifacts"].get(aid) for aid in DEPENDENCIES[artifact["artefakt_id"]]]
    if any(x is None for x in expected) or actual != expected:
        raise Blocked(f"{artifact['artefakt_id']}: veraltete oder unvollständige Abhängigkeiten.")
    if artifact["projekt_id"] != state["projekt_id"] or artifact["beispiel"] != state["beispiel"]:
        raise Blocked("Projekt-/DEMO-Kennung widerspricht dem Projektzustand.")
    for ref in actual:
        current(root, state, ref["artefakt_id"])


def qa_check(report: dict):
    if report.get("ergebnis") != "freigabefaehig":
        raise Blocked(f"QA: {report.get('ergebnis', 'pruefung_unvollstaendig')}")
    if any(x.get("offen", True) and x.get("schwere") in ("K0", "K1") for x in report.get("findings", [])):
        raise Blocked("QA: offene K0/K1-Findings.")
    checks = report.get("pflichtpruefungen", [])
    if not checks or any(x.get("status") not in ("bestanden", "nicht_anwendbar") for x in checks):
        raise Blocked("QA: anwendbare Pflichtprüfung fehlt oder ist nicht bestanden.")
    for finding in report.get("findings", []):
        if any(k not in finding for k in ("datei", "problem", "soll", "ist", "schwere", "rueckweg", "offen")):
            raise Blocked("QA-Finding unvollständig.")
        if finding["schwere"] not in ("K0", "K1", "K2"):
            raise Blocked("QA-Schwere muss K0/K1/K2 sein.")
    if any(c.get("status") == "nicht_anwendbar" and not c.get("begruendung") for c in checks):
        raise Blocked("Nicht anwendbare Prüfung benötigt eine Begründung.")


def red_team_check(report: dict):
    qa_check(report)
    checks = {c["name"]: c for c in report["pflichtpruefungen"]}
    if not RED_TEAM_CHECKS.issubset(checks):
        raise Blocked("Unabhängige Red-Team-Pflichtprüfungen fehlen: " + ", ".join(sorted(RED_TEAM_CHECKS - set(checks))))
    if any(checks[name]["status"] != "bestanden" for name in RED_TEAM_CHECKS):
        raise Blocked("Jede unabhängige Red-Team-Pflichtprüfung muss tatsächlich bestanden sein.")


def word_count(text: str) -> int:
    return len(re.findall(r"\b[\w]+(?:[-’'][\w]+)*\b", text, flags=re.UNICODE))


def normalize(text: str) -> str:
    return " ".join(text.split())


def preflight(root: Path, state: dict) -> dict:
    artifacts = {aid: current(root, state, aid) for aid in ("A01", "A02", "A03", "A04", "A05", "A06")}
    for artifact in artifacts.values():
        schema_check(artifact)
        dependency_check(root, state, artifact)
    a02, a03, a04, a05, a06 = [artifacts[f"A{i:02d}"]["inhalt"] for i in range(2, 7)]
    sources = {s["quelle_id"]: s for s in a02["originalquellen"]}
    if len(sources) != len(a02["originalquellen"]):
        raise Blocked("Doppelte Quellen-ID.")
    from .pipeline import claim_source_catalog
    if a03.get("quellenkatalog") != claim_source_catalog(root, state, artifacts["A03"]):
        raise Blocked("A03-Bibliographie stimmt nicht mit den gebundenen Originalquellen überein.")
    for aid, artifact in artifacts.items():
        if not set(artifact["quellen"]).issubset(sources):
            raise Blocked(f"{aid}: unbekannte Quellen-ID in Metadaten.")
    claims = {c["claim_id"]: c for c in a03["claims"]}
    if not claims or len(claims) != len(a03["claims"]):
        raise Blocked("Leeres Claims-Register oder doppelte Claim-ID.")
    for claim in claims.values():
        if claim["status"] in ("BESTÄTIGT", "TEILWEISE") and claim["einsatz"] != "nein":
            if not claim["belege"]:
                raise Blocked(f"{claim['claim_id']}: kein Originalbeleg.")
            for evidence in claim["belege"]:
                source = sources.get(evidence["quelle_id"])
                if not source or source["zugriff"] != "geprüft" or not source["geoeffnet_am"] or not evidence["fundstelle"].strip():
                    raise Blocked(f"{claim['claim_id']}: Originalquelle nicht geprüft / Fundstelle fehlt.")
        if claim["status"] in ("UNBEWIESEN", "WIDERLEGT") and claim["einsatz"] != "nein":
            raise Blocked(f"{claim['claim_id']}: Status erlaubt keinen produktiven Einsatz; Quellenbehauptung separat modellieren.")
        if claim["einsatz"] == "nur_mit_einschraenkung" and not claim["einschraenkungen"]:
            raise Blocked(f"{claim['claim_id']}: Einschränkung fehlt.")

    used = set()
    def claim_links(item: dict, location: str):
        ids = item.get("claim_ids", [])
        if item.get("faktisch") and not ids:
            raise Blocked(f"{location}: faktische Aussage ohne Claim-ID.")
        if len(ids) != len(set(ids)):
            raise Blocked(f"{location}: doppelte Claim-IDs.")
        for cid in ids:
            if cid not in claims or claims[cid]["einsatz"] == "nein" or claims[cid]["status"] not in ("BESTÄTIGT", "TEILWEISE"):
                raise Blocked(f"{location}: unzulässiger Claim {cid}.")
            used.add(cid)
        if re.search(r"\d", item.get("text", "")) and not ids and item.get("funktion") != "disclaimer":
            raise Blocked(f"{location}: Zahl ohne Claim-Zuordnung.")

    if not a05["saetze"] or len({s["satz_id"] for s in a05["saetze"]}) != len(a05["saetze"]):
        raise Blocked("Satzregister fehlt oder IDs sind doppelt.")
    for s in a05["saetze"]:
        claim_links(s, s["satz_id"])
    for field in ("titel", "thumbnail", "beschreibung", "cta"):
        claim_links(a05[field], field)
    for overlay in a05["overlays"]:
        claim_links(overlay, "Overlay")
        if not 0 <= overlay["start"] < overlay["ende"] <= 54:
            raise Blocked("Overlay außerhalb der erlaubten Timeline.")
    speech = normalize(" ".join(s["text"] for s in a05["saetze"]))
    if speech != normalize(a05["sprechertext"]) or normalize(a05["untertitel_basis"]) != speech:
        raise Blocked("Satzregister, Sprechertext und Untertitelgrundlage weichen ab.")
    if a05["wortzahl"] != word_count(speech) or not 100 <= a05["wortzahl"] <= 130:
        raise Blocked("Sprecherwortzahl muss tatsächlich 100–130 sein.")
    ctas = [s for s in a05["saetze"] if s["funktion"] == "cta"]
    if len(ctas) != 1 or ctas[0]["text"] != a05["cta"]["text"]:
        raise Blocked("Exakt eine übereinstimmende CTA erforderlich.")
    if a05["disclaimer"] != DISCLAIMER:
        raise Blocked("Disclaimer entspricht nicht dem verbindlichen Text.")
    for cid in used:
        if claims[cid]["einsatz"] == "nur_mit_einschraenkung":
            if not any(normalize(e).casefold() in speech.casefold() for e in claims[cid]["einschraenkungen"]):
                raise Blocked(f"{cid}: Einschränkung muss ausdrücklich im Sprechertext erscheinen; QA prüft die Bedeutung.")
    if a04["profil"] != "MA-SHORT-58-v1.0":
        raise Blocked("V1 unterstützt ausschließlich MA-SHORT-58-v1.0.")
    if [(x["funktion"], x["start"], x["ende"]) for x in a04["dramaturgie"]] != PHASES:
        raise Blocked("A04: verbindliche Dramaturgie weicht ab.")
    for beat in a04["dramaturgie"]:
        claim_links({"text": "", "claim_ids": beat["claim_ids"]}, beat["beat_id"])
    listed_sources = set()
    for source_note in a05["quellenangaben"]:
        source = sources.get(source_note["quelle_id"])
        if not source or source_note["url"] != source["url"] or not source_note["fundstelle"].strip():
            raise Blocked("A05-Quellenangaben referenzieren eine unbekannte/falsche Originalquelle.")
        listed_sources.add(source_note["quelle_id"])
    needed_sources = {b["quelle_id"] for cid in used for b in claims[cid]["belege"]}
    if not needed_sources.issubset(listed_sources):
        raise Blocked("A05: verwendete Originalquellen fehlen in den Publikationsangaben.")

    scenes = a06["szenen"]
    if not scenes or len({s["szene_id"] for s in scenes}) != len(scenes):
        raise Blocked("Leere Szenenliste / doppelte Szenen-ID.")
    cursor = Decimal("0")
    for scene in scenes:
        start, end = Decimal(str(scene["start"])), Decimal(str(scene["ende"]))
        if start != cursor or end <= start:
            raise Blocked("A06: Lücke/Überlappung oder umsortierte Timeline.")
        cursor = end
        phase = next((p for p in PHASES if start >= p[1] and end <= p[2]), None)
        if not phase or scene["funktion"] != phase[0]:
            raise Blocked("Szene überquert Phasengrenze / hat falsche Funktion.")
        if scene["funktion"] == "disclaimer":
            if (start, end) != (54, 58) or scene["sprechertext"] or scene["overlay"] != DISCLAIMER:
                raise Blocked("Disclaimer muss exklusiv 54–58 s ohne Voiceover stehen.")
            if scene["motiv"].casefold() not in ("schwarz", "schwarzer hintergrund") or scene["audio"]["musik"] not in ("keine", "", False) or scene["audio"]["effekte"] not in ("keine", "", False):
                raise Blocked("Disclaimer benötigt schwarzen Hintergrund und vollständige Audiostille.")
        elif scene["overlay"] and not (state["beispiel"] and scene["overlay"] == "DEMO"):
            tracked = [o for o in a05["overlays"] if o["text"] == scene["overlay"] and o["start"] <= scene["start"] and o["ende"] >= scene["ende"]]
            if not tracked:
                raise Blocked(f"{scene['szene_id']}: Overlay muss wortgleich und zeitlich vollständig in A05 erfasst sein.")
        if scene["funktion"] != "disclaimer" and scene["sprechertext"]:
            # Szenen dürfen nur vollständige freigegebene Sätze enthalten.
            remaining = normalize(scene["sprechertext"])
            related = set()
            for sentence in a05["saetze"]:
                text = normalize(sentence["text"])
                if text in remaining:
                    related.update(sentence["claim_ids"])
                    remaining = normalize(remaining.replace(text, "", 1))
            if remaining or set(scene["claim_ids"]) != related:
                raise Blocked(f"{scene['szene_id']}: Sprechertext / Claim-Zuordnung widerspricht A05.")
        for cid in scene["claim_ids"]:
            claim_links({"text": "", "claim_ids": [cid], "faktisch": True}, scene["szene_id"])
    if cursor != 58 or not any(s["ende"] == 3 for s in scenes) or next(s for s in scenes if s["start"] == 3)["uebergang"] != "harter Schnitt":
        raise Blocked("58-s-Timeline oder harter Schnitt bei 3,000 s fehlt.")
    if normalize(" ".join(s["sprechertext"] for s in scenes)) != speech:
        raise Blocked("A06-Sprechertext stimmt nicht vollständig mit A05 überein.")
    if sum(s["funktion"] == "cta" for s in scenes) != 1:
        raise Blocked("A06: zweite oder fehlende CTA-Szene.")
    for asset in a06["assets"]:
        if asset["rechte_status"] != "geklaert" or not asset["rechte_beleg"]:
            raise Blocked(f"Asset {asset['asset_id']}: Rechte ungeklärt; Legal Review erforderlich.")
    asset_ids = {a["asset_id"] for a in a06["assets"]}
    for scene in scenes:
        if not set(scene["assetbedarf"]).issubset(asset_ids):
            raise Blocked("Szenenplan referenziert ein unbekanntes Asset.")
    if not a06["invideo_auftrag"].strip():
        raise Blocked("Vollständiger InVideo-Auftrag fehlt.")
    # Die deklarativen Faktisch-Flags werden zusätzlich unabhängig semantisch geprüft.
    return {"ergebnis": "freigabefaehig", "findings": [], "pflichtpruefungen": [
        {"name": "Schema/Dependencies/Claims/Timeline/CTA/Disclaimer/Rechte", "status": "bestanden"}
    ]}
