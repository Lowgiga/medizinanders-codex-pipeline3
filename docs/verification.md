# V1-Verifikation — 2026-10-03

Die vollständige automatisierte Suite besteht: **178 Tests, OK**. Der Lead- und der separate Testagent führten sie nach den letzten Codeänderungen erneut aus. Ein unabhängiger Red-Team-Agent prüfte die Architektur und reproduzierte die relevanten Negativfälle; sein Abschluss steht in [red-team-review.md](red-team-review.md).

Tatsächlich ausgeführte Befehle in der bereitgestellten Umgebung:

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/ma doctor
.venv/bin/ma demo --data-dir /workspace/medizinanders-verified-demo
.venv/bin/ma demo --data-dir /workspace/medizinanders-release-demo
git diff --check
.venv/bin/python scripts/check_repository.py --staged
```

`scripts/bootstrap.sh` wurde außerdem in einer isolierten Repositorykopie ausgeführt; die dort installierten `ma doctor` und `ma demo` funktionierten. Python 3.12 sowie FFmpeg/ffprobe 7.1.5 waren tatsächlich vorhanden. Die CLI prüft verfügbare Werkzeuge und Codex-Flags vor Verwendung erneut.

## Synthetischer Durchlauf

Ergebnis: `DEMO_COMPLETE`, ausdrücklich `beispiel: true`. A01–A10 wurden erstellt; GAMMA, RESEARCH, ALPHA, BETA und unabhängige QA verwendeten deterministische, eindeutig synthetische Testdoubles. Die Halte an G1, G2 und G3 wurden nachgewiesen; ausschließlich die DEMO-Gates G0–G3 wurden simuliert.

Freeze `r001` und seine Hashes wurden erneut erfolgreich geprüft. InVideo- und YouTube-Handoff enthielten jeweils neun Dateien. Eine reale, lokal mit FFmpeg erzeugte Testdatei mit sichtbarem DEMO-Text wurde vollständig decodiert und gemessen. Ihr absichtlich falsches Format (160×284, zwei Sekunden) erzeugte technische Fehler und offene Prüfungen. Für Vorschau und Finalfixture wurden jeweils 25 bestandene, acht fehlgeschlagene und fünf nicht vollständig prüfbare technische Checks dokumentiert. Das ist ein nachgewiesener Negativfall, keine Behauptung eines freigabefähigen Produktionsvideos.

G4, G5a und G5b blieben **offen**. `real_upload: false`, `real_publication: false`. Kein InVideo-Render, keine reale Webrecherche, Fachprüfung, Smartphone-/Hörprüfung oder Veröffentlichung wurde durch den DEMO-Durchlauf behauptet. Erfolgspfade späterer Gates werden ausschließlich durch separat markierte DEMO-Testdoubles in den Unit-Tests geprüft.

## Integritätsgrenzen

Regressionen prüfen unter anderem manipulierte Artefakt-, Quellen-, Freeze-, Report- und Gatehashes, veraltete Kontexte, fehlende Fachreviews, tatsächlichen Produktionsreviewumfang, unzulässige Claims, CTA-/Timeline-/Untertitelfehler, irreversible Überschreibungen und technische Messlücken. Bekannte falsche Medienwerte bleiben Fehler. Ein ergänzender technischer Review kann unabhängige offene K0/K1 nicht überstimmen.

Quellen-IDs werden vor Dateimutierungen validiert; gescheiterte Worker-Writes rollen den State zurück. Umgeleitete Projektordner, einzelne Datei-Symlinks, Worker-Jobs, Reviews, Freeze, Handoffs und QA-Protokolle werden blockiert. Separate Git-Testrepositories weisen nach, dass `--history` sensible Commit-Inhalte auch nach einer lediglich gestagten Löschung erkennt. Die Securityfixtures enthalten ausschließlich synthetische Daten; keine echten Credentials oder Produktionsquellen.

Dieser Bericht erteilt keine Betriebs-, Episoden-, medizinische oder juristische Freigabe. G0 und sämtliche produktiven Gates müssen später von den tatsächlich verantwortlichen Menschen bestätigt werden.
