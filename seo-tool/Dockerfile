FROM python:3.13-slim
ARG WITH_JS=false
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
WORKDIR /app
COPY pyproject.toml README.md ./
COPY seo_tool ./seo_tool
RUN pip install --no-cache-dir ".[fast,google]" && \
    if [ "$WITH_JS" = "true" ]; then pip install --no-cache-dir ".[js]" && playwright install --with-deps chromium; fi
RUN useradd --create-home seo
USER seo
WORKDIR /work
ENTRYPOINT ["seo-tool"]
