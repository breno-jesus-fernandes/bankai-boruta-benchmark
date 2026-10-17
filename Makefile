CONTAINER_ENGINE ?= docker
.PHONY: install test smoke smoke-matrix aggregate docker-build docker-smoke aws-plan aws-destroy
install:
	uv sync --locked

test:
	uv run pytest

smoke:
	uv run bankai-benchmark smoke --experiment smoke

smoke-matrix:
	uv run bankai-benchmark smoke-matrix --experiment smoke-matrix

aggregate:
	uv run bankai-aggregate --results results --output reports --provisional

docker-build:
	$(CONTAINER_ENGINE) build --platform linux/amd64 --build-arg VCS_REF=$$(git rev-parse HEAD) -t bankai-benchmark:dev .

docker-smoke: docker-build
	$(CONTAINER_ENGINE) run --rm --platform linux/amd64 --entrypoint /app/.venv/bin/python bankai-benchmark:dev scripts/verify_linux.py

aws-plan:
	uv run bankai-aws plan $(AWS_ARGS)

aws-destroy:
	uv run bankai-aws destroy $(AWS_ARGS)
