# Schattencontainer: das Werkzeug muss jederzeit hier laufen. Im Alltag nicht in Gebrauch.
#   make schatten
#   docker run --rm -v <gewerbe>:/gewerbe rechnung <kommando>
# Bewusste Abstriche: läuft als root, kein User-Mapping, keine Secrets, kein Netzwerk-Setup.

# Schlankes TeX Live (scheme-minimal + tlmgr), Multi-Arch amd64/arm64.
FROM texlive/texlive:latest-minimal

COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /uvx /usr/local/bin/

RUN apt-get update \
 && apt-get install -y --no-install-recommends poppler-utils fontconfig ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# TeX-Pakete: genau die Liste, gegen die auch `rechnung doctor` prüft.
COPY docs/tex-pakete.txt /tmp/tex-pakete.txt
# `tlmgr update --self` zuerst: ist der CTAN-Mirror neuer als das Basisimage, verweigert ein
# veraltetes tlmgr jede Installation. `tlmgr path add` verlinkt die Programme neuer Pakete
# (lualatex, latexmk …) nach /usr/local/bin.
RUN tlmgr update --self \
 && tlmgr install $(sed -e 's/#.*//' /tmp/tex-pakete.txt | awk 'NF {print $1}') \
 && tlmgr path add

# Eigene Font-Dateien der Vorlage (XCharter und Fira Sans kommen als TeX-Pakete)
COPY vorlage/fonts/ /usr/local/share/fonts/rechnung/
RUN fc-cache -f

# Python: Version und Abhängigkeiten aus .python-version und uv.lock
ENV UV_PYTHON_INSTALL_DIR=/opt/uv-python \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /app
COPY pyproject.toml uv.lock .python-version README.md LICENSE ./
RUN uv sync --frozen --no-dev --no-install-project
COPY . .
RUN uv sync --frozen --no-dev

ENV PATH=/opt/venv/bin:$PATH \
    RECHNUNG_GEWERBE=/gewerbe
# Kennzeichnung, damit `make schatten` alte, unbenannte Images dieses Projekts aufräumen kann – nur diese.
# Der Beweis-Container erbt sie.
LABEL ai-e-rechnung=schatten
VOLUME /gewerbe
ENTRYPOINT ["rechnung"]
CMD ["--help"]
