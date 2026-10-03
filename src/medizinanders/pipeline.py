"""Dateibasierter Orchestrator. Keine menschliche Entscheidung wird automatisiert."""
from __future__ import annotations

import copy
import datetime as dt
import re
import shutil
from pathlib import Path

from .storage import (Blocked, artifact_path, atomic_json, current, data_root, digest, ensure_contained, ensure_project_storage, lock, now,
                      object_hash, read_json, reference, repo_root, write_text)
from .validation import DEPENDENCIES, dependency_check, preflight, qa_check, red_team_check, schema_check
from .workers import ROLE_INPUTS, ROLE_OUTPUTS, execute_cli, prepare_job


def policy_hash() -> str:
    repo = repo_root()
    files = {}
    for folder in ("agents", "schemas", "config"):
        for path in sorted((repo / folder).rglob("*")):
            if path.is_file() and path.suffix in (".py", ".json", ".yaml", ".md") and "__pycache__" not in path.parts:
                files[str(path.relative_to(repo))] = digest(path)
    for path in sorted(Path(__file__).resolve().parent.glob("*.py")):
        files[f"src/medizinanders/{path.name}"] = digest(path)
    if (repo / "AGENTS.md").is_file():
        files["AGENTS.md"] = digest(repo / "AGENTS.md")
    return object_hash(files)


def new_project(thema: str, *, beispiel=False, zielgruppe="Interessierte Erwachsene, ohne individuelle Beratung",
                serienkontext="Einzelepisode", zeitlimit="STANDARDVORSCHLAG: vor G1 festlegen",
                kostenlimit="STANDARDVORSCHLAG: keine Kosten ohne reale Zustimmung") -> tuple[Path, dict]:
    if not thema.strip():
        raise Blocked("Eine Themenidee ist erforderlich.")
    with lock(data_root() / ".project.lock"):
        day = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d")
        base = ensure_contained(data_root(), data_root() / "projects")
        base.mkdir(exist_ok=True, mode=0o700)
        for number in range(1, 1000):
            pid = f"MA-{day}-{number:03d}"
            root = base / pid
            if not root.exists():
                root.mkdir(mode=0o700)
                break
        else:
            raise Blocked("999 Projekte für diesen Tag existieren bereits.")
        for directory in ("artifacts", "jobs", "sources", "review", "gates", "freeze", "handoff/invideo",
                          "handoff/youtube", "08_produktion/inbox", "09_postproduktion/inbox", "10_qa", "12_analytics"):
            (root / directory).mkdir(parents=True, exist_ok=True, mode=0o700)
        state = {"projekt_id": pid, "beispiel": beispiel, "created": now(), "artifacts": {}, "jobs": {},
                 "gates": {}, "reviews": {}, "freeze": None, "red_team": None, "media": {}, "history": [],
                 "auftrag": {"thema": thema.strip(), "zielgruppe": zielgruppe, "serienkontext": serienkontext,
                             "zeitlimit": zeitlimit, "kostenlimit": kostenlimit, "beispiel": beispiel}}
        atomic_json(root / "state.json", state, exclusive=True)
        write_text(root / "DATENSCHUTZ.md", "Lokale Produktionsdaten. Niemals zu Git hinzufügen. Keine Patientendaten, Secrets oder Browserprofile ablegen.\n")
        return root, state


def next_version(root: Path, aid: str, bump="minor") -> str:
    versions = [tuple(map(int, p.stem.split("."))) for p in (root / "artifacts" / aid).glob("*.json")]
    if not versions:
        return "0.1.0"
    major, minor, patch = max(versions)
    if bump == "major":
        return f"{major + 1}.0.0"
    if bump == "patch":
        return f"{major}.{minor}.{patch + 1}"
    return f"{major}.{minor + 1}.0"


def put_artifact(root: Path, state: dict, artifact: dict, *, bind_inputs=False, bump=None, internal=False):
    root = ensure_project_storage(root)
    artifact = copy.deepcopy(artifact)
    aid = artifact.get("artefakt_id")
    if aid not in DEPENDENCIES:
        raise Blocked("Unbekanntes Artefakt.")
    if not internal and aid not in {f"A{i:02d}" for i in range(1, 7)}:
        raise Blocked("Freier Import ist auf A01–A06 beschränkt. A07–A12 benötigen den jeweiligen Orchestrator-/Operator-Befehl und reale Nachweise.")
    if bind_inputs:
        artifact["eingaben"] = [state["artifacts"][x] for x in DEPENDENCIES[aid]]
        artifact["projekt_id"] = state["projekt_id"]
        artifact["beispiel"] = state["beispiel"]
        artifact["version"] = next_version(root, aid, bump or "minor")
        artifact["datum"] = now()
    if aid == "A03":
        catalog = claim_source_catalog(root, state, artifact)
        declared = artifact["inhalt"].get("quellenkatalog")
        if declared and declared != catalog:
            raise Blocked("A03-Quellenkatalog widerspricht den gebundenen Originalquellen.")
        artifact["inhalt"]["quellenkatalog"] = catalog
    schema_check(artifact)
    dependency_check(root, state, artifact)
    if not state["beispiel"] and any("DEMO" in str(artifact[field]).upper() for field in ("autor", "inhalt")):
        raise Blocked("DEMO-Inhalt ist in Produktionsprojekten nicht zulässig.")
    replacing = aid in state["artifacts"]
    if replacing:
        old = current(root, state, aid)
        if tuple(map(int, artifact["version"].split("."))) <= tuple(map(int, old["version"].split("."))):
            raise Blocked("Neue Version muss höher sein; bestehende Version wird nie überschrieben.")
        if bump == "patch" and re.sub(r"\s+", "", str(old["inhalt"])) != re.sub(r"\s+", "", str(artifact["inhalt"])):
            raise Blocked("Patch nur reine Leerraum-/Formatkorrektur. Andere Korrekturen konservativ als Minor behandeln.")
    path = artifact_path(root, artifact)
    atomic_json(path, artifact, exclusive=True)
    if replacing:
        invalidate_artifact(root, state, aid, "Neue Artefaktversion")
    state["artifacts"][aid] = reference(root, aid, artifact["version"])
    state["history"].append({"time": now(), "event": "artifact", "ref": state["artifacts"][aid]})
    return artifact


def generate(root: Path, state: dict, aid: str, content: dict, *, author="ORCHESTRATOR", status="geprüft"):
    artifact = {"artefakt_id": aid, "projekt_id": state["projekt_id"], "version": next_version(root, aid),
                "datum": now(), "autor": author, "status": status,
                "eingaben": [state["artifacts"][x] for x in DEPENDENCIES[aid]], "quellen": [], "offene_punkte": [],
                "gesperrt": False, "sperrgrund": "", "beispiel": state["beispiel"], "inhalt": content}
    return put_artifact(root, state, artifact, internal=True)


def stage_candidates(root: Path, state: dict, aids: list[str]):
    root = ensure_project_storage(root)
    # Kandidaten vor der Freigabe erzeugen; deren unveränderlicher Status ist ein Zeitstempel.
    # Effektiver Freigabestatus steht ausschließlich in externen hashgebundenen Gates.
    for aid in aids:
        artifact = current(root, state, aid)
        if int(artifact["version"].split(".")[0]) == 0:
            staged = copy.deepcopy(artifact)
            staged.update(version="1.0.0", status="geprüft", datum=now())
            staged["eingaben"] = [state["artifacts"][x] for x in DEPENDENCIES[aid]]
            atomic_json(artifact_path(root, staged), staged, exclusive=True)
            state["artifacts"][aid] = reference(root, aid, staged["version"])


def invalidate_artifact(root: Path, state: dict, aid: str, reason: str):
    affected = {aid}
    changed = True
    while changed:
        changed = False
        for child, parents in DEPENDENCIES.items():
            if child not in affected and set(parents) & affected:
                affected.add(child)
                changed = True
    for child in affected:
        state["artifacts"].pop(child, None)
    from .gates import GATE_ARTIFACTS
    invalidated = []
    for gate in list(state["gates"]):
        if affected & set(GATE_ARTIFACTS.get(gate, [])):
            invalidated.append(gate)
            del state["gates"][gate]
    for job in state["jobs"].values():
        if any(x["artefakt_id"] in affected for x in job["input_refs"]) or set(ROLE_OUTPUTS[job["role"]]) & affected:
            job["invalidated"] = True
    if affected & {"A01", "A02", "A03", "A04", "A05", "A06", "A07"}:
        state["freeze"] = None
        state["red_team"] = None
    state["history"].append({"time": now(), "event": "invalidate", "reason": reason,
                             "artifacts": sorted(affected), "gates": invalidated})


CHANGE_ROUTES = {"source": "A02", "claim": "A03", "meaning": "A03", "wording": "A05",
                 "title": "A05", "thumbnail": "A05", "cta": "A05", "pronunciation": "A06",
                 "music": "A06", "image": "A06", "subtitle": "A06", "cut": "A06", "export": "A09",
                 "question": "A01", "format": "A04"}


def invalidate_change(root: Path, state: dict, change: str, reason: str):
    if not reason.strip():
        raise Blocked("Eine nachvollziehbare Änderungsbegründung ist erforderlich.")
    invalidate_artifact(root, state, CHANGE_ROUTES[change], f"{change}: {reason}")


def complete_job(root: Path, state: dict, job_id: str):
    """All-or-nothing acceptance; the CLI persists no partial BETA state on I/O failure."""
    root = ensure_project_storage(root)
    before = copy.deepcopy(state)
    directories = [ensure_contained(root, root / name) for name in ("artifacts", "sources")]
    prior_files = {p.resolve() for directory in directories for p in directory.rglob("*") if p.is_file()}
    try:
        _complete_job(root, state, job_id)
    except Exception as error:
        state.clear()
        state.update(before)
        for directory in directories:
            for path in directory.rglob("*"):
                if path.is_file() and path.resolve() not in prior_files:
                    path.unlink()
        if isinstance(error, Blocked):
            raise
        raise Blocked(f"Worker-Übergabe zurückgerollt: {type(error).__name__}: {error}") from error


def _complete_job(root: Path, state: dict, job_id: str):
    job = state["jobs"].get(job_id)
    if not job or job.get("invalidated") or job["completed"]:
        raise Blocked("Job unbekannt, bereits abgeschlossen oder invalidiert.")
    if job["policy"] != policy_hash() or job["input_refs"] != [state["artifacts"].get(a) for a in ROLE_INPUTS[job["role"]]]:
        raise Blocked("Worker-Kontext ist veraltet.")
    directory = root / "jobs" / job_id
    for name, expected_sha in job.get("input_hashes", {}).items():
        path = directory / name
        if not path.is_file() or digest(path) != expected_sha:
            raise Blocked(f"Worker hat seinen Input verändert: {name}")
    for ref in job["input_refs"]:
        if digest(directory / "input" / f"{ref['artefakt_id']}.json") != ref["sha256"]:
            raise Blocked("Worker hat seinen Input verändert.")
    output = directory / "output"
    if (output / "BLOCKED.md").exists():
        raise Blocked(f"Worker meldet Blocker: {output / 'BLOCKED.md'}")
    if job["role"] == "qa-red-team":
        report = read_json(output / "QA.json")
        red_team_check(report)
        state["red_team"] = {"job_id": job_id, "path": str((output / "QA.json").relative_to(root)),
                             "sha256": digest(output / "QA.json"), "input_refs": job["input_refs"]}
    else:
        # Validate all output before accepting any, to prevent partial BETA registration.
        trial = copy.deepcopy(state)
        pending = []
        source_copies = []
        for aid in ROLE_OUTPUTS[job["role"]]:
            artifact = read_json(output / f"{aid}.json")
            if artifact.get("artefakt_id") != aid or artifact.get("projekt_id") != state["projekt_id"] or artifact.get("beispiel") != state["beispiel"]:
                raise Blocked("Worker hat falsches Projekt/Artefakt oder DEMO-Kennung geliefert.")
            if artifact.get("status") != "Entwurf":
                raise Blocked("Worker darf nur Entwurf erzeugen.")
            artifact["eingaben"] = [trial["artifacts"][x] for x in DEPENDENCIES[aid]]
            artifact["version"] = next_version(root, aid)
            # Worker fields are untrusted. Validate them before using IDs in paths.
            schema_check(artifact)
            if aid == "A02":
                for source in artifact["inhalt"]["originalquellen"]:
                    if source["zugriff"] != "geprüft":
                        continue
                    origin = (output / source["lokaler_pfad"]).resolve()
                    if output.resolve() not in origin.parents or not origin.is_file() or digest(origin) != source["sha256"]:
                        raise Blocked("Geprüfte Quelle benötigt überprüfbare Originalkopie im Worker-Output.")
                    if not state["beispiel"] and not source["url"].startswith("https://"):
                        raise Blocked("Produktionsquelle benötigt reale HTTPS-URL.")
                    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", source["quelle_id"]):
                        raise Blocked("Quellen-ID darf kein Dateipfad sein.")
                    destination = (root / "sources" / source["quelle_id"] / (source["sha256"] + origin.suffix)).resolve()
                    if root.resolve() not in destination.parents:
                        raise Blocked("Quellenziel verlässt den Projektspeicher.")
                    if destination.exists() and digest(destination) != source["sha256"]:
                        raise Blocked("Unveränderliche Originalkopie wurde verändert.")
                    source_copies.append((origin, destination, source["sha256"]))
                    source["lokaler_pfad"] = str(destination.relative_to(root))
            if aid == "A03":
                artifact["inhalt"]["quellenkatalog"] = claim_source_catalog(root, state, artifact)
            schema_check(artifact)
            if artifact["eingaben"] != [trial["artifacts"].get(x) for x in DEPENDENCIES[aid]]:
                raise Blocked("Worker-Abhängigkeiten ungültig.")
            pending.append(artifact)
            from .storage import canonical
            trial["artifacts"][aid] = {"artefakt_id": aid, "version": artifact["version"], "sha256": object_hash(artifact)}
        for origin, destination, source_sha in source_copies:
            destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if not destination.exists():
                shutil.copyfile(origin, destination)
            if digest(destination) != source_sha:
                raise Blocked("Quelle wurde während der Übergabe verändert.")
        for artifact in pending:
            put_artifact(root, state, artifact)
        job["invalidated"] = False
    job["completed"] = True
    job["completed_at"] = now()
    job["output_hashes"] = {name: digest(output / name) for name in job["output_files"]}


def claim_source_catalog(root: Path, state: dict, artifact: dict) -> list[dict]:
    """Nur bibliographische Daten der von ALPHA referenzierten Originalquellen."""
    sources = {s["quelle_id"]: s for s in current(root, state, "A02")["inhalt"]["originalquellen"]}
    used = {b["quelle_id"] for c in artifact["inhalt"]["claims"] for b in c["belege"] + c["gegenbelege"]}
    if not used.issubset(sources):
        raise Blocked("ALPHA referenziert unbekannte Originalquelle.")
    return [{key: sources[qid][key] for key in ("quelle_id", "url", "titel", "zugriff", "sha256")} for qid in sorted(used)]


def evidence_validate(root: Path, state: dict):
    for aid in ("A01", "A02", "A03"):
        artifact = current(root, state, aid)
        schema_check(artifact)
        dependency_check(root, state, artifact)
    sources = {s["quelle_id"]: s for s in current(root, state, "A02")["inhalt"]["originalquellen"]}
    claims = current(root, state, "A03")["inhalt"]["claims"]
    if len({c["claim_id"] for c in claims}) != len(claims):
        raise Blocked("Doppelte Claim-ID.")
    for source in sources.values():
        if source["zugriff"] == "geprüft":
            path = (root / source["lokaler_pfad"]).resolve()
            if root.resolve() not in path.parents or not path.is_file() or digest(path) != source["sha256"]:
                raise Blocked(f"Originalquelle {source['quelle_id']} fehlt oder wurde verändert.")
    for claim in claims:
        if claim["einsatz"] == "nein":
            continue
        if claim["status"] not in ("BESTÄTIGT", "TEILWEISE") or not claim["belege"]:
            raise Blocked(f"{claim['claim_id']}: kein zulässiger belegter Claim.")
        for evidence in claim["belege"]:
            source = sources.get(evidence["quelle_id"])
            if not source or source["zugriff"] != "geprüft" or not evidence["fundstelle"].strip():
                raise Blocked(f"{claim['claim_id']}: nicht zugänglicher Originalbeleg.")


def freeze(root: Path, state: dict, report: dict):
    root = ensure_project_storage(root)
    refs = [state["artifacts"][f"A{i:02d}"] for i in range(1, 7)]
    if state["freeze"]:
        verify_freeze(root, state)
        return
    stage_candidates(root, state, ["A04", "A05", "A06"])
    refs = [state["artifacts"][f"A{i:02d}"] for i in range(1, 7)]
    # Candidate promotion changes BETA refs: fresh independent QA must review candidate bytes.
    red = state["red_team"]
    if not red or red["input_refs"] != refs:
        raise Blocked("Frischer Red-Team-Review für die konkreten Freeze-Kandidaten erforderlich.")
    qa_path = root / red["path"]
    if digest(qa_path) != red["sha256"]:
        raise Blocked("Red-Team-Report verändert.")
    red_team_check(read_json(qa_path))
    revision = 1
    while (root / "freeze" / f"r{revision:03d}").exists():
        revision += 1
    directory = root / "freeze" / f"r{revision:03d}"
    directory.mkdir(mode=0o700)
    for ref in refs:
        shutil.copyfile(artifact_path(root, ref), directory / f"{ref['artefakt_id']}-{ref['version']}.json")
    assets = current(root, state, "A06")["inhalt"]["assets"]
    atomic_json(directory / "ASSET_RIGHTS.json", assets, exclusive=True)
    atomic_json(directory / "PREFLIGHT.json", report, exclusive=True)
    shutil.copyfile(qa_path, directory / "RED_TEAM.json")
    from .handoffs import invideo_handoff
    invideo_handoff(root, state)
    shutil.copytree(root / "handoff" / "invideo", directory / "invideo")
    files = {str(path.relative_to(directory)): digest(path) for path in sorted(directory.rglob("*")) if path.is_file()}
    manifest = {"projekt_id": state["projekt_id"], "beispiel": state["beispiel"], "revision": f"r{revision:03d}",
                "created": now(), "artifacts": refs, "policy": policy_hash(), "files": files}
    atomic_json(directory / "manifest.json", manifest, exclusive=True)
    sums = files | {"manifest.json": digest(directory / "manifest.json")}
    write_text(directory / "SHA256SUMS", "".join(f"{sha}  {name}\n" for name, sha in sorted(sums.items())))
    state["freeze"] = {"revision": manifest["revision"], "manifest_sha256": digest(directory / "manifest.json"),
                       "sums_sha256": digest(directory / "SHA256SUMS"), "artifacts": refs}
    generate(root, state, "A07", {"freeze_revision": manifest["revision"], "manifest_sha256": state["freeze"]["manifest_sha256"],
                                  "preflight": report, "qa": read_json(qa_path)})
    stage_candidates(root, state, ["A07"])


def verify_freeze(root: Path, state: dict):
    if not state["freeze"]:
        raise Blocked("Freeze fehlt.")
    info = state["freeze"]
    directory = root / "freeze" / info["revision"]
    if digest(directory / "manifest.json") != info["manifest_sha256"] or digest(directory / "SHA256SUMS") != info["sums_sha256"]:
        raise Blocked("Freeze-Manifest/Hashliste verändert.")
    manifest = read_json(directory / "manifest.json")
    if manifest["policy"] != policy_hash() or info["artifacts"] != [state["artifacts"].get(f"A{i:02d}") for i in range(1, 7)]:
        raise Blocked("Freeze ist veraltet; neuer Freeze und neue G3-Freigabe erforderlich.")
    expected = manifest["files"] | {"manifest.json": info["manifest_sha256"], "SHA256SUMS": info["sums_sha256"]}
    actual = {str(p.relative_to(directory)): digest(p) for p in directory.rglob("*") if p.is_file()}
    if actual != expected:
        raise Blocked("Freeze-Dateiliste/Hashes stimmen nicht überein.")


def wait(gate: str, why: str, steps: list[str], *, blocked_at=None) -> dict:
    return {"status": "WAITING_FOR_HUMAN", "gate": gate, "why": why,
            "blocked_at": blocked_at or gate, "next": steps}


def dispatch(root: Path, state: dict, role: str, execute=False) -> dict:
    job = prepare_job(root, state, role, policy_hash())
    atomic_json(root / "state.json", state)
    if execute:
        execute_cli(root, job)
        complete_job(root, state, job["job_id"])
        atomic_json(root / "state.json", state)
        return {"status": "WORKER_COMPLETE", "role": role}
    return {"status": "WAITING_FOR_CODEX", "role": role, "job_id": job["job_id"],
            "job_path": str(root / "jobs" / job["job_id"]),
            "why": "Isolierter nativer Worker mit neuem Kontext erforderlich.",
            "next": ["Codex-Orchestrator: AGENTS.md lesen, spawn_agent mit fork_turns=none und nur diesem Jobpfad starten.",
                     f"Danach: ma worker-complete {state['projekt_id']} --job {job['job_id']}",
                     f"Alternative nach bestätigtem G0 CLI-Modus: ma run {state['projekt_id']} --execute-workers"]}


def run(root: Path, state: dict, *, execute=False, recheck_media=None) -> dict:
    root = ensure_project_storage(root)
    from .gates import gate_valid, operating_valid, review_requirements, review_valid
    from .handoffs import review_packets, youtube_handoff
    pid = state["projekt_id"]
    if not operating_valid(state):
        return wait("G0", "Betriebsfreigabe fehlt oder Regeln/Umgebung wurden verändert.",
                    ["ma setup", "Prüfe die Operator-Konfiguration und die Rollenprompts.", "ma approve G0"])
    if execute:
        import yaml
        config = yaml.safe_load((data_root() / "operator.yaml").read_text(encoding="utf-8")) if not state["beispiel"] else {"worker_mode": "codex_cli"}
        if config.get("worker_mode") != "codex_cli":
            raise Blocked("G0 erlaubt keinen Codex-CLI-Modus. Native Session nutzen oder G0 bewusst neu bestätigen.")
    for _ in range(12):
        if "A01" not in state["artifacts"]:
            result = dispatch(root, state, "gamma", execute)
            if result["status"] == "WORKER_COMPLETE":
                continue
            return result
        stage_candidates(root, state, ["A01"])
        if not gate_valid(root, state, "G1"):
            return wait("G1", "Auftrag benötigt menschliche Freigabe; erst danach beginnt Recherche.",
                        [f"Öffne {artifact_path(root, state['artifacts']['A01'])}", f"ma approve G1 --project {pid}"])
        if "A02" not in state["artifacts"]:
            result = dispatch(root, state, "research", execute)
            if result["status"] == "WORKER_COMPLETE":
                continue
            return result
        stage_candidates(root, state, ["A02"])
        if "A03" not in state["artifacts"]:
            result = dispatch(root, state, "alpha", execute)
            if result["status"] == "WORKER_COMPLETE":
                continue
            return result
        stage_candidates(root, state, ["A03"])
        evidence_validate(root, state)
        review_packets(root, state)
        if not gate_valid(root, state, "G2"):
            pending = [kind for kind in review_requirements(root, state) if not review_valid(root, state, kind)]
            return wait("G2", f"Inhaltsfreigabe fehlt. Pflichtreviews offen: {', '.join(pending) or 'keine; menschliche Claim-Prüfung erforderlich'}.",
                        [f"Öffne {root / 'review'}; echte Fachpersonen prüfen die zutreffenden Pakete.",
                         f"ma review-record {pid} --kind medical bzw. legal (nur nach tatsächlicher Fachprüfung)",
                         f"ma approve G2 --project {pid}"])
        if any(a not in state["artifacts"] for a in ("A04", "A05", "A06")):
            result = dispatch(root, state, "beta", execute)
            if result["status"] == "WORKER_COMPLETE":
                continue
            return result
        stage_candidates(root, state, ["A04", "A05", "A06"])
        review_packets(root, state)
        open_assets = [a["asset_id"] for a in current(root, state, "A06")["inhalt"]["assets"] if a["rechte_status"] != "geklaert" or not a["rechte_beleg"]]
        if open_assets:
            return wait("G3", "Assetrechte sind ungeklärt: " + ", ".join(open_assets),
                        [f"Öffne {root / 'review/LEGAL_PRODUCTION_REVIEW_PACKET.md'} und lasse die tatsächlichen Rechte klären.",
                         "Eine reale Fachperson dokumentiert die Entscheidung und konkrete Lizenz-/Rechtebelege; keine pauschale Rechtsfreigabe.",
                         f"Codex/BETA erstellt eine neue A06-Version mit den echten Belegen; anschließend ma resume {pid}.",
                         "Preflight, unabhängige QA und Freeze müssen vor G3 vollständig vorliegen."])
        report = preflight(root, state)
        refs = [state["artifacts"][f"A{i:02d}"] for i in range(1, 7)]
        if not state["red_team"] or state["red_team"]["input_refs"] != refs:
            result = dispatch(root, state, "qa-red-team", execute)
            if result["status"] == "WORKER_COMPLETE":
                continue
            return result
        freeze(root, state, report)
        if not gate_valid(root, state, "G3"):
            pending = [kind for kind in review_requirements(root, state, stage="production") if not review_valid(root, state, kind, stage="production")]
            if pending:
                return wait("G3", f"Konkreter Skript-/Szenenwortlaut benötigt echte Fachprüfung: {', '.join(pending)}.",
                            [f"Öffne {root / 'review'} und die zutreffenden *_PRODUCTION_REVIEW_PACKET.md.",
                             *[f"ma review-record {pid} --kind {kind} --stage production" for kind in pending],
                             f"ma approve G3 --project {pid}"], blocked_at="G3_INVIDEO")
            return wait("G3", "Preflight, unabhängige QA und unveränderlicher Freeze sind vorbereitet. Mensch bestätigt Produktion und reale Kosten.",
                        [f"Prüfe {root / 'freeze' / state['freeze']['revision']}", f"ma approve G3 --project {pid}",
                         f"Erst danach {root / 'handoff/invideo/OPERATOR_STEPS.md'} ausführen."], blocked_at="G3_INVIDEO")
        preview = root / "08_produktion/inbox/preview.mp4"
        if not preview.exists():
            return wait("G3", "Alles für den tatsächlichen manuellen InVideo-Schritt vorbereitet.",
                        [f"Öffne {root / 'handoff/invideo/INVIDEO_PROMPT.txt'}",
                         "Erzeuge damit genau einen Entwurf in InVideo; bestätige Kosten selbst und exportiere die Vorschau.",
                         f"Lege die echte Datei unter {preview} ab.", f"ma resume {pid}"], blocked_at="G3_INVIDEO")
        process_preview(root, state, preview, force=recheck_media == "preview")
        if not gate_valid(root, state, "G4"):
            return wait("G4", "Echte Vorschau geprüft. Technische Pflichtchecks und echte Smartphone-/Hör-/Inhaltsprüfung sind erforderlich.",
                        [f"Öffne {root / '10_qa'} und {root / 'review/PREVIEW_CHECKLIST.md'}",
                         f"ma review-record {pid} --kind preview", f"ma approve G4 --project {pid}"])
        final = root / "09_postproduktion/inbox/final.mp4"
        srt = root / "09_postproduktion/inbox/final.srt"
        if not final.exists() or not srt.exists():
            return wait("G5a", "Freigegebene Vorschau vorhanden. Tatsächlicher Finalexport und synchronisierte SRT fehlen.",
                        [f"Finaldatei nach {final} und UTF-8 SRT nach {srt} ablegen.", f"ma resume {pid}"])
        process_final(root, state, final, srt, force=recheck_media == "final")
        refresh_final_assessment(root, state)
        youtube_handoff(root, state)
        if not gate_valid(root, state, "G5a"):
            return wait("G5a", "Uploadpaket und QA binden die konkrete Finaldatei. Echte Finalprüfung erforderlich.",
                        [f"Öffne {root / 'handoff/youtube/UPLOAD_CHECKLIST.md'}",
                         f"ma review-record {pid} --kind final", f"ma approve G5a --project {pid}"])
        if "A11" not in state["artifacts"] or not current(root, state, "A11")["inhalt"].get("video_id"):
            return wait("G5b", "G5a erlaubt ausschließlich den manuellen privaten Upload.",
                        [f"Nutze {root / 'handoff/youtube'} und lade die gebundene Finaldatei privat hoch.",
                         f"ma youtube-record {pid} (Video-ID, URL, Entscheidungen und tatsächliche Sichtbarkeit)"])
        if publication_valid(root, state):
            return {"status": "PUBLISHED_RECORDED", "why": "Tatsächliche Veröffentlichung durch den Operator dokumentiert; keine Pipeline-Veröffentlichung.",
                    "next": [f"Später reale Analytics importieren: ma analytics {pid} --file analytics.json"]}
        from .handoffs import playback_checklist
        playback_checklist(root, state)
        if not gate_valid(root, state, "G5b"):
            return wait("G5b", "Verarbeitetes privates Plattformvideo muss tatsächlich geprüft werden.",
                        [f"Öffne {root / 'handoff/youtube/PRIVATE_PLAYBACK_CHECKLIST.md'}",
                         f"ma review-record {pid} --kind playback", f"ma approve G5b --project {pid}"])
        if current(root, state, "A11")["inhalt"]["sichtbarkeit"] != "public":
            return wait("G5b", "Menschliche Veröffentlichungsfreigabe liegt vor; Veröffentlichung bleibt manuell.",
                        ["Stelle das geprüfte Video selbst auf öffentlich.", f"ma published {pid} (nur nach tatsächlicher Veröffentlichung)"])
        return {"status": "PUBLISHED_RECORDED", "why": "Tatsächliche Veröffentlichung durch den Operator dokumentiert; keine Pipeline-Veröffentlichung.",
                "next": [f"Später reale Analytics importieren: ma analytics {pid} --file analytics.json"]}
    raise Blocked("Orchestrator hat zu viele Übergänge ausgeführt.")


def media_environment() -> str:
    tools = {tool: str(Path(shutil.which(tool)).resolve()) if shutil.which(tool) else None for tool in ("ffmpeg", "ffprobe", "fc-match")}
    font = data_root() / "fonts/Montserrat-Bold.ttf"
    return object_hash({"tools": tools, "font": digest(font) if font.is_file() else None})


def inspection_directory(root: Path, prefix: str) -> Path:
    root = ensure_project_storage(root)
    number = 1
    while (root / "10_qa" / f"{prefix}-r{number:03d}").exists():
        number += 1
    return ensure_contained(root, root / "10_qa" / f"{prefix}-r{number:03d}")


def process_preview(root: Path, state: dict, path: Path, *, force=False):
    root = ensure_project_storage(root)
    from .media import inspect_video
    sha = digest(path)
    environment = media_environment()
    if not force and state["media"].get("preview", {}).get("sha256") == sha and state["media"].get("preview", {}).get("environment") == environment and "A08" in state["artifacts"]:
        return
    if "A08" in state["artifacts"]:
        invalidate_artifact(root, state, "A08", "Neue echte Vorschau")
    report_dir = inspection_directory(root, f"preview-{sha[:16]}")
    report = inspect_video(path, report_dir)
    state["media"]["preview"] = {"path": str(path.relative_to(root)), "sha256": sha, "environment": environment,
                                 "report": str((report_dir / "report.json").relative_to(root)), "report_sha256": digest(report_dir / "report.json")}
    generate(root, state, "A08", {"preview_pfad": str(path.relative_to(root)), "preview_sha256": sha,
                                  "produktionsnotizen": ["Tatsächliche vom Menschen bereitgestellte Datei; technische Messung ist keine Inhaltsfreigabe."]}, status="produziert")
    stage_candidates(root, state, ["A08"])


def publication_valid(root: Path, state: dict) -> bool:
    from .gates import gate_valid
    publication = state.get("publication")
    if not publication or state["beispiel"] or not gate_valid(root, state, "G5a"):
        return False
    try:
        current(root, state, "A11")
        authorization = publication["authorization"]
        stored = read_json(root / authorization["record_path"])
        return (publication["artifact"] == state["artifacts"]["A11"]
                and stored == {k: v for k, v in authorization.items() if k != "record_path"}
                and stored["gate"] == "G5b" and not stored["simulated"]
                and stored["binding"]["previous"] == object_hash(state["gates"]["G5a"])
                and current(root, state, "A11")["inhalt"]["sichtbarkeit"] == "public")
    except (OSError, ValueError, KeyError, Blocked):
        return False


def process_final(root: Path, state: dict, path: Path, srt: Path, *, force=False):
    root = ensure_project_storage(root)
    from .media import inspect_video, validate_srt
    sha, srt_sha = digest(path), digest(srt)
    media = state["media"].get("final", {})
    environment = media_environment()
    if not force and media.get("sha256") == sha and media.get("srt_sha256") == srt_sha and media.get("environment") == environment and "A09" in state["artifacts"]:
        return
    if "A09" in state["artifacts"]:
        invalidate_artifact(root, state, "A09", "Neuer Finalexport / Untertitel")
    report_dir = inspection_directory(root, f"final-{sha[:16]}-{srt_sha[:8]}")
    report = inspect_video(path, report_dir)
    font = data_root() / "fonts" / "Montserrat-Bold.ttf"
    srt_report = validate_srt(srt, font_path=font if font.exists() else None)
    atomic_json(report_dir / "srt-report.json", srt_report)
    state["media"]["final"] = {"path": str(path.relative_to(root)), "sha256": sha, "environment": environment, "srt_path": str(srt.relative_to(root)),
                               "srt_sha256": srt_sha, "report": str((report_dir / "report.json").relative_to(root)),
                               "report_sha256": digest(report_dir / "report.json"),
                               "srt_report": str((report_dir / "srt-report.json").relative_to(root)),
                               "srt_report_sha256": digest(report_dir / "srt-report.json")}
    generate(root, state, "A09", {"final_pfad": str(path.relative_to(root)), "final_sha256": sha,
                                  "srt_pfad": str(srt.relative_to(root)), "srt_sha256": srt_sha,
                                  "aenderungen": ["Manuell bereitgestellter Finalexport; Inhalt erneut prüfen."]}, status="produziert")
    stage_candidates(root, state, ["A09"])
    generate(root, state, "A10", {"datei_sha256": sha, "technischer_report": report,
                                  "qa": {"ergebnis": "pruefung_unvollstaendig", "findings": [],
                                         "pflichtpruefungen": [{"name": "Echte Final-Inhalts-/Smartphone-/Hörprüfung", "status": "nicht_geprueft"}]}})


def refresh_final_assessment(root: Path, state: dict):
    """QA-Bewertung aus technischen Nachweisen und tatsächlich dokumentierten Reviews."""
    from .gates import require_media_qa, review_valid
    if not review_valid(root, state, "final"):
        return
    try:
        require_media_qa(root, state, "final")
    except Blocked:
        return
    artifact = current(root, state, "A10")
    if artifact["inhalt"]["qa"]["ergebnis"] == "freigabefaehig":
        return
    report = read_json(root / state["media"]["final"]["report"])
    summary = {"ergebnis": "freigabefaehig", "findings": [], "pflichtpruefungen": [
        {"name": "Technische Final-/SRT-Pflichtchecks mit tatsächlich dokumentierten Nachweisen", "status": "bestanden"},
        {"name": "Tatsächlich dokumentierte Final-Inhalts-/Smartphone-/Hörprüfung", "status": "bestanden"}]}
    generate(root, state, "A10", {"datei_sha256": state["media"]["final"]["sha256"], "technischer_report": report, "qa": summary})
    stage_candidates(root, state, ["A09", "A10"])
