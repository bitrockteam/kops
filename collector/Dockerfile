FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN useradd --create-home --uid 10001 kops \
    && mkdir -p /var/lib/kops/raw \
    && chown -R 10001:10001 /var/lib/kops
WORKDIR /opt/kops
COPY collector ./collector
USER 10001:10001

CMD ["python", "-m", "collector.run", "--registry", "/etc/kops/collectors.yaml"]
