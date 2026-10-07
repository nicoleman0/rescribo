# Production HTTPS proxy: the built frontend plus forwarding to the API.
# Build from the repository root: docker build -f proxy/Dockerfile .
FROM node:24-slim AS frontend
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

FROM caddy:2.11-alpine
COPY proxy/Caddyfile /etc/caddy/Caddyfile
COPY --from=frontend /app/dist /srv/app
