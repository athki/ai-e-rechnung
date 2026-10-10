#!/bin/sh
# Baut die Beweise und prüft ihre Axiome. Gleich auf dem Host (`make lean`) und im
# Beweis-Container (`make beweise`).
set -eu
cd "$(dirname "$0")"
lake build
lake env lean Pruefung.lean
