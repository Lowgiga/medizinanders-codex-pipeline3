# Synthetischer Dry Run

```bash
ma demo
```

Die Demo erzeugt ein neues, ausdrücklich mit `beispiel: true` markiertes
Projekt im lokalen Datenspeicher außerhalb dieses Git-Repositories. Den
genauen Pfad und den Bericht `DEMO_REPORT.json` zeigt der Befehl an.
Alle Rollenoutputs sind deterministische Testfixtures. Es wird keine
Webrecherche und keine echte Fachprüfung behauptet.

Der Durchlauf erstellt A01, hält bei G1, simuliert ausschließlich die
DEMO-Freigabe, importiert eine tatsächlich gelesene synthetische lokale
Originalkopie in A02 und die dazugehörige Claim-Prüfung A03. Nach dem
DEMO-G2 entstehen A04–A06, Preflight, synthetischer unabhängiger QA-Report,
Freeze `r001` und der vollständige InVideo-Handoff. G3 hält vor InVideo.
Die DEMO-G3-Simulation dokumentiert keine Kostenentscheidung.

Wenn FFmpeg vorhanden ist, erstellt die Demo ein echtes kleines Video mit
sichtbarem `DEMO`-Text, 160 × 284 Pixeln und zwei Sekunden Laufzeit. Das
absichtlich abweichende Profil muss technische Findings auslösen. Das ist
kein InVideo-Render. Das Video wird vollständig decodiert und gemessen.
Die Demo erstellt außerdem ein Final-QA-Testfixture und das YouTube-Paket
als isolierte Handoff-Prüfung. G4, G5a und G5b bleiben ohne Freigabe.
Es erfolgt kein Upload und keine Veröffentlichung.

Fehlt FFmpeg, lautet der betreffende Schritt `MANUAL_STEP`; es werden keine
Messwerte erfunden. Installiere FFmpeg und wiederhole `ma demo` für die
Medienprüfung. Ein Demo-Projekt kann niemals echte Produktionsfreigaben
erhalten. `--demo-simulate` funktioniert ausschließlich mit Demo-Projekten
und setzt keine reale G0-Betriebsfreigabe.

Automatisierte Negativtests prüfen zusätzlich manipulierte Hashes,
veraltete Inputs, Gatebindung, Invalidierung, offene K0/K1, fehlende
Fachreviews, unzulässige Claims, zweite CTA, Timelinefehler und Datenablage
im Repository. Tests und Demo benötigen keine API-Schlüssel.

```bash
python3 -m unittest discover -s tests -v
```
