#!/usr/bin/env bash
# PreToolUse-Hook: primäre Sperre gegen Schreibzugriffe der AI auf abgeleitete oder geschützte Dateien.
# Zweite Sperre: permissions.deny in .claude/settings.json.
#
# Gesperrt:
#   **/rechnung.resolved.json, **/*.pdf, **/status.yaml   (abgeleitet bzw. vom Werkzeug gepflegt)
#   <gewerbe>/<stammdaten>/ich.yaml und **/stammdaten/ich.yaml
#   jede Datei in einem Rechnungsordner, dessen status.yaml "festgeschrieben" sagt
#
# Exit 2 = blockieren (stderr geht an Claude). Fehlt jq, wird jeder Schreibzugriff blockiert (fail closed).

set -uo pipefail

eingabe="$(cat)"

blockiere() {
    echo "schutz.sh: $1 – das darf nur das Werkzeug bzw. der Nutzer (siehe CLAUDE.md, 'Was die AI darf')." >&2
    exit 2
}

if ! command -v jq >/dev/null 2>&1; then
    blockiere "jq fehlt, Hook kann nicht prüfen"
fi

werkzeug="$(jq -r '.tool_name // empty' <<<"$eingabe")"

# Konfigurierten Pfad von ich.yaml ermitteln (Env gewinnt, sonst config.toml; einfache Zeilenauswertung).
toml_wert() {
    local datei="$1" schluessel="$2"
    [[ -f "$datei" ]] || return 0
    sed -nE "s/^[[:space:]]*${schluessel}[[:space:]]*=[[:space:]]*\"([^\"]*)\".*/\1/p" "$datei" | head -n1
}
cfg="${RECHNUNG_CONFIG:-${XDG_CONFIG_HOME:-$HOME/.config}/rechnung/config.toml}"
gewerbe="${RECHNUNG_GEWERBE:-$(toml_wert "$cfg" gewerbe)}"
stammdaten="${RECHNUNG_STAMMDATEN:-$(toml_wert "$cfg" stammdaten)}"
stammdaten="${stammdaten:-stammdaten}"
gewerbe="${gewerbe/#\~/$HOME}"
ich_yaml=""
[[ -n "$gewerbe" ]] && ich_yaml="${gewerbe%/}/${stammdaten%/}/ich.yaml"

# Prüft einen Pfad. Gibt einen Grund aus, wenn er gesperrt ist.
gesperrt() {
    local pfad="$1"
    case "$pfad" in
        */rechnung.resolved.json|rechnung.resolved.json) echo "rechnung.resolved.json ist abgeleitet"; return ;;
        *.pdf|*.PDF) echo "PDFs sind abgeleitet"; return ;;
        */status.yaml|status.yaml) echo "status.yaml pflegt nur 'rechnung festschreiben'"; return ;;
        */stammdaten/ich.yaml) echo "stammdaten/ich.yaml pflegt nur der Nutzer"; return ;;
    esac
    if [[ -n "$ich_yaml" && "$pfad" == "$ich_yaml" ]]; then
        echo "ich.yaml pflegt nur der Nutzer"; return
    fi
    # Festgeschriebene Rechnung: status.yaml im selben Ordner oder eine Ebene hoeher (belege/).
    local dir
    dir="$(dirname "$pfad")"
    for d in "$dir" "$(dirname "$dir")"; do
        if [[ -f "$d/status.yaml" ]] && grep -qE '^[[:space:]]*status:[[:space:]]*"?festgeschrieben' "$d/status.yaml"; then
            echo "Rechnung in $d ist festgeschrieben"; return
        fi
    done
}

case "$werkzeug" in
    Write|Edit|MultiEdit|NotebookEdit)
        pfad="$(jq -r '.tool_input.file_path // .tool_input.notebook_path // empty' <<<"$eingabe")"
        [[ -z "$pfad" ]] && exit 0
        grund="$(gesperrt "$pfad")"
        [[ -n "$grund" ]] && blockiere "$werkzeug auf $pfad: $grund"
        ;;
    Bash)
        befehl="$(jq -r '.tool_input.command // empty' <<<"$eingabe")"
        # Geblockt wird nur, wenn ein geschützter Name das ZIEL eines Schreibvorgangs ist.
        # Lesen bleibt erlaubt (cat, pdftotext, grep), und ein geschützter Name irgendwo im
        # Befehlstext – etwa in einem Regex oder in einem Dokument, das geschrieben wird –
        # ist für sich genommen kein Grund. Ein zu grober Hook wird abgeschaltet und schützt dann nichts.
        ziel='([^[:space:];|&"'"'"']*(rechnung\.resolved\.json|\.pdf|\.PDF|status\.yaml|ich\.yaml))'
        # 1) Umleitung auf ein geschütztes Ziel   2) tee   3) dateiverändernde Befehle
        # 4) sed/perl -i   5) Python-Schreibaufrufe (undurchsichtig, deshalb großzügig gesperrt)
        muster=(
            "(^|[^0-9a-zA-Z_])(>|>>)[[:space:]]*${ziel}"
            "\btee\b([[:space:]]+-[a-zA-Z]+)*[[:space:]]+${ziel}"
            "\b(cp|mv|rm|chmod|chown|touch|truncate|dd|ln|install|shred|mkdir)\b[^;|&]*${ziel}"
            "\b(sed|perl)\b[^;|&]*-i[^;|&]*${ziel}"
            "(write_text|write_bytes|shutil\.(copy|move)|os\.(remove|rename))[^;|&]*"
        )
        # Ein geschützter Name als Pfad in Anführungszeichen – nicht bloß als Wort in einem Text.
        zielpfad="[\"'][^\"']*/[^\"']*(rechnung\.resolved\.json|\.pdf|status\.yaml|ich\.yaml)"
        for m in "${muster[@]}"; do
            if grep -qE "$m" <<<"$befehl"; then
                # Python ist undurchsichtig: blocken, sobald ein geschützter PFAD auftaucht.
                # Ein Dateiname in einem Dokumenttext ist kein Grund.
                if [[ "$m" == "(write_text"* ]]; then
                    grep -qE "$zielpfad" <<<"$befehl" || continue
                fi
                # RECHNUNG_HOOK_DEBUG=1 zeigt, welche Regel angeschlagen hat und worauf.
                if [[ -n "${RECHNUNG_HOOK_DEBUG:-}" ]]; then
                    echo "schutz.sh: Regel /$m/ traf auf: $(grep -oE "$m" <<<"$befehl" | head -1)" >&2
                fi
                blockiere "Bash-Befehl schreibt auf eine geschützte Datei"
            fi
        done
        if [[ -n "$ich_yaml" ]] && grep -qE "(>|>>|\btee\b|\bcp\b|\bmv\b|\brm\b)[^;|&]*$(sed 's/[][\.*^$/]/\\&/g' <<<"$ich_yaml")" <<<"$befehl"; then
            blockiere "Bash-Befehl schreibt auf ich.yaml"
        fi
        ;;
esac
exit 0
