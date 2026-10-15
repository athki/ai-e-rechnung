#!/usr/bin/env bash
# PreToolUse-Hook: primäre Sperre gegen Schreibzugriffe der AI auf abgeleitete oder geschützte Dateien.
# Zweite Sperre: permissions.deny in .claude/settings.json.
#
# Gesperrt:
#   **/rechnung.resolved.json, **/*.pdf, **/status.yaml   (abgeleitet bzw. vom Werkzeug gepflegt)
#   **/pro-forma/**   (gesendete Pro-forma-Revisionen, eingefroren)
#   **/rechnung.privat.yaml   (Preise und Referenz, schreibt nur `rechnung preise`)
#   <gewerbe>/<stammdaten>/ich.yaml und **/stammdaten/ich.yaml, ebenso preise.yaml (Preisliste)
#   jede Datei in einem Rechnungsordner, dessen status.yaml "festgeschrieben" sagt
#
# Lesesperre, nur unter dem Schalter RECHNUNG_GESCHWAERZT (siehe src/rechnung/sicht.py), nur in den
# Gewerbe-Wurzeln – der aus RECHNUNG_GEWERBE und der aus config.toml, damit der echte Ordner auch
# dann geschützt ist, wenn die Env auf einen Test-Ordner zeigt:
#   <wurzel>/<stammdaten>/** (mit der Preisliste), <wurzel>/<kunden>/**, und darunter überall
#   *.resolved.json, rechnung.privat.yaml, PDFs, status.yaml, pro-forma/**, belege/**
# Read/Grep/Glob über den Pfad; Bash, wenn der Befehl eine Wurzel nennt (außer einem bloßen
# `rechnung …`-Aufruf und Pfaden in Rechnungsordnern) oder in einer Wurzel läuft. Dazu sperrt er
# Befehle, die RECHNUNG_GESCHWAERZT, RECHNUNG_GEWERBE oder RECHNUNG_CONFIG überschreiben oder löschen.
# Ehrlich löchrig: Variablen, Globs und Skripte, die Pfade selbst zusammensetzen, sieht er nicht.
# Repo, stammdaten.example/ und demo-output/ bleiben frei.
#
# Läuft auch unter /bin/bash 3.2 (macOS): leere Arrays nur über ${a[@]+"${a[@]}"}.
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
preise_yaml=""
if [[ -n "$gewerbe" ]]; then
    ich_yaml="${gewerbe%/}/${stammdaten%/}/ich.yaml"
    preise_yaml="${gewerbe%/}/${stammdaten%/}/preise.yaml"
fi

# Prüft einen Pfad. Gibt einen Grund aus, wenn er gesperrt ist.
gesperrt() {
    local pfad="$1"
    case "$pfad" in
        */rechnung.resolved.json|rechnung.resolved.json) echo "rechnung.resolved.json ist abgeleitet"; return ;;
        *.pdf|*.PDF) echo "PDFs sind abgeleitet"; return ;;
        */status.yaml|status.yaml) echo "status.yaml pflegt nur 'rechnung festschreiben'"; return ;;
        */pro-forma/*|pro-forma/*) echo "gesendete Pro-forma-Revisionen sind eingefroren"; return ;;
        */rechnung.privat.yaml|rechnung.privat.yaml) echo "rechnung.privat.yaml schreibt nur 'rechnung preise'"; return ;;
        */stammdaten/ich.yaml) echo "stammdaten/ich.yaml pflegt nur der Nutzer"; return ;;
        */stammdaten/preise.yaml) echo "die Preisliste pflegt nur der Nutzer"; return ;;
    esac
    if [[ -n "$ich_yaml" && "$pfad" == "$ich_yaml" ]]; then
        echo "ich.yaml pflegt nur der Nutzer"; return
    fi
    if [[ -n "$preise_yaml" && "$pfad" == "$preise_yaml" ]]; then
        echo "die Preisliste pflegt nur der Nutzer"; return
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

# ---------------------------------------------------------------- Lesesperre (nur unter dem Schalter)

blockiere_lesen() {
    echo "schutz.sh: $1 – unter RECHNUNG_GESCHWAERZT liest die AI keine Kunden-, Aussteller- oder" \
         "abgeleiteten Daten. Die geschwärzte Sicht liefert \`rechnung resolve|bauen|pruefen|begruendung\`." >&2
    exit 2
}

geschwaerzt_aktiv() {
    local w="${RECHNUNG_GESCHWAERZT:-}"
    w="${w//[[:space:]]/}"
    [[ -n "$w" && "$w" != "0" ]]   # fail closed wie sicht.aktiv()
}

cwd="$(jq -r '.cwd // empty' <<<"$eingabe")"
cwd="${cwd:-$PWD}"

# Absoluter Pfad ohne ~, ohne /./ und ohne Schrägstrich am Ende; .. bleibt stehen (wird gesperrt).
normal() {
    local p="${1/#\~/$HOME}"
    [[ "$p" == /* ]] || p="${cwd%/}/$p"
    while [[ "$p" == *"/./"* ]]; do p="${p//\/.\//\/}"; done
    p="${p%/.}"
    [[ "$p" == "/" ]] || p="${p%/}"
    printf '%s' "$p"
}

# Physischer Pfad (Symlinks aufgelöst), soweit der Ordner existiert.
physisch() {
    local p="$1" d
    if [[ -d "$p" ]]; then
        (cd "$p" 2>/dev/null && pwd -P) && return
    fi
    d="$(dirname "$p")"
    if [[ -d "$d" ]]; then
        printf '%s/%s\n' "$(cd "$d" 2>/dev/null && pwd -P)" "$(basename "$p")"
        return
    fi
    printf '%s\n' "$p"
}

wurzeln=()
if geschwaerzt_aktiv; then
    for w in "${RECHNUNG_GEWERBE:-}" "$(toml_wert "$cfg" gewerbe)"; do
        [[ -z "$w" ]] && continue
        w="$(normal "$w")"
        wurzeln+=("$w")
        p="$(physisch "$w")"
        [[ "$p" != "$w" ]] && wurzeln+=("$p")
    done
fi
kunden="${RECHNUNG_KUNDEN:-$(toml_wert "$cfg" kunden)}"
kunden="${kunden:-${stammdaten%/}/kunden}"
ausgang="${RECHNUNG_AUSGANG:-$(toml_wert "$cfg" ausgang)}"
ausgang="${ausgang:-rechnung-ausgang}"

# Liegt der Pfad in einer Wurzel und ist er dort geschützt? Gibt den Grund aus.
lese_gesperrt() {
    local roh="$1" w rel p
    for p in "$(normal "$roh")" "$(physisch "$(normal "$roh")")"; do
        for w in ${wurzeln[@]+"${wurzeln[@]}"}; do
            [[ "$p" == "$w" || "$p" == "$w"/* ]] || continue
            rel="${p#"$w"}"
            rel="${rel#/}"
            case "/$rel/" in
                */../*) echo "Pfad mit .. in der Gewerbe-Wurzel"; return ;;
                "/${stammdaten%/}/"*|"/${kunden%/}/"*) echo "Stammdaten (Aussteller, Kunden)"; return ;;
                */pro-forma/*) echo "gesendete Pro forma"; return ;;
                */belege/*) echo "Belege"; return ;;
            esac
            case "$rel" in
                *rechnung.resolved.json) echo "rechnung.resolved.json"; return ;;
                *rechnung.privat.yaml) echo "rechnung.privat.yaml (Preise)"; return ;;
                *.pdf|*.PDF) echo "PDF"; return ;;
                *status.yaml) echo "status.yaml"; return ;;
            esac
        done
    done
}

# Durchsucht ein Werkzeug (Grep, Glob) einen Ordner, der eine Wurzel enthält oder in einer liegt?
suche_gesperrt() {
    local p w
    p="$(normal "$1")"
    for w in ${wurzeln[@]+"${wurzeln[@]}"}; do
        if [[ "$w" == "$p" || "$w" == "$p"/* ]]; then echo "Suche über die Gewerbe-Wurzel"; return; fi
        if [[ "$p" == "$w"/* && ! -f "$p" ]]; then echo "Suche in der Gewerbe-Wurzel"; return; fi
    done
    lese_gesperrt "$1"
}

# Bash unter dem Schalter: Schalter und Wurzel nicht überschreiben, Geschütztes nicht nennen.
bash_lesen() {
    local befehl="$1" w form rest treffer
    local tilde='~' home_var='$HOME'
    # Was hinter einer Nennung der Wurzel steht, wenn sie die Wurzel selbst meint (Ende, Trenner, /).
    local trenner='^[/[:space:]";|&)]'
    local schreibweise="'"
    local geschuetzt='resolved\.json|privat\.yaml|\.pdf|\.PDF|status\.yaml|pro-forma|belege'
    local suche='\b(find|rg|tree|du)\b|\bgrep\b[^;|&]*[[:space:]]-[a-zA-Z]*[rR]|\bls\b[^;|&]*[[:space:]]-[a-zA-Z]*R'

    # Den Schalter einschalten (=1) ist harmlos; gesperrt ist ausschalten (leer, 0) und jede neue Wurzel.
    if grep -qE '(^|[^A-Za-z0-9_])(RECHNUNG_GEWERBE|RECHNUNG_CONFIG)=|(^|[^A-Za-z0-9_])RECHNUNG_GESCHWAERZT=["'"'"']?0?["'"'"']?([[:space:];|&)]|$)|\bunset\b[^;|&]*RECHNUNG_|\benv\b[^;|&]*[[:space:]](-i|-u|--unset|--ignore-environment)\b' <<<"$befehl"; then
        blockiere_lesen "Bash-Befehl überschreibt RECHNUNG_GESCHWAERZT, RECHNUNG_GEWERBE oder RECHNUNG_CONFIG"
    fi
    # Ein bloßer Aufruf des Werkzeugs: Es schwärzt seine Ausgabe selbst.
    if grep -qE '^[[:space:]]*(uv[[:space:]]+run[[:space:]]+(--[a-z-]+[[:space:]]+)*)?rechnung([[:space:]][^;|&`$()<>]*)?$' <<<"$befehl"; then
        return
    fi
    for w in ${wurzeln[@]+"${wurzeln[@]}"}; do
        if [[ "$cwd" == "$w" || "$cwd" == "$w"/* ]]; then
            if grep -qE "$geschuetzt|(^|[^A-Za-z0-9_.-])(${stammdaten%/}|${kunden%/})(/|[[:space:]]|\$)|$suche" <<<"$befehl"; then
                blockiere_lesen "Bash-Befehl in der Gewerbe-Wurzel"
            fi
        fi
        for form in "$w" "${w/#$HOME/$tilde}" "${w/#$HOME/$home_var}" '$RECHNUNG_GEWERBE' '${RECHNUNG_GEWERBE}'; do
            [[ "$befehl" == *"$form"* ]] || continue
            if [[ "$form" == *RECHNUNG_GEWERBE* && "$w" != "$(normal "${RECHNUNG_GEWERBE:-/nirgends}")" ]]; then
                continue
            fi
            # Jede Nennung der Wurzel muss in einen Rechnungsordner führen, und nichts Geschütztes dabei.
            rest="$befehl"
            treffer=""
            while [[ "$rest" == *"$form"* ]]; do
                rest="${rest#*"$form"}"
                if [[ "$rest" == "/${ausgang%/}/"* ]]; then
                    treffer=1
                elif [[ -z "$rest" || "$rest" =~ $trenner || "${rest:0:1}" == "$schreibweise" ]]; then
                    blockiere_lesen "Bash-Befehl nennt die Gewerbe-Wurzel außerhalb von ${ausgang%/}/"
                fi   # sonst ein anderer Ordner, der nur gleich beginnt (Gewerbe und Gewerbe-Test)
            done
            [[ -n "$treffer" ]] || continue
            if grep -qE "$geschuetzt|/\.\./|$suche" <<<"$befehl"; then
                blockiere_lesen "Bash-Befehl liest Geschütztes in der Gewerbe-Wurzel"
            fi
        done
    done
}

case "$werkzeug" in
    Read)
        [[ ${#wurzeln[@]} -eq 0 ]] && exit 0
        pfad="$(jq -r '.tool_input.file_path // empty' <<<"$eingabe")"
        [[ -z "$pfad" ]] && exit 0
        grund="$(lese_gesperrt "$pfad")"
        [[ -n "$grund" ]] && blockiere_lesen "Read auf $grund"
        exit 0
        ;;
    Grep|Glob)
        [[ ${#wurzeln[@]} -eq 0 ]] && exit 0
        pfad="$(jq -r '.tool_input.path // empty' <<<"$eingabe")"
        muster="$(jq -r '.tool_input.pattern // empty' <<<"$eingabe")"
        grund="$(suche_gesperrt "${pfad:-$cwd}")"
        # Ein absolutes Glob-Muster nennt seinen Ordner selbst: der Teil vor dem ersten Platzhalter.
        if [[ -z "$grund" && "$werkzeug" == Glob && ( "$muster" == /* || "$muster" == "~"* ) ]]; then
            vorne="${muster%%[*?[{]*}"
            grund="$(suche_gesperrt "${vorne%/*}")"
        fi
        [[ -n "$grund" ]] && blockiere_lesen "$werkzeug: $grund"
        exit 0
        ;;
esac

# ---------------------------------------------------------------- Schreibsperre

case "$werkzeug" in
    Write|Edit|MultiEdit|NotebookEdit)
        pfad="$(jq -r '.tool_input.file_path // .tool_input.notebook_path // empty' <<<"$eingabe")"
        [[ -z "$pfad" ]] && exit 0
        grund="$(gesperrt "$pfad")"
        [[ -n "$grund" ]] && blockiere "$werkzeug auf $pfad: $grund"
        ;;
    Bash)
        befehl="$(jq -r '.tool_input.command // empty' <<<"$eingabe")"
        if geschwaerzt_aktiv; then
            bash_lesen "$befehl"
        fi
        # Schreiben: Geblockt wird nur, wenn ein geschützter Name das ZIEL eines Schreibvorgangs ist.
        # Lesen bleibt hier erlaubt (cat, pdftotext, grep), und ein geschützter Name irgendwo im
        # Befehlstext – etwa in einem Regex oder in einem Dokument, das geschrieben wird –
        # ist für sich genommen kein Grund. Ein zu grober Hook wird abgeschaltet und schützt dann nichts.
        ziel='([^[:space:];|&"'"'"']*(rechnung\.resolved\.json|rechnung\.privat\.yaml|stammdaten/preise\.yaml|\.pdf|\.PDF|status\.yaml|ich\.yaml|pro-forma/[^[:space:];|&"'"'"']*))'
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
        zielpfad="[\"'][^\"']*/[^\"']*(rechnung\.resolved\.json|rechnung\.privat\.yaml|stammdaten/preise\.yaml|\.pdf|status\.yaml|ich\.yaml|pro-forma/)"
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
        for datei in "$ich_yaml" "$preise_yaml"; do
            if [[ -n "$datei" ]] && grep -qE "(>|>>|\btee\b|\bcp\b|\bmv\b|\brm\b)[^;|&]*$(sed 's/[][\.*^$/]/\\&/g' <<<"$datei")" <<<"$befehl"; then
                blockiere "Bash-Befehl schreibt auf $(basename "$datei")"
            fi
        done
        ;;
esac
exit 0
