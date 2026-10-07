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
