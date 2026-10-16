# ks-sw-spec: checks for the kssw specification.
#
#   make check                          validate + links
#   make conformance BASE_URL=...       the suite against any server (it writes: never production)
#   make reference                      the suite against the PHP reference implementation (docker)

-include make.local

.PHONY: help check validate links conformance reference clean

PYTEST   ?= uv run --no-project --with pytest pytest -q
VALIDATE ?= uv run --no-project --with openapi-spec-validator openapi-spec-validator
SCRATCH  := .scratch
# The reference implementation. Public-ready URL: it works only once the
# repository is public; override with a local path or a private remote in
# make.local (gitignored), or point IMPL_DIR at an existing checkout.
IMPL_URL ?= https://github.com/kimari-s/ks-sw-api
IMPL_REF ?= main
IMPL_DIR ?= $(SCRATCH)/impl

help:
	@echo "Targets:"
	@echo "  check        validate + links"
	@echo "  validate     validate openapi/*.yaml (openapi-spec-validator)"
	@echo "  links        relative links and anchors in *.md"
	@echo "  conformance  BASE_URL=<API base> [ADMIN_TOKEN=...] [PYTEST_ARGS=...]: run conformance/"
	@echo "  reference    clone IMPL_URL at IMPL_REF (or use IMPL_DIR) and run conformance/ against it in docker"

check: validate links

validate:
	$(VALIDATE) openapi/kssw.openapi.yaml openapi/kssw-admin.openapi.yaml

links:
	python3 scripts/check-links.py

conformance:
	@test -n "$(BASE_URL)" || { echo "set BASE_URL=http://... (the API base)" >&2; exit 2; }
	BASE_URL=$(BASE_URL) $(PYTEST) conformance $(PYTEST_ARGS)

reference:
	@if [ "$(IMPL_DIR)" = "$(SCRATCH)/impl" ]; then \
		rm -rf $(SCRATCH)/impl && mkdir -p $(SCRATCH) && \
		git clone -q $(IMPL_URL) $(SCRATCH)/impl && git -C $(SCRATCH)/impl checkout -q $(IMPL_REF); \
	fi
	scripts/run-reference.sh $(IMPL_DIR) $(PYTEST_ARGS)

clean:
	rm -rf $(SCRATCH)/impl
