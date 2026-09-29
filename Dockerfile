FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN useradd --create-home --uid 10001 kops \
    && mkdir -p /var/lib/kops/content/sources /var/lib/kops/content/candidates /var/lib/kops/content/pages /var/lib/kops/content/answers \
    && chown -R 10001:10001 /var/lib/kops
WORKDIR /opt/kops
COPY pyproject.toml ./
RUN python -m pip install --no-cache-dir \
    setuptools wheel \
    bleach==6.2.0 fastapi==0.118.0 httpx==0.28.1 itsdangerous==2.2.0 \
    jinja2==3.1.6 markdown-it-py==4.0.0 "psycopg[binary,pool]==3.2.10" \
    pydantic==2.11.9 python-multipart==0.0.20 uvicorn==0.37.0
COPY app ./app
COPY scripts ./scripts
COPY fixtures ./fixtures
RUN python -m pip install --no-cache-dir --no-build-isolation --no-deps .
USER 10001:10001

FROM base AS runtime
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]

FROM base AS test
USER root
RUN python -m pip install --no-cache-dir pytest==8.4.2 pytest-cov==7.0.0
COPY tests ./tests
USER 10001:10001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
