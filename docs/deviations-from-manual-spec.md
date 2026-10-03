# Abweichungen zur manuellen 12-Schritt-Pipeline

Diese V1 automatisiert die bisher manuell reproduzierbare Architektur. Sie ändert Arbeitsmittel und Dateiübergaben, erhält jedoch Verantwortung, Fachreview, reale Produktion und Veröffentlichung als menschliche Schritte.

| Bisher | Codex-native V1 |
|---|---|
| Getrennte Mistral-Chats | Frische Codex-Subagents mit eng begrenztem Jobkontext und Rollenprompt. Kein vorausgesetzter permanent benannter Agent. |
| Manuelle Perplexity-Recherche | RESEARCH-Worker mit tatsächlich vorhandenen Web-/Abrufwerkzeugen. Fehlen sie, konkrete Originalquellen als manueller Input; keine erfundene Recherche. |
| Manuelle Dateiübergabe | Orchestrator erstellt Input-/Output-Jobs, prüft Abhängigkeiten und importiert versionierte Artefakte. |
| Manuell gestartete deterministische Checks | Schema-, Cross-, Timeline-, Gate-, Freeze-, SRT- und tatsächliche Medienprüfungen soweit messbar automatisch. |
| Manuelles Hashing | SHA-256 und unveränderliche Freeze-Revisionen automatisch. |
| Manuelle Dokumenterstellung | Strukturierte Artefakte, Reviewpakete und vollständige Handoffs automatisch vorbereitet. |

## Bewusst unverändert

- Menschliche Verantwortung und G0, G1, G2, G3, G4, G5a, G5b.
- Echte medizinische Fachprüfung bei relevanten Gesundheitsentscheidungsrisiken und Rechtsprüfung bei relevanten Rechtsfragen.
- InVideo als tatsächlich manuell bedienter Produktionsschritt samt Kostenentscheidung.
- Prüfung der echten Vorschau und Finaldatei, menschliche Smartphone-/Hör-/Lesbarkeitsprüfung.
- Privater YouTube-Upload durch den Menschen, tatsächliche Plattformkontrolle und menschliche Veröffentlichungsentscheidung.
- Keine erdachten Quellen, Studien, Zugriffsmeldungen, Messwerte, Analytics oder Durchführung.

## Präzisierungen für Reproduzierbarkeit

Artefakte werden als UTF-8 JSON gespeichert und über JSON Schema geprüft; JSON bleibt gültiges YAML. Die Metadaten, Statuswerte, Claim-Status und Projekt-IDs entsprechen der Spezifikation. Gate-Nachweise bleiben extern, hashgebunden und interaktiv. Das historische Statusfeld einer unveränderten Artefaktdatei kann keine neue Freigabe beweisen.

A03 erhält einen deterministisch aus tatsächlich referenzierten A02-Originalquellen materialisierten bibliografischen Quellenkatalog. BETA bekommt dadurch Quellen-IDs/URLs/Titel/Zugriff/Hashes ohne den A02-Vollkontext. Medizinische/juristische Prüfung hat ausdrücklich getrennte Stufen: Claimreview auf A01–A03 vor G2 und anwendbarer Produktionsreview auf A01–A06 vor G3. Ein bereits erteilter Claimreview wird niemals stillschweigend um ein späteres Skript ergänzt.

Der Datenspeicher liegt standardmäßig außerhalb Git. Nur synthetische, eindeutig markierte Testdaten gehören unter `demo/`/`tests/`. Freigabekandidaten starten bei `1.0.0`; kein Patch/Minor/Major erbt die vorherige menschliche Entscheidung.

Der Auftraggeber hat im laufenden Auftrag ausdrücklich das öffentliche Ziel `https://github.com/Lowgiga/medizinanders-codex-pipeline3` gewählt. Diese Entscheidung ersetzt den anfänglichen Wunsch nach einem neuen privaten Repository. Vor Push wird die vollständige Git-Historie geprüft; Produktionsdaten und sensible Inhalte bleiben unverändert ausgeschlossen.

Freier Import ist auf A01–A06 begrenzt. A07–A12 entstehen ausschließlich über die passenden Orchestrator-/Operatorbefehle mit tatsächlichen Nachweisen. `ma status` zeigt einen kurzen aktuellen Überblick und verweist für konkrete Next-Schritte auf `ma resume`; `--json` liefert Details.

Die CLI ist kein nativer Codex-Agenthost. Sie erzeugt begrenzte Jobs; die tatsächliche Codex-Sitzung startet Subagents. Der optionale `codex exec`-Modus ist abhängig von der bestätigten Installation. Dateikontextgrenzen sind kein Betriebssystem-Sandboxversprechen.

## Grenzen dieser V1

Ein InVideo-Prompt garantiert keine Codec-/GOP-/Audio-/Untertitelparameter. FFmpeg-Prüfungen können messbare Dateiwerte prüfen, kein medizinisches Urteil und keine juristische Lizenz ersetzen. Fehlen getrennte Tonspuren, kann der Musikabstand nicht zuverlässig als gemessen gelten; Standard-Fallback Musik entfernen. Fehlende Tools, Schrift, Referenztranskription oder Prüfmöglichkeiten bleiben offene Pflichtprüfungen. Eine fachlich geeignete reale Person kann nicht automatisiert geprüfte technische Punkte durch einen eigenen `technical_evidence`-Beleg je Punkt ergänzen; gemessene Fehler und unabhängige offene K0/K1 bleiben Blocker und sind nicht überstimmbar.

Hashbindung ist eine Integritätskontrolle, keine digitale Signatur. Die Bestätigungs-CLI dokumentiert eine reale menschliche Selbstauskunft; sie verifiziert weder ärztliche Qualifikation noch reale Terminalbenutzeridentität automatisch. Der Betreiber muss echte fachliche Zuständigkeiten und Zugriffsrechte organisieren.

Ein synthetischer DEMO-Dry-Run beweist Zustandsübergänge und technische Fehlererkennung. Er besteht keine reale Fachprüfung, Smartphone-/Hörprüfung, InVideo-Produktion, YouTube-Kontrolle oder Veröffentlichung. Produktionsgates lehnen DEMO-Daten ab.
