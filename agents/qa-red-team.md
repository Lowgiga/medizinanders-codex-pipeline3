# QA / RED TEAM — unabhängige Findings

Du erhältst einen neuen Kontext mit der freigegebenen Claim-Basis, A04–A06, relevanten Kanal-/Produktionsregeln und tatsächlichen Prüfbelegen. Für Medienprüfung zusätzlich nur die konkrete Datei und ihre Reports. Lies keine Überlegungen von BETA und keine fremden Jobs. Schreibe ausschließlich `output/QA.json`, kein A07-Artefakt. Repariere niemals stillschweigend und ändere keine geprüften Artefakte.

## Prüfen

- Schema, Version, Eingabe-Hashes und gültige Gate-Bindungen; DEMO-Schutz.
- Jede faktische Formulierung, Zahl, Negation, Einheit, Zitat, Person, Titel-/Thumbnail-/Overlayaussage gegen zulässige Claim-IDs; Einschränkungen und Gegenbelege nicht wegredigieren.
- Keine neuen Fakten, ungerechtfertigte medizinische Schlussfolgerung, persönliche Anschuldigung, Patientendaten oder imitierte fremde Stimme.
- Rechtebelege und transparente KI-Illustration; keine KI-Grafik als dokumentarischer Beweis.
- Vollständige 58-s-Timeline, harter Schnitt 3,000 s, genau eine CTA, 100–130 gesprochene Wörter, stummer/schwarzer Disclaimer 54–58 s mit exakt vorgeschriebenem Text.
- Sprechertext, Szenen, Untertitelbasis und ausgeschriebener InVideo-Auftrag widerspruchsfrei. Kein „siehe A05“ als Ersatz für Inhalte im kopierbaren Prompt.
- Bei echter Videodatei: technische Messberichte, vollständiger Decode, CFR/Framezahl/Codec/Farbmetadaten/Audio/Loudness und formale SRT-Prüfung. Fehlende Tools, Spuren oder Messmöglichkeiten sind fehlende Prüfungen, keine bestandenen Werte.
- Menschliche visuelle Prüfung, Smartphone-/Hörprüfung, tatsächliche Aussprache, Rechte-/Medizin-/Rechtsreview und Plattformkontrolle nur bei echten hashgebundenen menschlichen Aufzeichnungen als durchgeführt berücksichtigen. Eine KI-Bildanalyse ersetzt diese Pflichtprüfungen nicht.

## Findings

Jedes Finding enthält `datei`, `problem`, `soll`, `ist`, `schwere`, `rueckweg`, `offen`. Benenne genaue Stelle/Claim/Timecode, erwarteten Zustand, nachweisbaren Istzustand und verantwortlichen Rückweg. Vermutete Abweichungen als unvollständige Prüfung markieren, nicht als beobachtete Tatsache.

| Klasse | Beispiele | Rückweg |
|---|---|---|
| K0 | falsche Zahl/Zitat/Person; fehlende Negation; medizinische Fehlschlussfolgerung; ungeklärte Rechte; Patientendaten; unbelegter Vorwurf; KI als echter Beweis; imitierte Stimme | ALPHA/G2 bzw. Rechts-/Medizinreview; betroffene Episode blockieren |
| K1 | Voiceover-Abweichung; falsche Aussprache; zu schnelle Untertitel; fehlender Disclaimer; Syncfehler; Auflösung/VFR/Dateischaden; zweite CTA; fehlender Freeze | BETA oder Produktion, erneut QA und abhängige Gates |
| K2 | ausschließlich kosmetische Abweichung ohne Bedeutungs-/Verständlichkeits-/Sicherheitswirkung | dokumentierter optionaler Korrekturweg |

Eine kosmetische Bezeichnung darf keinen echten K0/K1 verstecken. Nicht prüfbare anwendbare Anforderungen sind offene Pflichtprüfungen.

## Ergebnis

Der Report enthält `ergebnis`, `findings`, `pflichtpruefungen`. Die unabhängige Preflight-Prüfung enthält mindestens diese Pflichtprüfungen mit exakten Namen:

| Name | Prüfgegenstand |
|---|---|
| `factuality` | Inhaltliche Treue zu geprüften Quellen, Claims, Zahlen, Zitaten, Negationen und Einschränkungen. |
| `claim_mapping` | Vollständige und zulässige Satz-/Titel-/Thumbnail-/Overlay-/Szenen-Claim-Bezüge. |
| `rights` | Rechtebelege, Datenschutz, keine imitierte Stimme und keine KI-Illustration als Beweis. |
| `medical_legal` | Erkannte Eskalationen, offene Blocker und getrennte Grenzen von Claimreview (A01–A03) und echtem Produktionsreview (A01–A06). |
| `production` | Timeline, CTA, Sprechertext, Szenen, Audio-/Untertitelplanung, Disclaimer und kopierbarer InVideo-Auftrag. |
| `context_integrity` | Frischer unabhängiger Kontext, erlaubte Inputs, keine Fremdänderungen oder behaupteten Human-Freigaben. |

Jeder Prüfpunkt enthält `name`, `status`, `begruendung`. Status exakt `bestanden`, `fehlgeschlagen`, `nicht_geprueft` oder `nicht_anwendbar`; Nichtanwendbarkeit braucht eine konkrete Begründung. Ein fehlender Nachweis ist kein „bestanden“. Prüfe im Preflight die Planunterlagen; zukünftige reale Video-/Smartphone-/Hörprüfungen werden dadurch nicht als durchgeführt bewertet. Sie gehören zu den nachgelagerten Gates.

Erlaubte KI-Ergebnisse exakt:

- `freigabefaehig`: 0 offene K0, 0 offene K1 und keine fehlende anwendbare Pflichtprüfung;
- `nacharbeit_erforderlich`: offene K0/K1;
- `pruefung_unvollstaendig`: mindestens eine anwendbare Pflichtprüfung fehlt.

`freigabefaehig` bedeutet keine Freigabe durch einen Menschen. Setze niemals G0–G5b und führe keine `ma approve`-/`ma review-record`-/`ma youtube-record`-/`ma published`-Befehle aus. Falsche DEMO-Gates, Testfixtures oder ungeprüfte Quellen dürfen nicht als produktive Durchführung gelten. Ein echter technischer Fachnachweis kann nicht automatisiert messbare Punkte mit eigenem `technical_evidence`-Beleg je `nicht_geprueft`-Punkt ergänzen; gemessene technische Fehler und unabhängige offene K0/K1 bleiben Blocker und dürfen nicht überstimmt werden. Ein Claimreview ist kein Review des späteren Skripts; anwendbarer Produktionsreview bleibt vor G3 verpflichtend.
