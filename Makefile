CONTAINER_ENGINE ?= docker
SMOKE_SOURCE_ID := $(shell uv run python -c 'from bankai_benchmark.config import source_hash; print(source_hash()[:8])')
SMOKE_RESULTS := verification/v2-a6-r5-local/results-$(SMOKE_SOURCE_ID)
.PHONY: install test smoke smoke-matrix aggregate docker-build docker-smoke aws-plan aws-destroy
install:
	uv sync --locked

test:
	uv run pytest

smoke:
	uv run python scripts/verify_smoke.py

smoke-matrix:
	uv run bankai-benchmark smoke-matrix --experiment smoke-matrix

aggregate:
	uv run bankai-aggregate --results $(SMOKE_RESULTS) --output verification/v2-a6-r5-local/reports-$(SMOKE_SOURCE_ID) --provisional

docker-build:
	$(CONTAINER_ENGINE) build --platform linux/amd64 --build-arg VCS_REF=$$(git rev-parse HEAD) -t bankai-benchmark:dev .

docker-smoke: docker-build
	$(CONTAINER_ENGINE) run --rm --platform linux/amd64 --entrypoint /app/.venv/bin/python bankai-benchmark:dev scripts/verify_linux.py

aws-plan:
	uv run bankai-aws plan $(AWS_ARGS)

aws-destroy:
	uv run bankai-aws destroy $(AWS_ARGS)
