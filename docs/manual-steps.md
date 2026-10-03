# Die wenigen manuellen Schritte

Die Pipeline meldet jeweils `WHY` und konkrete `Next`-Schritte. Benutze immer die im Status angezeigten absoluten Projektpfade. `ID` steht hier für die ausgegebene Projekt-ID.

## Einmalig: Betriebsfreigabe G0

1. `ma setup` ausführen.
2. Verantwortliche Person, konkrete Umgebung, Datenschutz, Speicherort und tatsächliche Tools eintragen. Rollen und Kanalregeln lesen. InVideo-Konto, Exportmöglichkeiten und Kosten bestätigen. Unbestätigte Fähigkeiten bleiben offen.
3. Bei Bedarf FFmpeg/ffprobe und die verwendete Untertitelschrift installieren. Verfügbarkeit in der tatsächlichen Umgebung prüfen.
4. Erst nach realer Prüfung selbst `ma approve G0` im Terminal ausführen.

Sichere `STANDARDVORSCHLÄGE`: Projekte lokal außerhalb Git; native Codex-Session; nur öffentliche Gesundheitsinformationen; Musik entfernen, solange getrennte Pegel nicht zuverlässig prüfbar sind. Diese Vorschläge sind keine bereits getroffenen Entscheidungen.

## Auftrag und Inhalt

1. `ma new` ausführen und Themenidee eingeben.
2. `ma run ID` in Codex bearbeiten lassen. GAMMA liefert A01; der Mensch prüft und führt `ma approve G1 --project ID` aus.
3. `ma run ID` fortsetzen. RESEARCH/ALPHA arbeiten bis A03. Nicht zugängliche Originalquellen selbst beschaffen oder Claim streichen/neu recherchieren; eine Quelle wird durch Bereitstellung allein noch nicht geprüft.
4. Wenn nötig Fachpersonen die vorbereiteten Claimreview-Pakete geben. Reale Entscheidungen über `ma review-record ID --kind medical` bzw. `legal` dokumentieren. Diese Standardstufe `claims` bindet ausschließlich A01–A03 und besteht keine spätere Skriptprüfung.
5. Claims, Gegenbelege und Risiken prüfen; selbst `ma approve G2 --project ID` bestätigen.

## InVideo nach G3

Nach BETA bei relevanten Episoden zusätzlich `review/MEDICAL_PRODUCTION_REVIEW_PACKET.md` bzw. `LEGAL_PRODUCTION_REVIEW_PACKET.md` durch eine echte Fachperson prüfen lassen: Wortlaut, Titel, Thumbnail, Overlays und Szenen. Danach `ma review-record ID --kind medical --stage production` bzw. `legal` selbst dokumentieren. Diese getrennte Prüfung bindet A01–A06; ohne sie blockiert G3. Nach Preflight, unabhängiger QA und Freeze prüft der Mensch das Paket und bestätigt `ma approve G3 --project ID`. Dann stoppt die Pipeline am InVideo-Handoff.

`handoff/invideo/` enthält:

- `INVIDEO_PROMPT.txt`: eigenständig kopierbarer vollständiger Auftrag;
- `SCENE_PLAN.md`: Szenen und Zeiten;
- `VOICEOVER.txt`: exakter Sprechertext;
- `SUBTITLE_BASE.txt`: exakte Textgrundlage;
- `ASSET_MANIFEST.yaml`: Motive, Assetbedarf und Rechteverweise;
- `RIGHTS_CHECKLIST.md`: tatsächliche Rechte prüfen;
- `EXPECTED_OUTPUT.md`: Sollprofil und Abweichungsregeln;
- `OPERATOR_STEPS.md`: konkrete Bedien-/Rückgabeschritte.

1. Öffne `OPERATOR_STEPS.md` und `INVIDEO_PROMPT.txt`.
2. Öffne das echte InVideo-Konto, prüfe Verfügbarkeit und Kosten, erzeuge genau einen Entwurf aus dem Prompt.
3. Prüfe, ob InVideo die Vorgaben tatsächlich umsetzt. Ein Prompt garantiert weder technische Exportparameter noch korrekte Rechte, Aussprache, Untertitel oder Schnittzeiten.
4. Exportiere die tatsächliche Vorschau als `08_produktion/inbox/preview.mp4` im Projekt.
5. `ma resume ID` ausführen. Die Pipeline prüft echte Datei und Reports.
6. Echte Vorschau auf Smartphone ansehen und mit Kopfhörern sowie Smartphone-Lautsprecher prüfen. Exakter Wortlaut/Negationen/Zahlen/Einheiten, Aussprache, Untertitel, Sync, Quellen, Rechte, Disclaimer und Verständlichkeit anhand der Checkliste kontrollieren.
7. Nach realer Prüfung `ma review-record ID --kind preview --media preview`, dann `ma approve G4 --project ID` selbst ausführen. Findings vorher beheben und neue Exporte erneut prüfen.

## Finaldatei und technische Korrektur

Die echte Finaldatei nach `09_postproduktion/inbox/final.mp4` und die gegen den realen Ton synchronisierte UTF-8 SRT nach `09_postproduktion/inbox/final.srt` zurückgeben. `ma resume ID` erstellt Finalreports. `handoff/invideo/SUBTITLE_DRAFT.srt` ist ein Zeitplanentwurf, kein Nachweis tatsächlicher Sprachsynchronität. Nicht passende Parameter werden nicht automatisch korrigiert.

Eine technische Korrektur ist ein neuer, bewusst dokumentierter Export: Änderung mit `ma invalidate ID --change export --reason "Konkreter Korrekturgrund"` bzw. passender Inhalts-/Produktionskategorie melden, Ursprung/Parameter/Grund aufzeichnen, korrigierte Datei zurückgeben und QA erneut laufen lassen. Die CLI ist kein Ersatz für eine Video-/Audioeditorentscheidung. Keine Originaldatei heimlich überschreiben und alte Freigabe beibehalten.

Bei technisch `nicht_geprueft` gekennzeichneten Punkten eine geeignete reale Fachperson beauftragen. Nach echter Prüfung `ma review-record ID --kind technical --media final` bzw. für die Vorschau `--media preview` mit Qualifikation und einem eigenen tatsächlichen Einzelbeleg je offenem Punkt dokumentieren; die CLI speichert diese Belege unter `technical_evidence`. Dies ersetzt keine nicht erfolgte Prüfung und erlaubt keinen Override gemessener Fehler oder unabhängiger offener K0/K1. Nach ergänzten Messwerkzeugen mit `ma resume ID --recheck-media final` bzw. `preview` neue Reports erzeugen und die invalidierten Folgeprüfungen/Freigaben erneut durchführen.

Die konkrete Finalfassung vollständig sichtbar/hörbar prüfen, dann `ma review-record ID --kind final`. G5a bindet exakt ihren SHA-256 und die SRT, keine beliebige künftige Version.

## YouTube: privat, Playback, Veröffentlichung

`handoff/youtube/` enthält finalen Titel, Beschreibung, Hashtags/Quellen, SRT, Thumbnail-Anweisung, Hash, Uploadcheckliste und offene Felder für KI-Kennzeichnung, Zielgruppe und Werbung. Der Mensch trifft die tatsächlichen Plattformentscheidungen; Codex erfindet keine YouTube-Fähigkeit.

1. Uploadpaket und Finalhash kontrollieren. KI-Kennzeichnung, Zielgruppe und Werbung real entscheiden.
2. `ma approve G5a --project ID` selbst bestätigen.
3. Genau die hashgebundene Finaldatei im echten YouTube Studio ausschließlich **privat** hochladen, SRT/Metadaten übernehmen und Verarbeitung abwarten.
4. Selbst `ma youtube-record ID` im Terminal ausführen. Tatsächliche Video-ID/URL, ausschließlich private Sichtbarkeit, hashidentische Uploaddatei und reale KI-/Zielgruppen-/Werbeentscheidungen bestätigen. Dieser Befehl dokumentiert den erfolgten privaten Upload in A11; er lädt nichts hoch.
5. `ma resume ID` erzeugt die private Playback-Checkliste. Die tatsächlich verarbeitete Plattformfassung aufrufen; Bild/Ton/Untertitel/Metadaten/Kennzeichnungen/Thumbnail prüfen.
6. `ma review-record ID --kind playback`, danach `ma approve G5b --project ID` selbst ausführen.
7. Erst jetzt im echten YouTube Studio auf öffentlich stellen.
8. Erst nach tatsächlicher öffentlicher Veröffentlichung selbst `ma published ID` ausführen. Der Befehl dokumentiert Sichtbarkeit und Zeitpunkt in A11; er veröffentlicht nichts. Kein Gate-Befehl führt einen Upload oder eine Veröffentlichung aus.

## Später: Analytics

Reale Analytics exportieren, Datenquelle und Zeitraum dokumentieren und die A12-Inhaltsstruktur als `analytics.json` ausfüllen. Nach dokumentierter Veröffentlichung `ma analytics ID --file analytics.json` ausführen. Der Import akzeptiert ein A12-Payload oder ein vollständiges Artefakt mit `inhalt`, kein unverarbeitetes Roh-CSV. Fehlende Werte bleiben `null` mit Begründung. Codex trennt Messbeobachtungen und Hypothesen und formuliert genau einen überprüfbaren nächsten Test. Kanalregeln nicht allein wegen eines Videos dauerhaft ändern.

`ma import` ist nur für A01–A06 vorgesehen. A07–A12 werden ausschließlich über die passenden Pipeline-/Operatorbefehle erzeugt. Für einen kurzen Überblick `ma status ID` verwenden, für Details `ma status ID --json`, für aktuelle nächste Schritte `ma resume ID`. Alte Veröffentlichungsanweisungen niemals nach einer Änderung weiterverwenden.
