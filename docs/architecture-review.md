# Architekturreview V1

Der Lead-Review prüft die Produktionskette anhand der tatsächlichen Implementierung. Die V1 nutzt Python und lokale Dateien; Codex-Rollen arbeiten in separaten Kontexten, ohne eigenen API-Client. Produktionsdaten sind außerhalb Git. Sämtliche Human Gates sind ausdrücklich manuell und an konkrete Hashes gebunden.

Behobene Integrationsprobleme:

- BETA-Output wird vollständig vor der Registrierung geprüft; interne A04/A05-Abhängigkeiten berücksichtigen noch nicht geschriebene Outputwerte.
- Releasekandidaten werden vor menschlicher Prüfung/Freeze erzeugt. Historische Artefaktstatus bleiben unverändert; externe Gates bestimmen den wirksamen Freigabestatus.
- Die gesamte Gatekette bindet Vorgängerfreigaben, Konfiguration und tatsächliche Dateien. Neue Exporte, Quelländerungen, Reports und Reviews invalidieren betroffene Schritte.
- Red Team muss alle sechs benannten Pflichtchecks liefern. Deklarative Faktisch-Flags werden unabhängig semantisch überprüft.
- Vorschau-Reviews wählen tatsächlich die Vorschau. QA-Rechecks erzeugen neue Reports und können installierte Werkzeuge/Fonts berücksichtigen.
- G5a erlaubt ausschließlich privaten Upload. G5b bindet konkrete private Plattformfassung; tatsächliche Veröffentlichung wird erst durch einen Operatornachweis dokumentiert.
- Technische fehlende Messungen bleiben Blocker. Nachweise ersetzen keine gemessenen Fehlprüfungen und niemals eine medizinische/juristische Prüfung.
- Alle Worker-Outputs werden vor der ersten Quellenkopie geprüft. Bei I/O-Fehlern werden neue Teildateien und Stateänderungen zurückgerollt; ein fehlgeschlagener Import entzieht keine bestehende Freigabe.
- BETA erhält die benötigten Original-URLs über einen aus der gebundenen A02-Basis materialisierten A03-Quellenkatalog. Die Rolle erhält weiterhin ausschließlich A03 und Produktionsregeln.
- Ein medizinischer/juristischer Claimreview bindet A01–A03. Der konkrete Skript-/Szenenwortlaut einschließlich Publikationsfeldern benötigt bei Relevanz einen separaten Produktionsreview vor G3.
- Bekannte falsche Medienwerte bleiben auch bei fehlenden Begleitwerten fehlgeschlagen. Technische Nachweise ergänzen ausschließlich den einzeln bezeichneten fehlenden Prüfpunkt; unabhängige offene K0/K1 bleiben blockierend.
- Freier Import ist auf A01–A06 beschränkt. Operator-/Medien-/Plattform-/Analyticsartefakte entstehen ausschließlich über ihre zuständigen Abläufe. Statusanzeigen übernehmen keine veralteten Veröffentlichungsanweisungen.
- Schreibziele bleiben im externen Datenspeicher. Projektverzeichnisse, einzelne Dateien, Worker-Jobs, Freeze, Handoffs, Fachreviews und QA-Rohprotokolle dürfen nicht durch Symlinks umgeleitet werden. Der Pushcheck prüft alle erreichbaren Commit-Blobs einschließlich historischer Dateien.

Verbleibende bewusste Grenzen:

- Namen und tatsächliche menschliche Prüfungen werden als Operator-Attestierungen dokumentiert. Ohne zusätzliche Identitätsinfrastruktur kann lokale Software deren Wahrheit nicht beweisen. Produktionsagenten dürfen diese Befehle ausdrücklich nicht ausführen.
- Kontextisolation ist ein minimaler Arbeitsvertrag; ein nativer Session-Subagent wird nicht als zusätzliche OS-Sicherheitsgrenze ausgegeben. Der CLI-Modus verwendet die tatsächlich vorhandene Codex-Workspace-Sandbox.
- Deterministische Tests prüfen Orchestrierung. Recherche- und Semantikqualität benötigen reale native Worker und unabhängige QA. Nicht zugängliche Originale bleiben nicht_geprueft.
- Encoder-Zielparameter, getrennte Musikspuren, echte Sprachsynchronität und visuelle Plattformqualität sind nicht vollständig aus jeder einzelnen Datei ableitbar. Fehlende technische Nachweise und echte Sicht-/Hörchecks sind sichtbar blockierend.

Ein separater Red-Team-Agent prüft das vollständige Repository mit frischem Kontext. Relevante Findings werden vor dem finalen Commit behoben und mit Regressionstests überprüft.
