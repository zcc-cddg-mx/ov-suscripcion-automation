# Code Agent — OV Suscripcion Automation
# Architecture v3: containerized HTTP service (SERVICIOSIAS)
#
# Build:
#   docker build -t ov-code-agent:latest .
#
# Run:
#   docker run -d \
#     -p 5000:5000 \
#     -e GRADLE_USERNAME=carlos.duarte2 \
#     -e GRADLE_DEV_PASSWORD=<azure-artifacts-pat> \
#     -e GIT_USERNAME=carlos.duarte2 \
#     -e GIT_PAT=<azure-repos-pat> \
#     -v /path/to/ov-arizona-backend-ecuador:/repos/ov-arizona-backend-ecuador \
#     ov-code-agent:latest

# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: Python dependencies
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS python-deps

WORKDIR /install

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install/pkg -r requirements.txt && \
    pip install --no-cache-dir --prefix=/install/pkg flask==3.1.1


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: Runtime image
# ─────────────────────────────────────────────────────────────────────────────
FROM eclipse-temurin:8-jdk-jammy

# Install Python 3.12, git, and curl
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3.12 \
        python3.12-venv \
        python3-pip \
        git \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Make python3.12 the default python3
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1 && \
    update-alternatives --install /usr/bin/python python /usr/bin/python3.12 1

# Install Gradle 6.8.3 (same version used locally)
ARG GRADLE_VERSION=6.8.3
RUN curl -fsSL "https://services.gradle.org/distributions/gradle-${GRADLE_VERSION}-bin.zip" \
        -o /tmp/gradle.zip && \
    unzip -q /tmp/gradle.zip -d /opt && \
    ln -s /opt/gradle-${GRADLE_VERSION}/bin/gradle /usr/local/bin/gradle && \
    rm /tmp/gradle.zip

# Copy Python packages from stage 1
COPY --from=python-deps /install/pkg /usr/local

# ─────────────────────────────────────────────────────────────────────────────
# Application
# ─────────────────────────────────────────────────────────────────────────────
WORKDIR /app

COPY . .

# ─────────────────────────────────────────────────────────────────────────────
# Entrypoint
# ─────────────────────────────────────────────────────────────────────────────
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 5000

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["python", "app.py"]
