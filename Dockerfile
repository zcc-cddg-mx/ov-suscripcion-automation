# ov-code-agent — imagen Alpine sin Java/Gradle (~120-150 MB)
#
# Diseñada para entornos con restricciones de almacenamiento (SERVICIOSIAS).
# Cubre todo el contrato del agente excepto la verificación de compilación:
#   compile=true → descartado silenciosamente (java no disponible)
#   compile=false → comportamiento normal
#
# No requiere PAT de Gradle ni dependencias Maven.
# El repo backend se clona en el entrypoint con GIT_PAT.
#
# Build:
#   PAT=<azure-pat> ./1-build-agent.sh

FROM python:3.12-alpine

ENV PYTHONUNBUFFERED=1
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

# Build-time deps para compilar cffi (requerido por msoffcrypto-tool)
RUN apk add --no-cache \
        git \
        gcc \
        musl-dev \
        curl \
        libffi-dev \
        ca-certificates

# Certificados corporativos — TLS hacia n8n y Azure DevOps
COPY certs/localCA.crt /usr/local/share/ca-certificates/localCA.crt
COPY certs/zurichseguros-rootca-until-2031_03_20.crt /usr/local/share/ca-certificates/zurichseguros-rootca.crt
COPY certs/cacert-workflow-uat.pem /usr/local/share/ca-certificates/cacert-workflow-uat.crt
RUN update-ca-certificates

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt flask==3.1.1

COPY . .
RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 5000
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["python", "app.py"]
