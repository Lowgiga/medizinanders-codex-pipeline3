# Tatsächlich geprüfte Fähigkeiten

Am 2026-10-03 in der bereitgestellten Unix-Umgebung:

- Native `spawn_agent`, `send_message`, `followup_task` mit `fork_turns=none` vorhanden und beim Aufbau tatsächlich verwendet.
- Codex CLI 0.159.0-alpha.3: `codex exec --help` geprüft. Der Adapter prüft vor Nutzung erneut die benötigten realen Flags; keine permanenten named agents vorausgesetzt.
- Python 3.12, Git, jsonschema, PyYAML und Pillow verfügbar.
- FFmpeg/ffprobe 7.1.5 verfügbar und mit echten synthetischen Videodateien getestet.
- Aktuelle Codex-Umgebung bietet reale Web-/Recherchewerkzeuge. Der spätere Betreiber bestätigt die verfügbaren Such- und Originalöffnungswerkzeuge in seiner Umgebung bei G0; das Repository behauptet keine portable Webfähigkeit jedes CLI-Workers.
- InVideo wird nicht automatisch bedient. YouTube-Upload/Veröffentlichung erfolgen nicht über eine Pipeline-API.
- GitHub-Lesezugriff tatsächlich bestätigt. Repository-Erstellung wurde über GraphQL und REST versucht; der Server verweigerte die Operation mit HTTP403 `Resource not accessible by integration`. Der lokale Aufbau wurde fortgesetzt. `scripts/publish-private.sh` bereitet den Schritt in einer tatsächlich berechtigten GitHub-Umgebung vor.

Der Betreiber hat anschließend ausdrücklich das bestehende öffentliche Ziel `Lowgiga/medizinanders-codex-pipeline3` vorgegeben. Dieses Ziel ersetzt für die konkrete Lieferung den anfänglichen Privat-Default. Der Inhalts- und Historiencheck bleibt vor jedem Push verpflichtend.

Keine Produktionsfreigabe, Kostenannahme, Fachprüfung oder Veröffentlichung wurde während dieser Implementierung vorgenommen.
