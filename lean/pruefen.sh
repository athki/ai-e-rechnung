#!/bin/sh
# Baut das Modell, gibt die Entscheidungstabelle aus, prüft Aussagen und Axiome und ob die Antworten
# für den Abgleich mit rules.py (abgleich/kern.json) zum Modell passen. Gleich auf dem Host
# (`make lean`) und im Beweis-Container (`make beweise`).
set -eu
cd "$(dirname "$0")"
lake build
lake env lean Tabelle.lean
lake env lean Beispiele.lean
lake env lean Pruefung.lean

# Abgleich: die Datei wird hier nie geschrieben, nur verglichen; neu schreiben mit `make abgleich`.
neu="$(mktemp)"
trap 'rm -f "$neu"' EXIT
lake env lean --run Abgleich.lean > "$neu"
if ! cmp -s "$neu" abgleich/kern.json; then
  echo "abgleich/kern.json passt nicht zum Lean-Modell (erste Abweichungen):" >&2
  diff abgleich/kern.json "$neu" | head -20 >&2 || true
  echo "Ist die Änderung am Modell gewollt: make abgleich, dann make test." >&2
  exit 1
fi
echo "Abgleich: abgleich/kern.json passt zum Modell."
