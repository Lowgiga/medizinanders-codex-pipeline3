# Datenschutz und Git-Sicherheit

Das Repository enthält ausschließlich Pipeline-Code, Regeln, Schemas, Prompts, synthetische Vorlagen, Tests und Dokumentation. Produktionsprojekte liegen standardmäßig außerhalb Git unter `~/.local/share/medizinanders/projects`. Die lokale Betreiberkonfiguration entsteht im Datenspeicher. `config/operator.example.yaml` bleibt eine Vorlage ohne reale Personen-/Kontodaten.

## Was nie ins Git gehört

Patientendaten und private Gesundheitsinformationen, Produktionsquellen, nichtöffentliche Dokumente, Videos/Audio/Thumbnails, Reviewidentitäten und Freigaben, Tokens, API-Keys, Cookies, Browserprofile, Credentials, `.env` und private Konfiguration. Auch öffentliche Produktionsquellen werden lokal gehalten, weil der Repositoryzweck Code/Regeln ist. Die `.gitignore` schließt gängige Projekt-, Medien-, Quellen-, Secret- und lokale Konfigurationspfade aus.

Eine `.gitignore` verhindert keinen ausdrücklich erzwungenen Commit. Nutze für echte Projekte nie `git add -f`. Vor einem Commit `git diff --cached` prüfen und nur Code-/Doku-/synthetische Testdateien stagen. Vor einem Push zusätzlich die vollständige Git-Historie auf sensible Inhalte scannen; ein sauberer letzter Commit genügt nicht. Bereits getrackte sensible Dateien werden durch `.gitignore` nicht rückwirkend entfernt. Bei versehentlich veröffentlichtem Secret: Credential sofort widerrufen/rotieren, betroffene Zugriffe prüfen und Repositoryhistorie kontrolliert bereinigen; bloßes Löschen in einem Folgecommit genügt nicht.

## Daten minimieren

Gesundheitsjournalismus benötigt hier keine individuellen Patientendaten. Solche Eingaben nicht in Workerprompts, externe Dienste oder Produktionsdateien übernehmen. Wenn reale Eingaben private Personen-/Gesundheitsinformationen enthalten, stoppen und Datenschutz-/Rechtsprüfung anstoßen. Quellen mit echten Fällen nur nach geprüftem rechtlichem Rahmen und ohne unnötige identifizierende Details nutzen.

Webrecherche verwendet öffentliche Quellen oder rechtmäßig bereitgestellte Dokumente. Keine Zugangssperren umgehen. Downloadkopien bleiben lokal; Quelle, Zugriffszeitpunkt und Hash sichern. Keine Cookies/Headers/Tokens in Logs oder Prompts. Ein Link ist kein Rechtebeleg für Mediennutzung.

## Lokale Verantwortung

G0 entscheidet konkrete Zugriffsrechte, Speicherort, Backups, Löschfristen und externe Dienste. Das ausdrücklich durch den Auftraggeber gewählte GitHub-Ziel `https://github.com/Lowgiga/medizinanders-codex-pipeline3` ist öffentlich; es enthält ausschließlich Pipeline-Code, Regeln und synthetische Materialien. Produktionsdaten gehören unabhängig von der Repositorysichtbarkeit niemals ins Git. Betriebssystemnutzer und Personen mit Zugriff auf `MA_DATA_DIR` können die lokalen Inhalte lesen; diese Pipeline verschlüsselt sie nicht automatisch. Keine gemeinsam veröffentlichte Cloudablage als Standard setzen.

Native Codex-Worker erhalten begrenzte Dateiinputs. Die gemeinsame Arbeitsumgebung ist keine Betriebssystem-Sandbox. Rollen sind angewiesen, ausschließlich die erlaubten Inputs zu lesen; der Orchestrator kontrolliert Outputs. Codex-/InVideo-/YouTube-Datenübermittlung und tatsächliche Kontoeinstellungen müssen vom Betreiber geprüft werden.

## Integrität und Gates

Atomische Dateien/Sperren reduzieren gleichzeitige Schreibfehler. SHA-256 bindet Artefakte, Freeze und reale Medien. Hashes sind keine Inhalts-, Identitäts- oder Rechteprüfung. Freigaben liegen außerhalb des Freeze und enthalten verantwortlichen Namen/Zeitpunkt. Gültigkeit wird aus der aktuellen Bindung, nicht allein aus einem gespeicherten `status` abgeleitet.

Schreibpfade werden auf ihren tatsächlichen Speicherort geprüft. Symlinks innerhalb eines Produktionsprojekts sind unzulässig, auch wenn sie auf eine andere Datei desselben Projekts zeigen. Das verhindert umgeleitete Jobs, Reviews, Handoffs, QA-Protokolle und nachträgliches Überschreiben eines Freeze. Vorschau/Finaldatei und Quellen als tatsächliche lokale Dateien ablegen. Diese Prüfung ersetzt keine Betriebssystem-Sicherheitsgrenze gegen einen gleichzeitig manipulierenden lokalen Benutzer.

Keine Agentrolle darf eine reale menschliche Fachprüfung, ein Gate oder tatsächlichen Render/Upload/Playback vortäuschen. DEMO-Daten sind eindeutig `beispiel: true` und strikt von produktiven Freigaben getrennt. Fixtures werden niemals auf YouTube hochgeladen. Logs und Fehlermeldungen dürfen keine Secrets aus Umgebungsvariablen oder Dateiinhalten ausgeben.

## Rechte und Täuschung

Assets benötigen echte Bild-/Musik-/Stimm-/Zitatrechtsbelege. Offene Rechtefragen blockieren betroffene Claims/Assets, bei zentralem Material die Episode. KI-Illustrationen dürfen nicht als echte Beweise erscheinen. Keine imitierte fremde Stimme und keine gespielte ärztliche Autorität. Kosten bestätigt der Mensch in der tatsächlichen Anwendung; Codex akzeptiert keine Gebühren im Namen des Betreibers.
