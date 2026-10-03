# Human Gates

Nur ein realer Mensch kann G0–G5b bestehen. `freigabefaehig` ist eine KI-Einschätzung, keine Freigabe. Produktionsagenten führen weder Approval-/Reviewrecord- noch `youtube-record`-/`published`-Befehle aus. Die interaktive CLI zeigt die konkrete Bindung und verlangt Namen und einen ausdrücklichen Bestätigungstext. Es gibt keinen pauschalen `--yes`-Pfad für produktive Freigaben; `--name` ist nur für simulierte DEMO-Freigaben zulässig.

```bash
ma approve G0
ma approve G2 --project MA-YYYYMMDD-NNN
```

Der Mensch wählt den passenden Gate und die echte Projekt-ID. Der Befehl prüft Voraussetzungen und Blocker vor der Bestätigung. Er dokumentiert Name, Zeitpunkt, Artefaktversionen, SHA-256 und relevante Konfiguration. Eine spätere Version erbt die Freigabe nie. Technische Änderungen an Regeln/Code oder gebundenen Dateien erfordern erneute Prüfung und gegebenenfalls G0 bzw. Folgegates.

## Was der Mensch bestätigt

| Gate | Gebundener Gegenstand | Konkrete Verantwortung |
|---|---|---|
| G0 | Betreiberkonfiguration, Umgebung, Regeln/Rollen, tatsächliche Tools | Reale Verantwortung, Datenschutz, Speicherort, Rechte/Backups, native Worker/Webrecherche, echte InVideo-Fähigkeiten und Kostenprozess geprüft. |
| G1 | A01 | Kernfrage, Zielgruppe, Scope, Ausschlüsse, Rechercheauftrag sowie Zeit-/Kostenrahmen angenommen. Ohne G1 keine Recherche. |
| G2 | A01–A03 und nötige Claimreviews (`claims`) | Einsetzbare Claims, Fundstellen, Gegenbelege, Einschränkungen und Risiken geprüft; echte medizinische/juristische Pflichtreviews der Claim-Basis liegen vor. |
| G3 | A01–A07, aktueller Freeze, Preflight, unabhängige QA und nötige Produktionsreviews (`production`) | Genau dieses Skript/Szenen-/Assetpaket einschließlich Wortlaut/Titel/Thumbnail/Overlays ist fachlich geprüft und darf produziert werden; keine offenen K0/K1/Pflichtprüfungen des Preflight. Kosten noch vor echter InVideo-Bestätigung prüfen. |
| G4 | Echte Vorschau A08, technische und menschliche Prüfbelege | Tatsächliche Vorschau gesehen/gehört, Claimwortlaut/Aussprache/Untertitel/Schnitt/Disclaimer/Verständlichkeit/Rechte geprüft. |
| G5a | A09/A10, konkrete Finaldatei + SHA-256 und SRT | Genau diese geprüfte Finalfassung darf ausschließlich privat auf YouTube hochgeladen werden. |
| G5b | A11 mit echter privater Video-ID/URL und Playback-Aufzeichnung | Tatsächliche verarbeitete private Plattformfassung kontrolliert; diese Fassung darf der Mensch veröffentlichen. |

G3 ist keine Behauptung über bereits gerenderte Medien. G4 ist keine Veröffentlichungsfreigabe. G5a erlaubt maximal einen privaten Upload. G5b veröffentlicht nichts automatisch. Eine geänderte Finaldatei oder geänderte private Plattformfassung braucht neue aktuelle Prüfungen und Gate-Bindungen.

## Medizinischer und juristischer Review

Die Claimreview-Pakete stehen unter `review/MEDICAL_REVIEW_PACKET.md` und `review/LEGAL_REVIEW_PACKET.md`. Sie enthalten Kernfrage, relevante Claims, tatsächliche Originalquellen/Fundstellen, Studienparameter, die Formulierungen des Claim-Registers, Unsicherheiten und konkrete Fragen. Sie binden ausschließlich A01–A03 und enthalten keinen als bereits geprüft dargestellten späteren BETA-Wortlaut.

Medizinischer Review ist Pflicht bei Bewertung von Wirksamkeit, Schaden, Diagnostik, Therapie, Dosierung oder individueller Krankheitsprognose, wenn Missverständnisse Gesundheitsentscheidungen beeinflussen könnten. Nur eine echte Fachperson darf ihn durchführen. Rechtsreview ist Pflicht bei relevanten Fragen zu identifizierbaren Personen/Unternehmen, schweren Vorwürfen, Bild-/Musik-/Stimmrechten, Zitatrecht oder Datenschutz. Eine offene Rechtsfrage sperrt den Claim, bei zentralem Claim die Episode.

Nach tatsächlicher Prüfung dokumentiert ein realer Mensch interaktiv:

```bash
ma review-record ID --kind medical
ma review-record ID --kind legal
```

Dabei ist `--stage claims` der Standard und G2 der nächste Gate. Nach BETA benötigt eine relevante Episode zusätzlich einen getrennten tatsächlichen Produktionsreview auf A01–A06. Die vorbereiteten Pakete heißen `review/MEDICAL_PRODUCTION_REVIEW_PACKET.md` und `review/LEGAL_PRODUCTION_REVIEW_PACKET.md` und enthalten den konkreten Wortlaut, Titel, Thumbnail, Overlays und Szenen.

```bash
ma review-record ID --kind medical --stage production
ma review-record ID --kind legal --stage production
```

Nur die anwendbaren Arten durchführen. Ein Claimreview wird nie automatisch um diese Skript-/Produktionsdateien erweitert. G3 bleibt bis zum anwendbaren echten Produktionsreview blockiert. Die Entscheidung muss den konkreten geprüften Gegenstand, Revieweridentität, Rolle/Qualifikation, Zeitpunkt, Ergebnis, Bedingungen und offene Punkte nachvollziehbar benennen. Eine nachträgliche Bedeutungsänderung benötigt erneut Fachreview. Ein Packet ohne reale Prüfung besteht den Blocker nicht. Ein ablehnender/bedingter Review wird nicht als vorbehaltlose Freigabe ausgelegt.

## Menschliche Medien-/Plattformprüfung

```bash
ma review-record ID --kind preview --media preview
ma review-record ID --kind final
ma review-record ID --kind playback
```

Die ersten beiden beziehen sich auf echte lokale Dateien und ihre Hashes. Playback bezieht sich auf die tatsächlich verarbeitete private YouTube-Fassung. Die CLI/Checklisten bereiten die Pflichtpunkte vor. Smartphone-/Hörprüfung, tatsächliche Bildlesbarkeit, eingebrannte Untertitel, Synchronität, Aussprache und Rechte werden nicht aus einem technischen Report als durchgeführt abgeleitet.

Für nicht automatisiert geprüfte technische Pflichtpunkte gibt es `ma review-record ID --kind technical --media preview` bzw. `--media final`. Eine fachlich geeignete reale Person muss jeden betreffenden Punkt tatsächlich prüfen. Die CLI verlangt für jeden `nicht_geprueft`-Punkt einen eigenen konkreten Beleg und speichert ihn unter `technical_evidence`. Diese Prüfung bindet Datei und Reports und ergänzt exakt die fehlenden technischen Nachweise. Gemessene Fehler und unabhängige offene K0/K1 können niemals damit überstimmt werden; sie erfordern eine nachvollziehbare Korrektur und erneute QA.

## DEMO und Gültigkeit

Ein DEMO-Projekt darf simulierte Bestätigungen ausschließlich mit `--demo-simulate` und konkreter Projekt-ID im Testworkflow erhalten. Für die Demo-G0-Simulation ist daher ebenfalls `--project DEMO_PROJEKT_ID` erforderlich; reale G0-Freigabe erfolgt ohne Projektargument über `ma approve G0`. Jede Aufzeichnung bleibt als DEMO erkennbar. DEMO kann keinen produktiven G0 und keine produktive Episodenfreigabe setzen. Produktionsfreigaben blockieren `beispiel: true`, Fixtures, offene Blocker und fehlende Pflichtprüfungen.

Die Gate-Datei liegt außerhalb `freeze/rNNN/`; Änderungen an ihrer gebundenen Artefakt-/Medien-/Regelbasis machen sie ungültig. Ein archivierter Name/Zeitpunkt ist keine fortdauernde Freigabe für neue Inhalte. Die Operatorbestätigung ist eine dokumentierte Selbstauskunft; sie ist keine digitale Identitätsprüfung und ersetzt keine reale Fachprüfung.
