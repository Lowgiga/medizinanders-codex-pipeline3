# MedizinAnders Codex-Pipeline

Lokale Produktionsumgebung für deutschsprachige Gesundheitsvideos. Codex übernimmt Planung, Recherche, unabhängige Claim-Prüfung, Skript, Szenenplan, Handoffs, Freeze und QA. **Menschliche Freigaben, reale Fachreviews, InVideo und YouTube bleiben echte manuelle Schritte.** Es gibt keinen Server und keine eigene OpenAI-API.

GitHub-Ziel dieser Umsetzung: [Lowgiga/medizinanders-codex-pipeline3](https://github.com/Lowgiga/medizinanders-codex-pipeline3), auf ausdrücklichen Betreiberwunsch öffentlich. Es enthält ausschließlich Pipeline-Code und synthetische Vorlagen; echte Produktionsdaten bleiben extern.

## Einmal installieren und einrichten

Voraussetzungen: Linux/macOS mit Python 3.11+, Git und Codex. Die mitgelieferte V1 verwendet Unix-Dateisperren. FFmpeg/ffprobe sind für Video-QA erforderlich; fehlende Werkzeuge werden als Blocker angezeigt.

Im Repository-Terminal:

```bash
./scripts/bootstrap.sh
source .venv/bin/activate
ma doctor
ma setup
ma approve G0
```

`ma setup` fragt die tatsächliche verantwortliche Person, Umgebung, Datenschutzregeln, verfügbaren Werkzeuge und InVideo-Möglichkeiten ab. G0 wird ausschließlich von dir im interaktiven Terminal bestätigt. **Dieses ausgelieferte Repository enthält keine reale Betriebsfreigabe.**

Öffne das Repository anschließend in Codex. Der Orchestrator liest [AGENTS.md](AGENTS.md), startet Rollen mit frischem Kontext und übernimmt ihre Dateihandoffs. Bestätigungen führt der Mensch in seinem Terminal aus.

## Erste echte Episode

```bash
ma new
```

Themenidee und Limits eingeben. Die Ausgabe nennt die Projekt-ID, beispielsweise `MA-20261003-001`. In Codex anschließend eingeben: „Führe `ma run MA-20261003-001` aus und arbeite gemäß AGENTS.md bis zum nächsten Human Gate weiter.“

Die wenigen Operator-Befehle:

```bash
ma run MA-20261003-001
ma status MA-20261003-001
ma approve G1 --project MA-20261003-001
ma resume MA-20261003-001
```

Die IDs im Beispiel durch deine tatsächliche ID ersetzen. Jeder Halt zeigt **WHY** und nummerierte **Next**-Schritte mit konkreten Dateien. Kein Gate wird automatisch gesetzt. Freigaben verlangen Namen und eine exakte Bestätigung, die die angezeigten Versionen/Hashes bindet.

Falls du bewusst den verfügbaren `codex exec`-Modus in G0 ausgewählt hast:

```bash
ma run MA-20261003-001 --execute-workers
```

Jede Rolle läuft dann als separate native Codex-Session in ihrem Jobverzeichnis. Fehlen Authentifizierung, Werkzeuge oder Webzugriff, bleibt der Auftrag ehrlich blockiert. Im Modus `native_session` startet der Codex-Orchestrator die tatsächlich verfügbaren Subagent-Tools. Ein gewöhnlicher Python-Prozess kann die Tools einer geöffneten Codex-Session nicht selbst aufrufen.

## Die manuellen Stellen

| Halt | Deine Handlung |
|---|---|
| G0 | Betrieb, Datenschutz, Umgebung und reale Tool-/InVideo-Fähigkeiten einmal bestätigen; bei Änderungen erneut. |
| G1 | Konkreten Themenauftrag und Ressourcen bestätigen. |
| G2 | Claims, Gegenbelege und Grenzen bestätigen; erforderliche echte medizinische/juristische Fachreviews dokumentieren. |
| G3 | Freeze und Produktionsauftrag prüfen, reale Kosten selbst akzeptieren, InVideo manuell bedienen. |
| G4 | Echte Vorschau vollständig auf Smartphone ansehen/anhören und prüfen. |
| G5a | Konkrete Finaldatei/SRT/Uploadpaket prüfen; danach ausschließlich privat hochladen. |
| G5b | Tatsächlich verarbeitete private YouTube-Fassung kontrollieren; danach selbst veröffentlichen. |

Fachreviews dokumentierst du **erst nach realer Prüfung**:

```bash
ma review-record MA-20261003-001 --kind medical
ma review-record MA-20261003-001 --kind legal
```

Der automatisch erstellte Ordner `review/` enthält die zutreffenden Fachpakete und Video-Checklisten. Eine KI-Bewertung `freigabefaehig` ersetzt keinen menschlichen Gate.

Wenn medizinischer oder juristischer Review erforderlich ist, wird nach BETA der **konkrete Skript-/Szenenwortlaut zusätzlich geprüft**, bevor G3 möglich ist. Die zutreffenden `*_PRODUCTION_REVIEW_PACKET.md` enthalten sämtliche Formulierungen, Titel, Thumbnail, Overlays und Szenen. Die vorherige Claim-Prüfung gilt ausschließlich für A01–A03:

```bash
ma review-record MA-20261003-001 --kind medical --stage production
ma review-record MA-20261003-001 --kind legal --stage production
```

Der InVideo-Halt nennt beispielsweise:

```text
STATUS: WAITING_FOR_HUMAN
BLOCKED_AT: G3_INVIDEO
1. Öffne .../handoff/invideo/INVIDEO_PROMPT.txt.
2. Erzeuge genau einen Entwurf und exportiere die tatsächliche Vorschau.
3. Lege sie unter .../08_produktion/inbox/preview.mp4 ab.
4. Führe ma resume MA-... aus.
```

Finaldatei und synchronisierte SRT gehören nach `09_postproduktion/inbox/final.mp4` und `final.srt`. Die konkreten absoluten Pfade stehen in der Ausgabe. Der InVideo-Prompt garantiert keine Exportparameter; die echten Dateien werden geprüft. Musik ohne belegbare getrennte Spuren wird entfernt. Montserrat Bold kann lokal unter `<Datenspeicher>/fonts/Montserrat-Bold.ttf` bereitgestellt werden; bei fehlendem Font wird keine Pixelbreitenprüfung erfunden.

Fehlende technische Encoderbelege erfordern einen qualifizierten tatsächlichen Nachweis. Gemessene Fehler lassen sich damit nicht überstimmen:

```bash
ma review-record MA-20261003-001 --kind technical --media final
ma resume MA-20261003-001 --recheck-media final
```

Eine erneute QA erzeugt eine neue Reportrevision und invalidiert die betroffenen Freigaben. Es wird niemals automatisch neu encodiert.

Der technische Review fordert für **jeden** ausdrücklich nicht geprüften Punkt einen eigenen tatsächlichen Nachweis. Ein unabhängiger offener K0/K1-Fehler bleibt blockierend.

Nach G5a und deinem tatsächlichen privaten Upload:

```bash
ma youtube-record MA-20261003-001
ma resume MA-20261003-001
ma review-record MA-20261003-001 --kind playback
ma approve G5b --project MA-20261003-001
# Jetzt persönlich auf YouTube veröffentlichen; erst danach:
ma published MA-20261003-001
```

Später reale Analytics als JSON gemäß [A12-Vorlage](templates/A12.json) importieren (`inhalt` oder nur dessen Objekt). Fehlende Kennzahlen bleiben `null` mit Begründung; Beobachtungen, Hypothesen und genau ein nächster Test werden getrennt:

```bash
ma analytics MA-20261003-001 --file /pfad/zu/echten/analytics.json
```

## Änderungen und Datenschutz

Artefakte und Freezes niemals direkt bearbeiten. Änderungen explizit zurückführen, danach Codex neu arbeiten lassen:

```bash
ma invalidate MA-20261003-001 --change source --reason "Originalquelle korrigiert"
ma resume MA-20261003-001
```

Quelle/Claim/Bedeutung führt zu ALPHA und erneutem G2; Wortlaut/Titel/Thumbnail/CTA zu BETA; Produktion/Untertitel/Export zu erneuter QA. Jede neue Version benötigt eine neue anwendbare Freigabe. Alte Artefakte, Gatebelege und Freeze-Revisionen bleiben erhalten. Patch-Versionen sind in V1 konservativ auf bedeutungsgleiche Leerraum-/Formatänderungen begrenzt.

Der freie `ma import` ist auf A01–A06 beschränkt. Freeze-, Medien-, Upload-/Veröffentlichungs- und Analyticsnachweise A07–A12 entstehen über die jeweils vorgesehenen Befehle. Ein I/O-Fehler bei einer Workerübergabe lässt den bisherigen gültigen Projektzustand erhalten.

Produktionsdaten liegen standardmäßig unter `~/.local/share/medizinanders/projects`, außerhalb des Repositories. Mit `MA_DATA_DIR` kannst du einen anderen **externen** Datenspeicher wählen. Vorschauen, Finaldateien und Quellen als echte lokale Dateien ablegen; Symlinks innerhalb eines Projekts werden blockiert. Keine Gesundheits-/Patientendaten, Tokens, Cookies oder Browserprofile ablegen. `.gitignore` und ein installierter Pre-Commit-Check schützen zusätzlich; sie ersetzen keine sorgfältige Auswahl dessen, was du in Codex eingibst. Das Repo enthält ausschließlich Code, Regeln, Schemas, Prompts, Vorlagen, Tests und Doku.

## DEMO und Tests

```bash
python -m unittest discover -s tests -v
ma demo --data-dir /tmp/medizinanders-demo
```

Der komplette synthetische Dry Run erzeugt A01–A10, simuliert ausschließlich ausdrücklich markierte DEMO-Gates G0–G3, erzeugt Freeze/Handoffs und eine echte kleine FFmpeg-Testdatei. Sie ist absichtlich kein Produktionsvideo. G4/G5a/G5b bleiben offen. Keine Recherche-/InVideo-/Fachprüfungsleistung wird vorgetäuscht; die Worker-Ausgaben sind deterministische Testdoubles. Tests prüfen zusätzlich Gate-Erfolgspfade mit expliziten DEMO-Testdoubles. DEMO lässt sich nicht produktiv freigeben.

Für ein eigenes privates Repository gibt es zusätzlich das folgende Skript. Es benötigt eine tatsächlich berechtigte GitHub-Anmeldung und ein ungesetztes oder bereits zum privaten Ziel passendes `origin`:

```bash
./scripts/publish-private.sh
```

Das Skript prüft Git-Historie, sauberen Arbeitsstand und private Sichtbarkeit vor dem Push. Die oben genannte öffentliche Ablage ist das ausdrücklich gewählte Ziel dieser Lieferung. Keine Tokens in Dateien, Befehle oder Git-URLs schreiben.

Weiterführend: [Pipeline](docs/pipeline.md), [Architektur](docs/architecture.md), [Human Gates](docs/human-gates.md), [Manuelle Schritte](docs/manual-steps.md), [Sicherheit](docs/security.md), [Abweichungen zur manuellen Pipeline](docs/deviations-from-manual-spec.md).
