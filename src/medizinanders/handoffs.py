"""Vollständig kopierbare Handoffs; keine InVideo-/YouTube-API."""
from __future__ import annotations

import json
import shutil
import textwrap
from pathlib import Path
import yaml

from .storage import atomic_json, current, digest, ensure_contained, ensure_project_storage, write_text
from .validation import DISCLAIMER


def render(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def review_packets(root: Path, state: dict):
    root = ensure_project_storage(root)
    from .gates import CHECKLISTS, review_requirements
    a01 = current(root, state, "A01")
    a02 = current(root, state, "A02")
    a03 = current(root, state, "A03")
    prefix = "DEMO – keine reale Fachprüfung, keine medizinischen Tatsachen.\n\n" if state["beispiel"] else ""
    for kind in sorted(set(review_requirements(root, state)) | set(review_requirements(root, state, stage="production"))):
        name = "MEDICAL_REVIEW_PACKET.md" if kind == "medical" else "LEGAL_REVIEW_PACKET.md"
        claims = [c for c in a03["inhalt"]["claims"] if c["einsatz"] != "nein"]
        text = (prefix + f"# {'Medizinischer' if kind == 'medical' else 'Juristischer'} Fachreview\n\n"
                "Keine KI-Freigabe. Eine tatsächlich qualifizierte Fachperson prüft dieses Paket.\n\n"
                f"Projekt: {state['projekt_id']}\n\nKernfrage: {a01['inhalt']['kernfrage']}\n\n"
                f"Gebundene Artefakte:\n\n```json\n{render([state['artifacts'][a] for a in ('A01','A02','A03')])}\n```\n\n"
                f"## Verwendbare Claims, Quellenfundstellen und Unsicherheiten\n\n```json\n{render(claims)}\n```\n\n"
                f"## Tatsächliche Originalquellen und Studienparameter\n\n```json\n{render(a02['inhalt']['originalquellen'])}\n```\n\n"
                f"## Gegenbelege und Risiken\n\n```json\n{render({'gegenbelege':a02['inhalt']['gegenbelege'],'risiken':a03['inhalt']['risiken'],'unsicherheiten':a02['inhalt']['unsicherheiten']})}\n```\n\n"
                "## Geplante Formulierungen\n\nDie Aussagen im Claims-Register sind die vor G2 geplanten Formulierungen. "
                "BETA darf ihre Bedeutung nicht erweitern. Jede Bedeutungsänderung führt zu ALPHA und erneutem G2.\n\n"
                "## Konkrete Fragen an die Fachperson\n\n" + "\n".join(f"- {item}?" for item in CHECKLISTS[kind]) +
                "\n- Welche Formulierung muss geändert oder gestrichen werden?\n- Welche Gültigkeitsgrenze muss hörbar erscheinen?\n\n"
                f"## Operator\n\nNur nach tatsächlicher Prüfung: `ma review-record {state['projekt_id']} --kind {kind}`. "
                "Name, Fachqualifikation, echte Entscheidung und Nachweis dokumentieren. Ein offener zentraler Rechtsclaim blockiert die Episode.\n")
        text += "\nDieses Paket bindet ausschließlich A01–A03. Eine Claim-Prüfung ist keine Prüfung eines späteren Skripts.\n"
        write_text(root / "review" / name, text)
        if all(a in state["artifacts"] for a in ("A04", "A05", "A06")):
            production_text = (text + "\n# Zusätzlicher tatsächlicher Produktionsreview\n\n"
                               "Offen bis eine reale Fachperson den konkreten Wortlaut, Titel/Thumbnail/Overlays und die Szenen geprüft hat.\n\n"
                               "```json\n" + render([state["artifacts"][a] for a in ("A04", "A05", "A06")]) + "\n```\n\n"
                               "## Konkrete Formulierungen\n\n```json\n" + render(current(root, state, "A05")["inhalt"]) + "\n```\n\n"
                               "## Konkrete Szenen, Assets und Audio\n\n```json\n" + render(current(root, state, "A06")["inhalt"]) + "\n```\n\n"
                               f"Nach tatsächlicher Prüfung: `ma review-record {state['projekt_id']} --kind {kind} --stage production`.\n")
            write_text(root / "review" / ("MEDICAL_PRODUCTION_REVIEW_PACKET.md" if kind == "medical" else "LEGAL_PRODUCTION_REVIEW_PACKET.md"), production_text)
    for kind, filename in (("preview", "PREVIEW_CHECKLIST.md"), ("final", "FINAL_CHECKLIST.md")):
        write_text(root / "review" / filename, prefix + "# Echte Prüfung\n\n" + "\n".join(f"- [ ] {item}" for item in CHECKLISTS[kind]) + "\n\nKeine automatische Fach-, Smartphone- oder Hörprüfung.\n")


def format_time(seconds: float) -> str:
    millis = round(seconds * 1000)
    hours, rest = divmod(millis, 3600000)
    minutes, rest = divmod(rest, 60000)
    secs, ms = divmod(rest, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{ms:03}"


def subtitle_draft(scenes: list[dict]) -> str:
    """Zeitschätzung aus Szenen, ausdrücklich keine gemessene Sprachsynchronisation."""
    cues = []
    for scene in scenes:
        if not scene["sprechertext"]:
            continue
        lines = textwrap.wrap(scene["sprechertext"], width=28, break_long_words=False, break_on_hyphens=False)
        chunks = ["\n".join(lines[i:i + 2]) for i in range(0, len(lines), 2)]
        duration = scene["ende"] - scene["start"]
        weights = [len(c.replace("\n", " ")) for c in chunks]
        total = sum(weights)
        start = scene["start"]
        for idx, chunk in enumerate(chunks):
            end = scene["ende"] if idx == len(chunks) - 1 else start + duration * weights[idx] / total
            cues.append(f"{len(cues)+1}\n{format_time(start)} --> {format_time(end)}\n{chunk}\n")
            start = end
    return "\n".join(cues)


def invideo_handoff(root: Path, state: dict):
    root = ensure_project_storage(root)
    a05, a06 = [current(root, state, a)["inhalt"] for a in ("A05", "A06")]
    target = root / "handoff" / "invideo"
    prefix = "DEMO – SYNTHETISCH. KEINE REALE PRODUKTION ODER FREIGABE.\n\n" if state["beispiel"] else ""
    technical = ("Profil MA-SHORT-58-v1.0: genau58,000s/1740Frames,9:16,1080×1920,SAR1:1,30/1CFR,progressiv,"
                 "yuv420p,SDR/BT.709,H.264/AVC High Level4.1,Video Ziel10Mbit/s max16Mbit/s,geschlosseneGOPmax60Frames,"
                 "2B-Frames,MP4 FastStart,AAC-LC48kHzStereo,Ziel384kbit/s,-14LUFS-I (zulässig-15…-13),TruePeak≤-1,5dBTP.\n"
                 "Untertitel Deutsch,SRTUTF-8 und eingebrannt,MontserratBold52px,weiß,max2Zeilen/max28Zeichen,"
                 "realePixelbreite840px hatVorrang,max18Zeichen/s,Cues0,80–4,00s,Sync≤100ms;"
                 "sinnvolle semantische Umbrüche,Negationen/Zahlen/Einheiten erhalten."
                 "Sicherer Bereichx90…930,y192…1536,Unterkantey1520,Quellenhinweisey1200…1320.\n"
                 "Ruhige erwachsene deutsche Erzählstimme,keine imitierte Person/ärztliche Autorität."
                 "Instrumentalmusik ohneGesang/dramatischeStings,währendSprache18dB leiser(zulässig15–21dB)."
                 "Ohne belegbare getrennteSpuren:Musik entfernen.\n"
                 "Hook0–3,OpenLoop3–8,Payload8–41,Verdichtung41–48,CTA48–52,Ausklang52–54,Disclaimer54–58."
                 "HarterSchnitt exakt3,000s,genau eineCTA.\n"
                 f"Disclaimer54–58s:schwarzerHintergrund,ausschließlichText '{DISCLAIMER}',keinVoiceover,keineMusik/Effekte.\n")
    text = (prefix + "VOLLSTÄNDIGER INVIDEO-AUFTRAG\n\nVor Ausführung muss der Mensch G3 für diesen Freeze freigegeben haben.\n\n"
            + a06["invideo_auftrag"] + "\n\nVERBINDLICHER PRODUKTIONSRAHMEN\n" + technical +
            "\nVOLLSTÄNDIGER SPRECHERTEXT (wortgleich, keine Ergänzungen)\n" + a05["sprechertext"] +
            f"\n\nWortzahl: {a05['wortzahl']}\n\nAUSSPRACHE\n" + render(a05["aussprache"]) +
            "\n\nVOLLSTÄNDIGER SZENENPLAN\n" + render(a06["szenen"]) +
            "\n\nOVERLAYS\n" + render(a05["overlays"]) + "\n\nASSETS UND RECHTE\n" + render(a06["assets"]) +
            "\n\nQUELLENHINWEISE\n" + render(a05["quellenangaben"]) +
            "\n\nUNTERTITEL-TEXTGRUNDLAGE\n" + a05["untertitel_basis"] +
            "\n\nGenau eine CTA: " + a05["cta"]["text"] +
            "\n\nKeine Stockbilder als echten Beweis ausgeben. KI-Illustrationen deutlich kennzeichnen. "
            "Keine realen Patienten oder imitierte Stimmen. Ungeklärte Rechte blockieren.\n"
            "Ein Prompt garantiert keine Exportparameter. Die tatsächliche Datei wird nach dem Export geprüft.\n")
    write_text(target / "INVIDEO_PROMPT.txt", text)
    write_text(target / "SCENE_PLAN.md", prefix + "# Vollständiger Szenenplan\n\n```json\n" + render(a06["szenen"]) + "\n```\n")
    write_text(target / "VOICEOVER.txt", a05["sprechertext"] + "\n")
    write_text(target / "SUBTITLE_BASE.txt", a05["untertitel_basis"] + "\n")
    write_text(target / "SUBTITLE_DRAFT.srt", subtitle_draft(a06["szenen"]))
    write_text(target / "ASSET_MANIFEST.yaml", yaml.safe_dump({"beispiel": state["beispiel"], "assets": a06["assets"]}, allow_unicode=True, sort_keys=False))
    write_text(target / "RIGHTS_CHECKLIST.md", prefix + "# Rechte\n\nAlle Assets müssen konkrete Rechtebelege besitzen.\n\n```json\n" + render(a06["assets"]) + "\n```\n\n- [ ] Tatsächliche InVideo-/Stock-Lizenz und geplante Verwendung prüfen.\n- [ ] Keine fremde Stimme imitieren; keine Patientendaten.\n- [ ] KI-Illustrationen als Illustration kennzeichnen.\n- [ ] Offene Bild-/Musik-/Stimm-/Zitat-/Datenschutzfragen durch reale Rechtsprüfung klären.\n")
    write_text(target / "EXPECTED_OUTPUT.md", prefix + "# Tatsächlicher Export\n\n" + technical +
               "\nInVideo-Funktionen und Kosten sind real zu prüfen. Wenn einzelne Einstellungen nicht verfügbar sind, ist ein dokumentierter manueller Postproduktionsschritt erforderlich. "
               "Keine automatische Neucodierung. SUBTITLE_DRAFT.srt ist eine Zeitplanung und muss gegen den echten Ton synchronisiert werden.\n")
    write_text(target / "OPERATOR_STEPS.md", prefix + "# Manueller InVideo-Schritt\n\n"
               "1. G3 muss für den konkreten Freeze gültig sein.\n2. INVIDEO_PROMPT.txt vollständig kopieren.\n"
               "3. Kosten und tatsächliche Funktionen selbst prüfen; genau einen Entwurf erzeugen.\n"
               "4. Text, Assets, Rechte, Musikabstand und stille Disclaimer-Endcard kontrollieren.\n"
               "5. Vorschau tatsächlich exportieren.\n"
               f"6. Datei unter `{root / '08_produktion/inbox/preview.mp4'}` ablegen.\n"
               f"7. `ma resume {state['projekt_id']}` ausführen.\n\nKeine KI behauptet einen Render oder eine Kostenannahme.\n")


def youtube_handoff(root: Path, state: dict):
    root = ensure_project_storage(root)
    a05 = current(root, state, "A05")["inhalt"]
    a09 = current(root, state, "A09")["inhalt"]
    target = root / "handoff" / "youtube"
    prefix = "DEMO – KEIN UPLOAD UND KEINE VERÖFFENTLICHUNG.\n\n" if state["beispiel"] else ""
    write_text(target / "TITLE.txt", a05["titel"]["text"] + "\n")
    description = a05["beschreibung"]["text"] + "\n\nQuellen:\n" + "\n".join(q["text"] + " " + q["url"] + " – " + q["fundstelle"] for q in a05["quellenangaben"])
    write_text(target / "DESCRIPTION.txt", description + "\n\n" + " ".join(a05["hashtags"]) + "\n")
    write_text(target / "HASHTAGS.txt", " ".join(a05["hashtags"]) + "\n")
    write_text(target / "SOURCES.md", "# Quellen\n\n```json\n" + render(a05["quellenangaben"]) + "\n```\n")
    write_text(target / "THUMBNAIL_INSTRUCTIONS.md", prefix + "# Thumbnail\n\nText: " + a05["thumbnail"]["text"] + "\n\nNur belegte Aussagen, geklärte Assets, keine unbestätigten Gesundheitsversprechen.\n")
    shutil.copyfile(ensure_contained(root, root / a09["srt_pfad"]), ensure_contained(root, target / "SUBTITLES.srt"))
    write_text(target / "FINAL_SHA256.txt", a09["final_sha256"] + "  " + str(root / a09["final_pfad"]) + "\n")
    atomic_json(target / "DECISIONS.json", {"beispiel": state["beispiel"], "ki_kennzeichnung": {"entscheidung": None, "begruendung": "Vom Menschen auf der tatsächlichen Plattform zu bestätigen."},
                "zielgruppe_fuer_kinder": None, "bezahlte_werbung": None, "final_sha256": a09["final_sha256"]})
    write_text(target / "UPLOAD_CHECKLIST.md", prefix + "# Ausschließlich privater Upload\n\n"
               f"Finaldatei: `{root / a09['final_pfad']}`\n\nSHA-256: `{a09['final_sha256']}`\n\n"
               "1. Reale Finalprüfung einschließlich Smartphone/Hören und alle QA-Blocker klären.\n"
               f"2. `ma approve G5a --project {state['projekt_id']}` persönlich ausführen.\n"
               "3. Exakt diese Datei manuell ausschließlich privat auf YouTube hochladen.\n"
               "4. Titel, Beschreibung, Quellen, Hashtags, SRT und Thumbnail aus diesem Paket übernehmen.\n"
               "5. KI-Kennzeichnung, Zielgruppe und Werbeentscheidung persönlich treffen; DECISIONS.json ist keine bestätigte Entscheidung.\n"
               f"6. Tatsächliche Video-ID/URL zurückmelden: `ma youtube-record {state['projekt_id']}`.\n"
               "7. Verarbeitete Plattformfassung vollständig prüfen; erst G5b erlaubt manuelle Veröffentlichung.\n")


def playback_checklist(root: Path, state: dict):
    root = ensure_project_storage(root)
    from .gates import CHECKLISTS
    content = current(root, state, "A11")["inhalt"]
    write_text(root / "handoff/youtube/PRIVATE_PLAYBACK_CHECKLIST.md", "# Tatsächliche private Plattformprüfung\n\n"
               f"Video-ID: {content['video_id']}\n\nURL: {content['url']}\n\nFinal-SHA256: {content['final_sha256']}\n\n"
               + "\n".join(f"- [ ] {item}" for item in CHECKLISTS["playback"]) +
               f"\n\nNur danach: `ma review-record {state['projekt_id']} --kind playback`, "
               f"dann `ma approve G5b --project {state['projekt_id']}`. Veröffentlichung führt der Mensch selbst aus.\n")
