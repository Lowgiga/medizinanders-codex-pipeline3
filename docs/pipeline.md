# Pipeline und Artefakte

Die Pipeline automatisiert die reproduzierbare journalistische Vorbereitung und deterministische Prüfung deutschsprachiger Gesundheitsvideos. Sie dokumentiert Unsicherheiten und stoppt vor realer menschlicher Verantwortung, Fachreview, InVideo, Kosten, privaten Uploads und Veröffentlichung.

## Der normale Betrieb

Einmalig `ma setup` ausführen, die realen G0-Entscheidungen treffen und selbst `ma approve G0` im Terminal bestätigen. Danach `ma new` ausführen, die Themenidee eingeben und die ausgegebene Projekt-ID verwenden. `ma run ID` startet die nächste zulässige Vorbereitung und zeigt Blocker sowie konkrete nächste Schritte. `ma status ID` zeigt einen kurzen aktuellen Gate-Überblick; `ma status ID --json` liefert Artefakte, Gategültigkeit, Freeze und dokumentierte Veröffentlichung. Aktuelle konkrete Schritte immer mit `ma resume ID` ermitteln; nach manuellen Handoffs setzt dieser Befehl fort. Ein früherer Veröffentlichungs-Next wird nicht als weiterhin gültiger Auftrag übernommen.

`WAITING_FOR_CODEX` bedeutet, dass ein vorbereiteter Datei-Job im nativen Codex-Kontext auszuführen ist. Der Orchestrator folgt `agents/orchestrator.md`, startet einen frischen Worker und importiert die Outputs mit `ma worker-complete ID --job JOB_ID`. Ein unerfahrener Betreiber kann Codex einfach die Anweisung geben: „Führe den vorbereiteten Job für dieses Projekt nach AGENTS.md aus.“ Danach zeigt die CLI den nächsten echten Gate. Eine CLI außerhalb einer Codex-Sitzung startet nicht von sich aus eine erfundene native Subagentfunktion.

## A01–A12 und Abhängigkeiten

| Artefakt | Inhalt / Erzeugung | Nächster Kontrollpunkt |
|---|---|---|
| A01 | GAMMA: Kernfrage, Nutzen, Zielgruppe, Scope/Ausschlüsse, Suchfragen, Format, Ressourcen, offene Entscheidungen | G1 vor Recherche |
| A02 | RESEARCH: tatsächliches Suchprotokoll, Originalquellen, Gegenbelege, Unsicherheiten | ALPHA |
| A03 | ALPHA: Faktenmatrix, atomare Claims, Belege/Fundstellen, Gegenbelege, Einschränkungen, Risiken, Einsatz, Psychologie-Map; Orchestrator ergänzt referenzierte Quellenbibliografie | Claimreviews und G2 |
| A04 | BETA: Formatprofil und vollständige Dramaturgie | Preflight |
| A05 | BETA: Sprechertext, Wortzahl, Satz-/Claim-Mapping, Untertitelbasis, Aussprache, Overlays, Titel/Thumbnail/Beschreibung/Quellen/CTA/Disclaimer | Preflight |
| A06 | BETA: vollständige Szenen, Asset-/Rechteverweise, eigenständig kopierbarer InVideo-Auftrag | Preflight |
| A07 | deterministische Cross-Checks, unabhängige QA, Freeze-Referenz und Manifesthash | Anwendbare Produktionsreviews und G3 |
| A08 | echte Vorschau, SHA-256 und tatsächliche Produktionsnotizen | technische QA, menschliche Vorschauprüfung, G4 |
| A09 | echte Finaldatei und SRT, Hashes, dokumentierte Änderungen | finale QA |
| A10 | technische Reports und QA der konkreten Finaldatei | G5a |
| A11 | reale private Video-ID/URL, Finalhash, Entscheidungen, später tatsächliche Veröffentlichung | Playback, G5b, menschliche Veröffentlichung |
| A12 | reale Analytics, fehlende Werte mit Begründung, Beobachtungen, Hypothesen, genau ein nächster Test | Auswertung, keine automatische Regeländerung |

Die Artefakte verwenden UTF-8 JSON, das zugleich gültiges YAML ist. Schemas und Vorlagen liegen unter `schemas/` und `templates/`. Alle Artefakte enthalten `artefakt_id`, `projekt_id`, `version`, `datum`, `autor`, `status`, `eingaben`, `quellen`, `offene_punkte`, `gesperrt`, `sperrgrund`, `beispiel`, `inhalt`. `eingaben` bindet Artefakt-ID, Version und SHA-256. Projekt-ID `MA-YYYYMMDD-NNN`.

Freier `ma import ID --file DATEI` ist ausschließlich für A01–A06 vorgesehen. A07–A12 entstehen über die passenden Orchestrator-/Operatorbefehle: Preflight/Freeze, echte Medienrückgabe mit `resume`, privater Uploadnachweis mit `youtube-record`, Veröffentlichungsnachweis mit `published`, reale Datenauswertung mit `analytics`. Ein JSON-Import kann diese tatsächlichen Nachweise nicht ersetzen.

Statuswerte exakt: `Entwurf`, `geprüft`, `freigegeben`, `produziert`, `veröffentlicht`. `gesperrt` ist ein unabhängiges Boolean-Feld mit nachvollziehbarem Sperrgrund. Der historisch gespeicherte Status ersetzt nie die Prüfung eines aktuellen Gates. Outputs eines Workers sind keine menschliche Freigabe.

## Versionsregeln

Erster Entwurf `0.1.0`; erster Freigabekandidat `1.0.0`. Patch: reine Schreib-/Formatkorrektur ohne Bedeutungsänderung. Minor: andere Formulierung, Szene, Quelle, Claim, Musik, Untertitel usw. Major: wesentlich andere Kernfrage, Episode oder Format. Kein Versionsschritt erbt die vorherige Freigabe. Inputs und veröffentlichte Artefaktversionen werden nicht überschrieben.

## Evidenz

Die Originalquelle muss geöffnet und die relevante Fundstelle geprüft sein. Ein Suchtreffer oder Modellgedächtnis trägt keinen produktiven Claim. Unzugängliche Originale bleiben `nicht_geprueft`. Für klinische Aussagen soweit relevant Population, Design, Vergleich, Endpunkt, absolute/relative Wirkung, Unsicherheit, Interessenkonflikte und Gültigkeitsgrenzen dokumentieren. Gegenbelege, Korrekturen und Retraktionen aktiv suchen.

Claim-Status exakt `BESTÄTIGT`, `TEILWEISE`, `WIDERLEGT`, `UNBEWIESEN`; Einsatz exakt `ja`, `nur_mit_einschraenkung`, `nein`. Ein belegtes „Quelle X behauptet Y“ belegt nicht „Y stimmt“. Fehlender Wirksamkeitsbeleg beweist keine Unwirksamkeit. Eingeschränkte Claims benötigen die Einschränkung im späteren Wortlaut. BETA darf keine neuen Fakten einführen.

`A03.inhalt.quellenkatalog` wird automatisch aus tatsächlich referenzierten A02-Originalquellen materialisiert: `quelle_id`, `url`, `titel`, `zugriff`, `sha256`. BETA erhält diese Bibliografie in A03 und keinen A02-Vollkontext. Quellenangaben werden nicht aus Modellwissen ergänzt.

Bei gesundheitsrelevanten Aussagen zu Wirksamkeit, Schaden, Diagnostik, Therapie, Dosierung oder individueller Prognose ist echter medizinischer Review Pflicht, wenn ein Missverständnis Gesundheitsentscheidungen beeinflussen könnte. Rechtliche Risiken betreffen u. a. identifizierbare Personen/Unternehmen, schwere Vorwürfe, Medien-/Stimmrechte, Zitatrecht und Datenschutz. Reviewpakete bereiten die Fachprüfung vor; offene Rechtsfragen blockieren betroffene Claims, zentrale Fragen die Episode.

Vor G2 bindet `ma review-record ID --kind medical` bzw. `legal` standardmäßig `--stage claims` und ausschließlich A01–A03. Nach BETA gibt es bei relevanten Episoden zusätzlich `review/MEDICAL_PRODUCTION_REVIEW_PACKET.md` bzw. `LEGAL_PRODUCTION_REVIEW_PACKET.md`: `ma review-record ID --kind medical --stage production` bzw. `legal` bindet A01–A06 einschließlich konkretem Wortlaut, Titel, Thumbnail, Overlays und Szenen. G3 blockiert bis zu dieser tatsächlichen Prüfung. Claimreview wird nie stillschweigend um spätere Skriptdaten ergänzt.

## Standardshort und Produktionsregeln

Profil `MA-SHORT-58-v1.0`: 58,000 s, 1740 Frames, 1080×1920, 9:16, 30/1 fps konstant, ungefähr 100–130 gesprochene Wörter und genau eine CTA.

| Funktion | Zeitfenster |
|---|---|
| Hook | 0–3 s |
| Open Loop | 3–8 s |
| Payload | 8–41 s |
| Verdichtung | 41–48 s |
| CTA | 48–52 s |
| Ausklang | 52–54 s |
| Disclaimer | 54–58 s |

Harter Schnitt exakt 3,000 s. Keine Lücke/Überlappung. Disclaimer ausschließlich „Journalistischer Analyse-Content. Kein medizinischer Rat.“ auf Schwarz, ohne Voiceover/Musik/weitere Inhalte. Die Sprecherwortzahl enthält ihn nicht.

Video: SAR 1:1, progressiv, yuv420p, SDR/BT.709, H.264/AVC High Level 4.1, Ziel 10 Mbit/s/max. 16 Mbit/s, geschlossene GOP max. 60 Frames, 2 B-Frames, MP4/Fast Start. Audio: AAC-LC, 48 kHz Stereo, Ziel 384 kbit/s, Ziel −14 LUFS-I, zulässig −15 bis −13 LUFS-I, True Peak höchstens −1,5 dBTP. Die Angaben sind Sollwerte; InVideo-Prompts erzwingen keine tatsächlichen Exportparameter.

Untertitel: Deutsch, UTF-8 SRT zusätzlich zur eingebrannten Fassung, Montserrat Bold 52 px weiß, max. 2 Zeilen/max. 28 Zeichen je Zeile, reale Pixelbreite vorrangig, max. 18 Zeichen/s, Cues 0,80–4,00 s, Sync höchstens 100 ms. Semantische Umbrüche, keine sinnentstellend getrennten Negationen/Zahlen/Einheiten. Bereich x=90…930/y=192…1536; Unterkante y=1520; Quellenhinweise etwa y=1200…1320. Eine Formprüfung ersetzt keine tatsächliche Sicht-/Syncprüfung. Bei fehlender Schrift bzw. referenzierter Transkription ist die betreffende Messung nicht durchgeführt.

Stimme: ruhig, erwachsen, deutsch; keine imitierte reale Person, keine gespielte ärztliche Autorität. Musik ausschließlich instrumental, kein Gesang/dramatischer Sting. Während Sprache Ziel 18 dB unter Stimme, zulässig 15–21 dB. Fehlende zuverlässig getrennte Spuren: Standard-Fallback Musik entfernen. Kein erfundener Ducking-/Pegelwert.

## Freeze und QA

Vor G3 entsteht `freeze/r001/`: konkrete A01–A06-Versionen, zulässige Asset-/Rechteverweise, manifeste Dateiliste und `SHA256SUMS`. Nach Änderung entsteht `r002`, niemals eine Überschreibung. Human-Gate-Aufzeichnungen liegen außerhalb des Freeze. Hashprüfungen erkennen veränderte Freeze-Inhalte und blockieren.

Technische QA läuft erst mit einer echten Datei. ffprobe, vollständiger Decode, Loudnessmessung, Dauer/Framezahl/Auflösung/FPS/CFR/Codec/Pixelformat/Farbmetadaten und Audioformat/Samplerate/Kanalzahl erzeugen maschinenlesbare Reports unter `10_qa/`. Nicht messbare anwendbare Anforderungen bleiben offen. Ein realer technischer Fachreview kann solche Punkte durch konkrete Nachweise ergänzen: `ma review-record ID --kind technical --media preview` bzw. `--media final`. Für jeden `nicht_geprueft`-Punkt sind echte Prüfung, Qualifikation und ein eigener `technical_evidence`-Beleg nötig; dies ist kein Override für gemessene Fehler oder unabhängige offene K0/K1. Fehlt FFmpeg, verlangt die Pipeline Installation; sie meldet keine erfundenen Messwerte. Nach ergänzten Werkzeugen erzeugt `ma resume ID --recheck-media preview` bzw. `final` eine neue QA-Revision und invalidiert abhängige Freigaben. Keine automatische Neuencodierung. Eine Korrektur benötigt eine dokumentierte neue Datei und erneute QA.

K0: Inhalt/Sicherheit/Recht/Täuschung. K1: Produktion/Verständlichkeit/technische Abweichung. K2: nur Kosmetik. Findings enthalten Datei, Problem, Soll, Ist, Schwere, Rückweg und Offenstatus. QA repariert nicht stillschweigend. `freigabefaehig` erfordert 0 offene K0, 0 offene K1, keine fehlende anwendbare Pflichtprüfung; andere Ergebnisse `nacharbeit_erforderlich`/`pruefung_unvollstaendig`. Alle drei sind KI-Einschätzungen, keine menschlichen Gate-Entscheidungen.

Der unabhängige Preflight-QA-Bericht liegt als `QA.json` im Workeroutput und enthält mindestens `factuality`, `claim_mapping`, `rights`, `medical_legal`, `production`, `context_integrity`. Jeder Prüfpunkt hat Namen, Status und Begründung. Ein `nicht_anwendbar` braucht eine belegbare Begründung. Die Prüfung des Produktionsplans besteht keine zukünftige Prüfung eines echten Videos.

## Rückwege

```bash
ma invalidate ID --change source --reason "Originalquelle wurde ersetzt"
ma invalidate ID --change meaning --reason "Gesundheitsaussage wurde geändert"
ma invalidate ID --change export --reason "Neuer dokumentierter Finalexport"
```

Ersetze `ID` und wähle eine passende Änderung. Die verfügbaren Kategorien sind `source`, `claim`, `meaning`, `wording`, `title`, `thumbnail`, `cta`, `pronunciation`, `music`, `image`, `subtitle`, `cut`, `export`.

| Änderung | Nötiger Rückweg |
|---|---|
| Quelle, Claim, Zahl, Zitat, medizinische Einordnung, Vorwurf | ALPHA, G2 neu und abhängige Artefakte/Gates invalidieren |
| Wortlaut, Titel, Thumbnail, CTA | BETA; bei Bedeutung zusätzlich ALPHA/G2 |
| Aussprache, Musik, Bild, Untertitel, Schnitt | Produktion/Postproduktion und QA erneut; betroffene Folgegates neu |
| Neuer Export nach G4 | technische QA, aktuelle Datei-/SRT-Bindung, G5a neu; geänderte Inhalte auch Vorschau erneut |

Automatische Hashprüfung ergänzt diese explizite Einordnung; sie ersetzt keine semantische Prüfung. Unsichere Bedeutungsänderung sicher als `meaning` einstufen. Neue Uploadfassungen benötigen neue private Playback-Kontrolle und G5b. Keine abhängige Freigabe bleibt heimlich gültig.

## Analytics

Nur reale Exporte oder manuell verifizierte Daten übernehmen. Nach dokumentierter realer Veröffentlichung mit `ma analytics ID --file analytics.json` importieren. Die Datei enthält das strukturierte A12-Payload oder ein vollständiges Artefakt mit `inhalt`; nicht unterstützte Roh-CSV erst nachvollziehbar in diese Struktur überführen. Fehlende Kennzahlen: `wert: null` plus `begruendung`, niemals Null als erfundenes „0“. Zeitraum und Datenquelle dokumentieren. Beobachtungen beschreiben Messwerte; Hypothesen mögliche Erklärungen. Pro A12 genau ein überprüfbarer nächster Test mit vorher definierter Messgröße. Einzelne Videos ändern keine dauerhafte Kanalregel automatisch.
