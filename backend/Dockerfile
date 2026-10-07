FROM ghcr.io/astral-sh/uv:0.11.21 AS uv

# Same Rust release as rust/rust-toolchain.toml. Trixie matches the runtime image's glibc.
FROM rust:1.92-slim-trixie AS matcher
WORKDIR /build
# The toolchain file is left out: it would make rustup download lint components.
COPY rust/matcher ./rust/matcher
COPY backend/matching/configs ./backend/matching/configs
RUN cargo build --locked --release --manifest-path rust/matcher/Cargo.toml

FROM python:3.14-slim AS dev
COPY --from=uv /uv /uvx /bin/
COPY --from=matcher /build/rust/matcher/target/release/matcher /usr/local/bin/rescribo-matcher
ENV RESCRIBO_MATCHER_PATH=/usr/local/bin/rescribo-matcher
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked
COPY backend ./backend
EXPOSE 8000

FROM python:3.14-slim AS production
COPY --from=uv /uv /bin/
COPY --from=matcher /build/rust/matcher/target/release/matcher /usr/local/bin/rescribo-matcher
ENV RESCRIBO_MATCHER_PATH=/usr/local/bin/rescribo-matcher \
    UV_COMPILE_BYTECODE=1 \
    PATH=/app/.venv/bin:$PATH
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-cache
COPY backend ./backend
# collectstatic loads settings but never connects, so placeholders are enough.
RUN DJANGO_SECRET_KEY=collectstatic RESCRIBO_DATABASE_URL=postgresql://unused/unused \
    RESCRIBO_REDIS_URL=redis://unused python backend/manage.py collectstatic --noinput
RUN useradd --system --uid 10001 rescribo
USER rescribo
EXPOSE 8000
CMD ["gunicorn", "--chdir", "backend", "--bind", "0.0.0.0:8000", "--workers", "3", "config.wsgi"]
