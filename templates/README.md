# Beispielvorlagen A01–A12

Diese UTF-8-JSON-Dateien sind zugleich gültiges YAML. Jede Vorlage ist ausdrücklich `beispiel: true`, `status: Entwurf`, Version `0.1.0` und Projekt `MA-20261003-001`. Sie erfüllen ihr Schema und enthalten keine Produktions- oder Gate-Freigabe.

Beim Anlegen eines Projekts muss der Core Projekt-ID, Datum und verantwortliche Person aus den tatsächlichen Eingaben übernehmen. `beispiel` ist eine Projektentscheidung; einen Demodatensatz nicht durch Umbenennen als reale Arbeit ausgeben. Erst nach Bearbeitung und Review werden neue Artefaktversionen mit tatsächlichen Eingabereferenzen und Hashes erstellt.

Texte in eckigen Klammern, `Q-PLACEHOLDER`, `C-PLACEHOLDER` und `AS-PLACEHOLDER` sind erkennbare Platzhalter. Die Beispielquelle ist nicht geöffnet, der medizinische Beispielclaim ist unbewiesen und nicht einsetzbar, sein Risiko ist offen und blockierend, die Assetrechte sind offen und alle QA-Berichte sind unvollständig. Quellen, Fundstellen, Rechte, Prüferidentitäten und Messwerte müssen aus tatsächlicher Arbeit stammen.

Preview-, Final- und SRT-Pfade bezeichnen die vorgesehenen Eingangsorte. Leere Hashes bestätigen, dass die Vorlagen keine existierenden Dateien nachweisen. Die private Sichtbarkeit in A11 ist die gewünschte Ausgangseinstellung; ihre tatsächliche Plattformkontrolle steht aus. Analyticswerte sind `null` mit Begründung. A12 enthält genau ein Objekt für einen nächsten Test.

Die Payloadformen und verpflichtenden Felder stehen direkt in den Vorlagen. Alle zwölf Dateien lassen sich ohne externe Schemaauflösung mit `jsonschema.Draft202012Validator` und `FormatChecker` validieren.
