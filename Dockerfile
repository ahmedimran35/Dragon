# Dragon in a container: the agent sees /data (its memory, vault, audit log) and
# /workspace (its files), and the web app on :8787.
#
#   docker build -t dragon .
#   docker run -d -p 127.0.0.1:8787:8787 --env-file .env -v dragon-data:/data -v $PWD/workspace:/workspace dragon
#
# The first run prints the access-token URL once; it is also in the `dragon-data` volume
# under server_token. With a browser tool (Chromium + Playwright, ~400 MB more):
#   docker build --build-arg WITH_BROWSER=1 -t dragon:browser .

# --- stage 1: build the web app into dragon/server/static ---------------------
FROM node:22-slim AS web
WORKDIR /src/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
# vite writes the production build straight into the Python package
RUN npm run build

# --- stage 2: the runtime ----------------------------------------------------
FROM python:3.12-slim
LABEL org.opencontainers.image.title="Dragon" \
      org.opencontainers.image.licenses="GPL-3.0-or-later"

# Override for a regional PyPI mirror, e.g.
#   docker build --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple .
ARG PIP_INDEX_URL=https://pypi.org/simple
# 1 = bundle Chromium and turn the browser tool on
ARG WITH_BROWSER=0

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_INDEX_URL=${PIP_INDEX_URL} \
    DRAGON_DATA_DIR=/data \
    DRAGON_WORKSPACE=/workspace \
    DRAGON_CONFIG=/app/config/config.toml \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

RUN useradd --create-home --uid 1000 dragon \
 && mkdir -p /data /workspace /app/config \
 && chown -R dragon:dragon /data /workspace /app

WORKDIR /app
COPY --chown=dragon:dragon pyproject.toml README.md LICENSE NOTICE ./
COPY --chown=dragon:dragon dragon ./dragon
COPY --chown=dragon:dragon config/config.example.toml ./config/config.example.toml
# the web app built in stage 1
COPY --from=web --chown=dragon:dragon /src/dragon/server/static ./dragon/server/static

RUN if [ "$WITH_BROWSER" = "1" ]; then \
      pip install --no-cache-dir ".[browser,channels]" \
      && playwright install --with-deps chromium \
      && chmod -R a+rX /ms-playwright \
      && rm -rf /var/lib/apt/lists/*; \
    else \
      pip install --no-cache-dir ".[channels]"; \
    fi \
 && ln -s /workspace /app/workspace \
 && cp config/config.example.toml config/config.toml

# the browser tool is on in the browser image ("1"); anything else leaves config.toml alone
ENV DRAGON_BROWSER_ENABLED=${WITH_BROWSER}

USER dragon
VOLUME ["/data", "/workspace"]
EXPOSE 8787

# For the default `serve` command; a container running `chat` or `run` has no server and
# shows unhealthy, which `--no-healthcheck` on `docker run` turns off.
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8787/api/health', timeout=3).status == 200 else 1)"

# The web app. Override with `dragon chat`, `dragon run "..."`, `dragon daemon`, ...
CMD ["dragon", "serve", "--host", "0.0.0.0"]
