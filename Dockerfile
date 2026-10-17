FROM --platform=linux/amd64 python:3.11-slim-bookworm@sha256:0a310eeecf4e1f5a0743f9a6520c90c88d089c903ca5fd283f501e3a805f5f89 AS build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl git libgomp1 ca-certificates && rm -rf /var/lib/apt/lists/*
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal --default-toolchain 1.97.1
ENV PATH="/root/.cargo/bin:$PATH"
RUN pip install --no-cache-dir uv==0.5.20
WORKDIR /app
COPY . .
RUN sha256sum -c artifacts/SHA256SUMS && uv sync --locked --no-dev --no-editable
FROM --platform=linux/amd64 python:3.11-slim-bookworm@sha256:0a310eeecf4e1f5a0743f9a6520c90c88d089c903ca5fd283f501e3a805f5f89
ARG VCS_REF=unknown
LABEL org.opencontainers.image.revision=$VCS_REF
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/* && useradd --create-home benchmark
WORKDIR /app
COPY --from=build --chown=benchmark:benchmark /app /app
RUN chown benchmark:benchmark /app
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
USER benchmark
ENTRYPOINT ["bankai-benchmark"]
CMD ["smoke"]
