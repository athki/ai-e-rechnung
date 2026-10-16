IMAGE := rechnung
# Leerer Gewerbe-Ordner für den Schattencontainer; nie der echte.
SCHATTEN_GEWERBE := $(CURDIR)/build/schatten-gewerbe
SCHATTEN_MCP := $(CURDIR)/build/schatten-mcp
DOCKER_RUN := docker run --rm -v "$(SCHATTEN_GEWERBE)":/gewerbe $(IMAGE)

.PHONY: test doctor hooks beispiel beispiel-neu lean abgleich beweise beweise-image schatten schatten-image

test: hooks
	uv run --extra mcp pytest -q

doctor:
	uv run rechnung doctor

# Commit-Wächter einschalten: prüft jeden Commit gegen die Sperrliste neben der Config
# (sperrliste.txt oder RECHNUNG_SPERRLISTE). Ohne Sperrliste still. `test` und `schatten`
# schalten ihn mit ein; `rechnung doctor` wird rot, wenn eine Sperrliste da ist und er aus ist.
hooks:
	git config core.hooksPath .githooks

# Beispielrechnung der Vorlage (feste Werte, Unternehmen im Drittland, nicht steuerbar) – die Designrunde in Sekunden.
beispiel:
	cd vorlage && latexmk -pdf -interaction=nonstopmode -halt-on-error -no-shell-escape beispiel.tex

# Vollständiger Neubau inklusive Beleg-PDF der Anlage; nach Änderungen an style/ nötig,
# weil latexmk Stiländerungen nicht immer bemerkt.
beispiel-neu:
	cd vorlage && rm -f beispiel.aux beispiel.fls beispiel.fdb_latexmk beispiel.log beispiel.out
	cd vorlage && latexmk -pdf -interaction=nonstopmode -halt-on-error -no-shell-escape -outdir=attachments attachments/sample-receipt.tex
	$(MAKE) beispiel

# Beweise unter lean/ bauen und ihre Axiome prüfen, auf dem Host (braucht elan; Version aus
# lean/lean-toolchain). Schnell beim Arbeiten an den Beweisen.
lean:
	lean/pruefen.sh

# Antworten des Lean-Modells für den Abgleich mit rules.py neu schreiben (lean/abgleich/kern.json,
# eingecheckt). Nur bewusst aufrufen, wenn das Modell sich gewollt geändert hat; `make lean` und
# `make beweise` prüfen die Datei, `make test` hält rules.py dagegen.
abgleich:
	cd lean && lake build && lake env lean --run Abgleich.lean > abgleich/kern.json

schatten-image:
	docker build -t $(IMAGE) .

# Beweis-Container: Rechnungs-Image plus Lean. Jeder Lauf baut die Beweise neu und prüft die Axiome;
# ein offener Beweis (`sorry`) oder `native_decide` macht ihn rot.
beweise-image: schatten-image
	docker build -f Dockerfile.beweise -t $(IMAGE)-beweise .

beweise: beweise-image
	docker run --rm $(IMAGE)-beweise

# Beide Container: das Rechnungs-Image mit init gegen einen leeren Gewerbe-Ordner, doctor,
# den Demo-Rechnungen, `rechnung pruefen` und `rechnung begruendung` auf jeder einzelnen; dann der
# Beweis-Container.
# Pflicht: keine Änderung ist fertig, solange das hier rot ist.
schatten: hooks schatten-image
	rm -rf "$(SCHATTEN_GEWERBE)" && mkdir -p "$(SCHATTEN_GEWERBE)"
	$(DOCKER_RUN) init
	$(DOCKER_RUN) doctor
	$(DOCKER_RUN) demo --ziel /gewerbe/demo-output
	@for rechnung in inland-muster-gmbh reverse-charge-exemple-sarl nicht-steuerbar-sample-ltd \
		nicht-steuerbar-privat-ch inland-privat-de kleinunternehmer-muster-gmbh; do \
		$(DOCKER_RUN) pruefen /gewerbe/demo-output/$$rechnung || exit 1; \
	done
	$(DOCKER_RUN) pruefen --pro-forma /gewerbe/demo-output/nicht-steuerbar-sample-ltd
	@for rechnung in inland-muster-gmbh reverse-charge-exemple-sarl nicht-steuerbar-sample-ltd \
		nicht-steuerbar-sample-ltd/pro-forma/2 nicht-steuerbar-privat-ch inland-privat-de \
		kleinunternehmer-muster-gmbh; do \
		$(DOCKER_RUN) begruendung /gewerbe/demo-output/$$rechnung > /dev/null || exit 1; \
	done
	@echo "begruendung: alle Demo-Rechnungen grün"
	@# Geschwärzte Sicht (RECHNUNG_GESCHWAERZT): dieselben Kommandos, ohne Namen und Beträge.
	docker run --rm -e RECHNUNG_GESCHWAERZT=1 -v "$(SCHATTEN_GEWERBE)":/gewerbe $(IMAGE) pruefen /gewerbe/demo-output/reverse-charge-exemple-sarl
	docker run --rm -e RECHNUNG_GESCHWAERZT=1 -v "$(SCHATTEN_GEWERBE)":/gewerbe $(IMAGE) begruendung /gewerbe/demo-output/reverse-charge-exemple-sarl > /dev/null
	@# MCP-Server im Container, gestartet wie von Claude Desktop (docker run -i … mcp), gegen einen
	@# Ordner mit den Beispiel-Stammdaten: neu → schreiben → resolve über stdio.
	rm -rf "$(SCHATTEN_MCP)" && mkdir -p "$(SCHATTEN_MCP)"
	docker run --rm -v "$(SCHATTEN_MCP)":/gewerbe $(IMAGE) init --beispiel > /dev/null
	uv run --extra mcp python tests/mcp_stdio.py docker run -i --rm -v "$(SCHATTEN_MCP)":/gewerbe $(IMAGE) mcp
	@# Demo-Betrieb (RECHNUNG_DEMO) in einem leeren Ordner: Beispieldaten aus dem Image, Werkzeug kunden.
	rm -rf "$(SCHATTEN_MCP)-demo" && mkdir -p "$(SCHATTEN_MCP)-demo"
	uv run --extra mcp python tests/mcp_stdio.py docker run -i --rm -e RECHNUNG_DEMO=1 -v "$(SCHATTEN_MCP)-demo":/gewerbe $(IMAGE) mcp
	$(MAKE) beweise
	@# Alte, unbenannte Images dieses Projekts wegräumen (Kennzeichnung im Dockerfile); fremde bleiben, der Build-Cache auch.
	docker image prune -f --filter label=ai-e-rechnung=schatten
