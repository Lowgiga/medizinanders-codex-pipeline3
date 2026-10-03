# Abschließender unabhängiger Red-Team-Review

Datum: 2026-10-03. Geprüft wurde das vollständige lokale Repository mit frischem Reviewer-Kontext. Der Reviewer änderte ausschließlich diesen Bericht; Core, Schemas, Rollenprompts und Tests wurden durch die zuständigen Implementierungsagenten geändert. Kein Commit, keine reale Freigabe, keine Produktion, kein Upload und keine Veröffentlichung wurden ausgeführt.

## Gesamtbeurteilung

**Technischer Review abgeschlossen.** Alle elf konkret reproduzierten Befunde R01–R11 wurden korrigiert und unabhängig nachgeprüft; im geprüften Umfang bleibt kein konkret reproduzierter offener K0/K1-Befund. Der abschließende Vollauf besteht mit **178 Tests, OK**. Quellen-, Gate-, Freeze- und Medienhashes werden erneut geprüft; getrennte Fachreviewumfänge, fehlende Messungen, reale Produktionshandoffs und Rückwege blockieren an den geprüften Stellen wie vorgesehen. Der DEMO-Durchlauf endet mit unbestätigtem G4/G5a/G5b und ohne Upload oder Veröffentlichung.

Die Implementierung wurde durch die zuständigen Implementierungsagenten während dieses Reviews korrigiert. Die Schweregrade unten beschreiben die ursprünglichen Fehler. `offen: false` bedeutet, dass der Reviewer den konkreten ursprünglichen Repro erneut ausgeführt und die Korrektur bestätigt hat. Der abschließende technische Bericht ersetzt keine tatsächliche Betreiber-, medizinische, juristische oder Medienfreigabe und setzt keines der Human Gates.

## Prüfung und Belege

- Gelesen: AGENTS.md, README, Architekturreview, Implementierungsvertrag, alle Pythonmodule, Schemas, Rollenprompts, Kanalregeln, Tests und manuellen Betriebsanweisungen.
- Ausgangsprüfung: `python -m unittest discover -s tests -v`, **121 Tests, OK**. Abschließende unabhängige Nachprüfung desselben Befehls auf dem endgültigen Quellstand: **178 Tests in 28,828 s, OK**; Log: `/tmp/ma-red-team-final-178-tests.log`. Neue Regressionen prüfen die tatsächlich gefundenen Grenzfälle, einschließlich teilweise vorhandener falscher Medienwerte, Writerfehler, Produktionsfachreviews, Symlinks und erreichbarer Git-Historie.
- Zusatzrepros: ausschließlich synthetische DEMO-Projekte, In-Memory-Testdoubles und isolierte Git-/Repositorydummys unter `/tmp`. Skripte: `/tmp/ma-red-team-repros.py` und `/tmp/ma-red-team-final-boundaries.py`; letzte Ergebnisse: `/tmp/ma-red-team-final-repros.log` und `/tmp/ma-red-team-final-boundaries.log`. Sämtliche R01–R11 sowie die spät gefundenen R06-Unterfälle wurden erneut ausgeführt. Diese temporären Pfade sind lokale Reviewbelege und keine portablen Repositorytests.
- README-Installation: `scripts/bootstrap.sh` in einer isolierten Repositorykopie tatsächlich ausgeführt, danach dort `ma doctor` und `ma demo --data-dir /tmp/ma-red-team-bootstrap-demo` erfolgreich ausgeführt. Ergebnis: `DEMO_COMPLETE`, Freeze `r001`, G4/G5a/G5b offen, kein Upload/keine Veröffentlichung. Shellsyntax und CLI-Befehlsnamen stimmen. Produktive interaktive Befehle wurden nicht ausgeführt; GitHub-Push wurde nur statisch und mit lokalem Git-Repro geprüft.
- Aktueller DEMO-End-to-End-Lauf: `ma demo --data-dir /tmp/ma-red-team-final-stable-demo`, Ergebnis `/tmp/ma-red-team-final-stable-demo.json`: `DEMO_COMPLETE`, A01–A10, Freeze `r001` zusätzlich unabhängig mit `verify_freeze` bestätigt, jeweils neun InVideo-/YouTube-Handoffdateien, simulierte G0–G3, G4/G5a/G5b unbestätigt, `real_upload=false`, `real_publication=false`. FFmpeg erzeugt eine klar bezeichnete synthetische 2-s-Datei außerhalb des geforderten 58-s-Profils; sie gilt ausdrücklich nicht als InVideo-Produktion oder erfolgreiche Medienfreigabe.
- Bestehende Negativtests decken unter anderem Artefakt-/Gate-/Freeze-/Quellenmanipulation, fehlende Originale, falsche Medienhashes, fehlende Kennzeichnungen, SRT-/Codec-/CFR-Fehler, fehlende Pflichtchecks, ungültige DEMO-Freigaben und erneute QA nach Dateiveränderung ab.
- Auf dem tatsächlichen Repository bestehen auch `python scripts/check_repository.py --history`, `python scripts/check_repository.py --staged` und der Diff-Whitespacecheck des Berichts. Der Reviewer hat keine Änderungen gestagt oder committed.

## Findings

### R01 — Quellenkopie vor der Prüfung untrusted Identifier

- **datei:** `src/medizinanders/pipeline.py`, `complete_job` / `_complete_job`, A02-Quellenimport.
- **problem:** Eine unvalidierte Quelle-ID wurde bereits als Zielpfad verwendet.
- **soll:** Schema und aufgelöste Quell-/Zielcontainment müssen vor jeder Dateimutierung geprüft werden; abgelehnte Worker-Ausgaben dürfen keine Quelle außerhalb des Projekts ablegen.
- **ist:** Der Ausgangsrepro setzte `quelle_id` auf einen absoluten `/tmp/...`-Pfad. Der Import kopierte die synthetische Quelle dort hin und brach erst danach bei `relative_to(root)` ab. Der neue Repro blockiert jetzt mit A02-Schemafehler; außerhalb wurde keine Datei mehr geschrieben.
- **schwere:** K1.
- **rueckweg:** Importer: vorab Schema-/Containmentprüfung und konsistente Quelle-ID-Regeln; Quellenkopien erst nach vollständiger Outputvalidierung übernehmen.
- **offen:** false.

### R02 — BETA fehlen die Original-URLs für die Pflichtausgabe

- **datei:** `src/medizinanders/workers.py`, `ROLE_INPUTS`; `schemas/A03.schema.json`; `validation.py`, Prüfung von A05-Quellenangaben.
- **problem:** BETA erhielt nur A03 mit Quellen-ID/Fundstelle, musste aber die exakte, ausschließlich in A02 vorhandene Original-URL in A05 ausgeben.
- **soll:** Der minimale erlaubte Kontext enthält die geprüften Publikationsdaten der verwendbaren Claimbelege, ohne fremde Rechercheargumentation oder zusätzliche Originale.
- **ist:** Eine eindeutig bezeichnete synthetische A02-URL war zunächst in keinem BETA-Input verfügbar; `preflight` fordert URL-Gleichheit mit A02. Nach dem Fix wird ein aus der gebundenen Claim-/Quellenbasis abgeleiteter Katalog in A03 materialisiert; dieselbe URL ist nun im BETA-Input vorhanden. BETA erhält weiterhin keine fremden Jobs oder das vollständige A02.
- **schwere:** K1.
- **rueckweg:** Orchestrator-/Schemakontrakt: minimalen geprüften Quellenkatalog binden und seinen Widerspruch zur Originalbasis ablehnen.
- **offen:** false.

### R03 — Bekannte falsche Medienwerte werden zu fehlenden Prüfungen

- **datei:** `src/medizinanders/media.py`, `_probe_stream`, `_check_frames`, B-Frame-Prüfung.
- **problem:** Einige kombinierte Prüfungen verlieren einen bereits bekannten Fehler, sobald ein anderer erforderlicher Messwert fehlt.
- **soll:** Ein vorhandener falscher Pflichtwert bleibt `fehlgeschlagen`; fehlende Begleitwerte dürfen diesen Fehler nicht in einen technisch ergänzbaren Prüfpunkt verwandeln.
- **ist:** Ursprünglich lieferte `_probe_stream` für `r_frame_rate=24/1` bei fehlendem zweiten FPS-Wert sowie `channels=1` bei fehlendem Layout jeweils `nicht_geprueft`. Im abschließenden identischen Repro sind `fps_30` und `audio_stereo` beide `fehlgeschlagen`. Die gemeinsamen Kombinationsprüfungen behandeln bekannte Fehler vor fehlenden Werten; Regressionen erfassen auch Dauer, Auflösung, Progressivstatus, Pixelformat, GOP/B-Frames, Paketbitrate, teilweise Loudnessdaten und Glyphenmessungen.
- **schwere:** K1.
- **rueckweg:** Medien-QA: bekannte Abweichungen zuerst auswerten; nur ohne bekannten Fehler auf `nicht_geprueft` zurückfallen. Regressionen für teilweise vorhandene Metadaten.
- **offen:** false.

### R04 — Ein fehlender Prüfpunkt unterdrückt sämtliche offenen Findings

- **datei:** `src/medizinanders/gates.py`, `require_media_qa`.
- **problem:** Die Prüfung offener K0/K1-Findings war global an `not missing` gekoppelt.
- **soll:** Ein tatsächlicher technischer Nachweis ergänzt ausschließlich die exakt bezeichneten fehlenden technischen Prüfungen. Ein unabhängiges offenes K0/K1-Finding bleibt blockierend.
- **ist:** Ursprünglich erlaubte ein ausdrücklich als DEMO-Testdouble erzeugter, hashgebundener Report mit einer fehlenden Prüfung und einem zusätzlichen offenen K0-Finding nach simuliertem technical-/preview-Review eine gültige G4-Simulation. Derselbe abschließende Repro blockiert jetzt ausdrücklich am unabhängigen offenen K0/K1; G4 bleibt ungültig. Eine technische Ergänzung benötigt genau einen bezeichneten `technical_evidence`-Beleg für jeden tatsächlich fehlenden Video-/SRT-Prüfpunkt. Gemessene Fehler und unabhängige offene Findings bleiben blockierend. Das ist ein Validatorrepro, keine Behauptung über einen tatsächlich gemessenen Produktionsfehler.
- **schwere:** K1.
- **rueckweg:** Gate-/Reportkontrakt: Findings eindeutig dem Prüfpunkt und dem fehlenden bzw. fehlgeschlagenen Status zuordnen; nur tatsächlich ergänzte Missing-Findings behandeln, alle übrigen offenen K0/K1 ablehnen.
- **offen:** false.

### R05 — Fehlgeschlagene Writes verändern den angenommenen Projektzustand

- **datei:** `src/medizinanders/pipeline.py`, `complete_job`, `put_artifact`; `cli.py`, abschließende Statepersistierung.
- **problem:** Vollständige Schemavalidierung stellt allein keine atomische Übernahme sicher. Die ursprüngliche Workerübernahme und der direkte Import veränderten den State vor erfolgreichem Abschluss aller Writes.
- **soll:** Bei einem Writefehler bleiben bisherige Artefaktreferenzen, Gates und Jobstatus erhalten; neue Teiloutputs werden nachvollziehbar verworfen, der Operator erhält einen Blocker.
- **ist:** Ein injizierter A05-Writefehler hinterließ ursprünglich registriertes und persistiertes A04 bei unvollständigem BETA-Job. Der neue Workerwrapper rollt State und neu angelegte Artefakt-/Quelldateien zurück; im erneuten Repro bleiben A04–A06 unregistriert, A04 unpersistiert und der Job unvollständig. Ursprünglich invalidierte auch ein fehlgeschlagener direkter A01-Import die alte A01 samt G1. Jetzt schreibt `put_artifact` die neue Version vor der Invalidierung; der erneute injizierte Writefehler erhält alte Referenz und G1. Ein fehlgeschlagener exklusiver JSON-Write entfernt seine angelegte Teildatei.
- **schwere:** K1.
- **rueckweg:** Storage/Importer: neue Datei vor der Invalidierung erfolgreich erstellen oder gesamte Übernahme inklusive Stateänderung zurückrollen. Nach Fehlern dürfen keine still verlorenen aktuellen Referenzen übrig bleiben.
- **offen:** false.

### R06 — Externer Datenspeicher umgeht über Unterpfadsymlink die Repositorygrenze

- **datei:** `src/medizinanders/storage.py`, `data_root`, `ensure_contained`, `ensure_project_storage`, Writer und Lock; `pipeline.py`, `workers.py`, `handoffs.py`, `gates.py`, `cli.py`, `media.py`, Produktionswrite-Ziele.
- **problem:** Nur der oberste Datenspeicher war auf Repositoryabstand geprüft. Die erste Korrektur erfasste noch nicht alle direkten Writer; ein umgeleiteter Jobs-Unterpfad schrieb weiterhin die Themenidee in einen Repositorydummy.
- **soll:** Aufgelöste Projekt-/Artefakt-/Quellen-/Job-/Review-/Freeze-/Handoff-/Report-/Analytics-/Operatorpfade bleiben im erlaubten externen Speicher und außerhalb des Repositories; auch einzelne Zielsymlinks dürfen keine externen Dateien verändern.
- **ist:** Der ursprüngliche `projects -> Repository`-Repro und der später gefundene `jobs -> Repositorydummy`-Repro blockieren jetzt vor jeder Produktionserstellung. Im letzten Repro bleiben Jobs-Ziel und State unverändert. Eine einzelne `TITLE.txt`-Symlinkdatei blockiert vor dem Handoff; der externe Sentinel bleibt unverändert. Ein einzelner `decode.log`-Symlink liefert `pruefung_unvollstaendig` mit `berichte_gespeichert=nicht_geprueft`, ohne Messaufruf, Reportwrites oder Änderung des externen Ziels. Die Containmentprüfung verwirft auch interne Symlinks im lexikalischen Zielpfad; der Projektguard prüft alle vorhandenen Projektsymlinks vor Mutationen. Elf neue Regressionen prüfen diese Writergrenzen; unsichere Berichtverzeichnisse bleiben direkt blockiert.
- **schwere:** K1.
- **rueckweg:** Storage: aufgelöste tatsächliche Unterpfade prüfen, Symlinkescapes blockieren; keine echte Produktionsdatei als Reprobeleg ins Repository schreiben.
- **offen:** false.

### R07 — Fachreviewpaket wächst um nicht fachlich geprüften Skriptwortlaut

- **datei:** `src/medizinanders/gates.py`, `review_binding`; `handoffs.py`, `review_packets`.
- **problem:** Der ursprüngliche medizinische Review band A01–A03, während derselbe Fachreviewpacketpfad später mit A05-Publikationsformulierungen überschrieben wurde. Eine neue Prüfung dieses Wortlauts war nicht gebunden.
- **soll:** Der tatsächlich geprüfte Umfang ist unverwechselbar. Neu hinzugekommener oder geänderter klinischer Publikationswortlaut wird entweder erneut fachlich geprüft oder im Paket eindeutig als ungeprüft geführt und erforderlichenfalls blockiert.
- **ist:** Ursprünglich enthielt nach BETA dasselbe Packet die neue A05, obwohl ausschließlich die Claimbasis geprüft war. Jetzt bleiben Claimreview (`--stage claims`) und A01–A03-Paket unverändert. Getrennte medizinische/juristische Produktionspakete enthalten vollständig A05 und A06; `--stage production` bindet A01–A06. Der unabhängige Repro bestätigt: G2/Claimreview bleiben gültig, G3 blockiert ohne relevanten Produktionsfachreview und erfüllt diese Voraussetzung erst nach ausdrücklich simulierter zusätzlicher Produktionsprüfung. Änderungen an A05/A06 widerrufen den Produktionsreview; Tests prüfen medizinische und juristische Umfänge. Eine tatsächlich medizinisch falsche Aussage wurde mit diesem Integritätsrepro nicht behauptet.
- **schwere:** K1.
- **rueckweg:** Fachreviewkontrakt: klinische A05-Publikationsformulierungen in den anwendbaren Reviewumfang aufnehmen und neu bestätigen lassen; geprüfte Claims und ungesichteten späteren Wortlaut im Paket klar unterscheiden.
- **offen:** false.

### R08 — Offensichtliche Wirksamkeitsaussage überspringt die Review-Eskalation

- **datei:** `src/medizinanders/gates.py`, `review_requirements`.
- **problem:** Medizinische Reviewpflicht hängt von einem KI-Boolean und einer begrenzten Wortstammliste ab.
- **soll:** Eine konkrete klinische Wirksamkeitsaussage darf bei irrtümlich falschem Boolean nicht ohne medizinischen Pflichtreview in die Gatevorlage gelangen.
- **ist:** Der ursprüngliche In-Memory-Negativtest mit `aussage="Dieses Mittel senkt den Blutdruck."`, `medizinisch=false` und leerer Risikoliste lieferte `required_reviews=[]`. Derselbe abschließende Repro verlangt jetzt `medical`; die konservativ erweiterte klinische Erkennung eskaliert unabhängig vom falschen Boolean. Die Regression bestätigt den G2-Blocker bei fehlendem Fachreview. Die Wortstammerkennung ersetzt keine semantische oder medizinische Prüfung aller denkbaren Formulierungen. Es wurde keine reale medizinische Prüfung oder Freigabe simuliert als produktiv ausgegeben.
- **schwere:** K0.
- **rueckweg:** Konservative Eskalation für relevante klinische Formulierungen; ALPHA-/QA-Vorgaben und menschliche G2-Prüfung dürfen diese Pflicht nicht aus einem falsch gesetzten Agentenflag ableiten. Deeskalation muss begründet und nachvollziehbar bleiben.
- **offen:** false.

### R09 — Generischer Import umgeht Operator-/Veröffentlichungsabhängigkeiten

- **datei:** `src/medizinanders/pipeline.py`, `put_artifact`; `cli.py`, `import` gegenüber `analytics`.
- **problem:** Der freie Import akzeptierte auch orchestrator-/operatorgebundene A07–A12.
- **soll:** A12 entsteht erst über einen nachvollziehbaren Analyticsimport nach dokumentierter Veröffentlichung; A11 entsteht aus tatsächlich menschlich zurückgemeldeten Plattformdaten.
- **ist:** In einer DEMO-Kette mit privater A11 und ohne G5b/Publicationreceipt akzeptierte der generische Import A12, während `publication_valid=false` war. Der gesonderte Analyticsbefehl blockiert diesen Fall bereits. Nach dem Fix lehnt der freie Import A12 ab und nennt die zugelassenen A01–A06 bzw. den erforderlichen Spezialbefehl.
- **schwere:** K1.
- **rueckweg:** Importoberfläche auf fachliche A01–A06 begrenzen; Spezialartefakte ausschließlich in ihren überprüften Orchestrator-/Operatorabläufen erzeugen.
- **offen:** false.

### R10 — Status zeigt nach Widerruf weiterhin die Veröffentlichungsanweisung

- **datei:** `src/medizinanders/cli.py`, `status`; `pipeline.py`, Invalidierung.
- **problem:** `last_status` wurde nach einer Invalidierung ohne ausreichende Aktualitätsprüfung ausgegeben.
- **soll:** Bei ungültigem G5b darf keine aktuelle Operatoranweisung zur Veröffentlichung erscheinen. WHY und Next müssen zum angezeigten Gatestatus passen.
- **ist:** Nach G5b-Simulation und anschließender `meaning`-Invalidierung meldete `ma status` G2–G5b als offen/veraltet, aber zugleich „Menschliche Veröffentlichungsfreigabe liegt vor“ und „Stelle das geprüfte Video selbst auf öffentlich“. Nach dem Fix zeigt derselbe Repro nur den erforderlichen Resume zur Ermittlung des aktuellen nächsten Schritts; keine Veröffentlichungsanweisung mehr.
- **schwere:** K1.
- **rueckweg:** Status aus aktueller Gate-/Artefaktbasis ableiten oder gespeicherte Handoffs nur bei nachgewiesener unveränderter Bindung ausgeben.
- **offen:** false.

### R11 — Publishprüfung scannt den Index, der Push überträgt HEAD

- **datei:** `scripts/check_repository.py`, `check`; `scripts/publish-private.sh`.
- **problem:** Die ursprüngliche Sicherheitsprüfung kontrollierte `git ls-files` und `git show :PFAD`, während `git push origin main` tatsächlich Commits einschließlich Historie überträgt.
- **soll:** Der Publishpreflight prüft die tatsächlich zu übertragenden Commits/Blobs auf verbotene Produktionsdateien und Secretmuster. Eine nur gestagte Löschung kann bereits committed Inhalte nicht aus dem Push entfernen.
- **ist:** Im lokalen Gitdummy wurde ausschließlich eine synthetische, verbotene `operator.yaml` committed und danach nur aus dem Index gelöscht. Der Indexcheck meldet weiterhin korrekt Exit 0 für den aktuellen Index; der neue `--history`-Check blockiert im wiederholten Repro mit Exit 1 wegen der committed Datei. Er prüft alle erreichbaren Commitbäume und Blobs einschließlich verbotener Pfade, Symlinks, Größe und Secretmustern. Das Publishskript führt diese Historyprüfung vor dem Push aus und fordert einen sauberen Arbeitsstand. Die Securitytests prüfen auch Dateien in älteren Commits und anderen erreichbaren Branches. Kein Netzwerkpush wurde ausgeführt.
- **schwere:** K1.
- **rueckweg:** Separate Commit-/Historyprüfung vor Push; gestagter Pre-Commit-Check bleibt bestehen. Verbotene Daten aus nicht veröffentlichter History entfernen und danach erneut prüfen.
- **offen:** false.

## Geprüfte Grenzen und Rückwege

`meaning`/`claim` führt technisch zu A03/ALPHA und widerruft G2 samt Folgeartefakten; `source` führt zu A02/RESEARCH und anschließend ALPHA; `wording` führt zu BETA und belässt die unveränderte Claimbasis. Die Bedeutungstreue eines als `wording` bezeichneten Edits wird bewusst durch den frischen unabhängigen `factuality`-/`claim_mapping`-Review geprüft. Eine rein syntaktische Claim-ID-Zuordnung beweist keine Bedeutungstreue; der Review darf eine Bedeutungsänderung nur nach ALPHA und neuem G2 weitergeben. Hier wurde kein zusätzlicher automatischer Semantikbeweis behauptet.

Native Rollen erhalten die angegebenen Dateiinputs und frischen Kontext laut Orchestratorprompt. Die gemeinsame Codex-Umgebung ist ausdrücklich keine OS-Sandbox; das wird ehrlich dokumentiert. Ein Pythonprozess ruft keine erfundenen nativen Sessiontools auf. Bei `codex exec` prüft der Adapter die tatsächlichen erforderlichen Flags, nutzt eine separate Session und importiert anschließend konkrete Outputs. Keine eigene OpenAI-API oder automatische InVideo-/YouTube-Uploadfunktion wurde gefunden.

Die dokumentierte Operatorattestierung kann lokale Software nicht als reale Identität oder fachliche Qualifikation beweisen. Das ist eine erklärte Betriebsgrenze. Der Reviewer wertet deshalb interaktive Namen, echte Fachprüfungen, Smartphone-/Hörprüfungen und veröffentlichte Plattformdaten nicht als im Review tatsächlich durchgeführt. DEMO-/In-Memory-Erfolgstests bleiben ausdrücklich synthetisch.

Nicht als tatsächlich durchgeführt gewertet werden eine reale Originalquellenrecherche mit medizinischer/juristischer Inhaltsprüfung, ein produktiver nativer Worker-Durchlauf, eine 58-s-InVideo-Produktion mit Smartphone-/Hörprüfung, tatsächliche Kostenannahme, Plattformupload, Veröffentlichung oder echte Analytics. Die Regressionen und DEMO-Worker prüfen Softwareverträge, Hashbindung und Rückwege mit synthetischen Daten; sie belegen diese externen Handlungen nicht. Der vollständige reale Episodenbetrieb bleibt menschlich zu betreiben und an den Gates nachzuweisen. Auch ein öffentlicher GitHub-Push wurde in diesem Review nicht ausgeführt.

Ein Produktions-G0 und sämtliche realen Episodengates bleiben ausschließlich vom zuständigen Menschen zu bestätigen. Die geschlossenen technischen Befunde erlauben die Übergabe des geprüften Builds; sie erteilen keine Produktions- oder Veröffentlichungsfreigabe.
