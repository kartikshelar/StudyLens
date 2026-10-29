FROM node:22-bookworm-slim AS web
WORKDIR /build/web
RUN corepack enable && corepack prepare pnpm@10.34.9 --activate
COPY web/package.json web/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY web/ ./
RUN pnpm build

FROM ghcr.io/astral-sh/uv:0.12.2 AS uv

FROM python:3.12-slim
COPY --from=uv /uv /usr/local/bin/uv
ENV PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    STUDYLENS_ENV=production \
    STUDYLENS_WEB_DIST=/app/web/dist
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/app/ ./app/
COPY --from=web /build/web/dist /app/web/dist
RUN useradd --create-home --uid 10001 studylens
USER studylens
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8000')+'/healthz',timeout=3)"
CMD ["uv", "run", "--no-sync", "python", "-m", "app.serve"]
