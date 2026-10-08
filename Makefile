IMAGE := rechnung
# Leerer Gewerbe-Ordner für den Schattencontainer; nie der echte.
SCHATTEN_GEWERBE := $(CURDIR)/build/schatten-gewerbe
DOCKER_RUN := docker run --rm -v "$(SCHATTEN_GEWERBE)":/gewerbe $(IMAGE)

.PHONY: test doctor hooks beispiel beispiel-neu schatten schatten-image

test: hooks
	uv run pytest -q

doctor:
	uv run rechnung doctor

# Commit-Wächter einschalten: prüft jeden Commit gegen die Sperrliste neben der Config
# (sperrliste.txt oder RECHNUNG_SPERRLISTE). Ohne Sperrliste still. `test` und `schatten`
# schalten ihn mit ein; `rechnung doctor` wird rot, wenn eine Sperrliste da ist und er aus ist.
hooks:
	git config core.hooksPath .githooks

# Beispielrechnung der Vorlage (feste Werte, Steuerfall C) – die Designrunde in Sekunden.
beispiel:
	cd vorlage && latexmk -pdf -interaction=nonstopmode -halt-on-error -no-shell-escape beispiel.tex

# Vollständiger Neubau inklusive Beleg-PDF der Anlage; nach Änderungen an style/ nötig,
# weil latexmk Stiländerungen nicht immer bemerkt.
beispiel-neu:
	cd vorlage && rm -f beispiel.aux beispiel.fls beispiel.fdb_latexmk beispiel.log beispiel.out
	cd vorlage && latexmk -pdf -interaction=nonstopmode -halt-on-error -no-shell-escape -outdir=attachments attachments/sample-receipt.tex
	$(MAKE) beispiel

schatten-image:
	docker build -t $(IMAGE) .

# Image bauen, dann im Container: init gegen einen leeren Gewerbe-Ordner, doctor,
# die vier Demo-Rechnungen und `rechnung pruefen` auf jeder einzelnen.
# Pflicht: keine Änderung ist fertig, solange das hier rot ist.
schatten: hooks schatten-image
	rm -rf "$(SCHATTEN_GEWERBE)" && mkdir -p "$(SCHATTEN_GEWERBE)"
	$(DOCKER_RUN) init
	$(DOCKER_RUN) doctor
	$(DOCKER_RUN) demo --ziel /gewerbe/demo-output
	@for fall in a-muster-gmbh b-exemple-sarl c-sample-ltd d-privat-ch; do \
		$(DOCKER_RUN) pruefen /gewerbe/demo-output/fall-$$fall || exit 1; \
	done
