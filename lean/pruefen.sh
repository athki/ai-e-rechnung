#!/bin/sh
# Baut das Modell, gibt die Entscheidungstabelle aus und prüft Aussagen und Axiome. Gleich auf dem
# Host (`make lean`) und im Beweis-Container (`make beweise`).
set -eu
cd "$(dirname "$0")"
lake build
lake env lean Tabelle.lean
lake env lean Pruefung.lean
