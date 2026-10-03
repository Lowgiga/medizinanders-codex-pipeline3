# Schemas A01–A12

Jede `Axx.schema.json` ist ein eigenständiges JSON Schema 2020-12. Gemeinsam genutzte Definitionen stehen in der jeweiligen Datei unter `$defs`; sämtliche `$ref` sind lokale JSON-Pointer. Es gibt keine Netzwerkanfrage, keinen relativen Dateiverweis und keine erforderliche `referencing.Registry`.

```python
import json
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker

schema = json.loads(Path("schemas/A03.schema.json").read_text(encoding="utf-8"))
artifact = json.loads(Path("templates/A03.json").read_text(encoding="utf-8"))
Draft202012Validator.check_schema(schema)
Draft202012Validator(schema, format_checker=FormatChecker()).validate(artifact)
```

`FormatChecker` muss aktiviert sein, damit ungültige Kalenderdaten, Zeitpunkte und URLs zusätzlich zu ihrer Form erkannt werden. `datum` akzeptiert ein ISO-Datum oder einen RFC-3339-Zeitpunkt mit Zeitzone. Unbekannte Metadaten und unbekannte fachliche Felder sind ausgeschlossen. Der originale maschinelle `A10.inhalt.technischer_report` darf zusätzliche Messdaten enthalten.

V1 verwendet das Profil `MA-SHORT-58-v1.0`: A01 enthält 58 Sekunden und 9:16; A04 benennt das Profil als String und enthält genau die sieben verbindlichen Phasen. Das Satzregister verwendet unter anderem `hook`, `open_loop`, `payload`, `verdichtung`, `cta` und `ausklang`. Die Disclaimer-Szene hat leeren Sprechertext, einen schwarzen Hintergrund und keine Musik oder Effekte. Sprecherwortzahl, Szenenabdeckung, Phasenzuordnung und der harte Schnitt bei 3,000 s werden zusätzlich im Core geprüft.

Alle Artefakte haben dieselben verpflichtenden Metadaten. Ein gesperrtes Artefakt verlangt einen nicht leeren Sperrgrund; ein ungesperrtes Artefakt verlangt einen leeren Sperrgrund. Eingabereferenzen verlangen reale SHA-256-Hashes. Noch nicht existierende Medien- und Freeze-Dateien dürfen im Entwurf einen leeren Hash haben. Ein freigabefähiges A07 beziehungsweise A10 verlangt den tatsächlichen Freeze- beziehungsweise Dateihash.

Originalquellen enthalten neun verpflichtende klinische Parameter als Text. Nicht anwendbare Parameter brauchen eine konkrete Begründung; fehlende Daten dürfen nicht geschätzt werden. Eine als `geprüft` markierte Quelle verlangt einen tatsächlichen Öffnungszeitpunkt, Fundstellen, einen bekannten Quellentyp und eine URL oder einen lokalen Pfad. Ob diese Angaben wahr sind und den Claim tragen, entscheidet die Recherche und der fachliche Review.

Unbewiesene und widerlegte Claims dürfen nur `einsatz: nein` haben. Teilweise bestätigte Claims benötigen Belege und Einschränkungen; sie erlauben `nur_mit_einschraenkung` oder `nein`. Faktische Sätze, Overlays und Publikationsfelder benötigen Claim-IDs. `einschraenkung` ist bei diesen Feldern optional; ob die Einschränkung verständlich wahrnehmbar im Sprechertext vorkommt, prüft der Crosscheck und die menschliche QA.

QA-Findings und Risiken verwenden ausschließlich `K0`, `K1` und `K2`. Ein Bericht mit `ergebnis: freigabefaehig` darf keine offenen K0/K1-Findings oder fehlgeschlagene/ungeprüfte Pflichtprüfungen enthalten. Offene kosmetische K2-Findings sind erlaubt. `nicht_anwendbar` braucht eine Begründung. Der Core muss zusätzlich die vollständige, kontextabhängige Liste der Pflichtprüfungen verlangen; eine beliebige bestandene Prüfung genügt nicht für ein Gate.

Die Schemas prüfen Struktur und begrenzte feldübergreifende Regeln. Quellen-/Claim-/Asset-IDs, Eingabehashes, Zeitintervalle, Sprechertext/Wortzahl, Rechtebelege, reale Medienmessungen, vollständige Reviews, Freeze-Inhalte, Plattformkontrolle und Freigabeidentität müssen die Validatoren und Gates separat prüfen. `status` ist ein historischer Dateistatus. Ein Artefaktstatus und ein QA-Ergebnis erzeugen keine externe Freigabe und vererben keine Freigabe an spätere Versionen.
