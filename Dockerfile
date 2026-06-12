# Code Agent — OV Suscripcion Automation
# Architecture v3: containerized HTTP service (SERVICIOSIAS)
#
# Inherits from ams-ubuntu-lite:26 — Ubuntu 26.04 + Temurin 8 JDK + Zurich CA certs
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
#     -v /data/gradle-cache:/root/.gradle/caches \
#     ov-code-agent:latest
#
# Gradle cache volume (/data/gradle-cache):
#   - First run downloads JARs from Azure Artifacts → cached in the host volume
#   - Subsequent runs reuse the cache — no re-download needed
#   - Credentials are injected at runtime (not baked in the image)

# ubnutu 24.04 + Temurin 8 JDK + Python 3.12 + wget + Zurich CA certs
FROM ams-ubuntu-lite:latest

# ─────────────────────────────────────────────────────────────────────────────
# System dependencies
# Base provides: Ubuntu 24.04, Temurin 8 JDK, Python 3.12, wget, Zurich CA certs
# We add: git, unzip, pip
# ─────────────────────────────────────────────────────────────────────────────
RUN apt-get -qq update && \
    apt-get -qq -y install --no-install-recommends \
        python3-pip \
        python3-venv \
        git \
        unzip \
    && rm -rf /var/lib/apt/lists/*

# ─────────────────────────────────────────────────────────────────────────────
# Gradle 6.8.3 — copied from local artifact (avoids corporate SSL interception)
# ─────────────────────────────────────────────────────────────────────────────
COPY gradle-6.8.3.zip /tmp/gradle.zip
RUN unzip -q /tmp/gradle.zip -d /opt && \
    ln -s /opt/gradle-6.8.3/bin/gradle /usr/local/bin/gradle && \
    rm /tmp/gradle.zip

# ─────────────────────────────────────────────────────────────────────────────
# Gradle plugin JARs not published to Azure Artifacts — baked as a Maven2 repo.
# init.d/baked-plugins.gradle injects this repo into every buildscript so
# Gradle resolves them locally without modifying the backend build.gradle.
# ─────────────────────────────────────────────────────────────────────────────
COPY gradle-plugins/maven2 /opt/gradle-plugins/maven2
COPY gradle-init.d/baked-plugins.gradle /root/.gradle/init.d/baked-plugins.gradle

# ─────────────────────────────────────────────────────────────────────────────
# Python dependencies — venv isolates from system packages (avoids RECORD conflicts)
# ─────────────────────────────────────────────────────────────────────────────
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt flask==3.1.1

# ─────────────────────────────────────────────────────────────────────────────
# Application
# ─────────────────────────────────────────────────────────────────────────────
WORKDIR /app
COPY . .

# ─────────────────────────────────────────────────────────────────────────────
# Entrypoint
# ─────────────────────────────────────────────────────────────────────────────
RUN chmod +x /app/docker-entrypoint.sh

ENV JAVA_HOME=/usr/lib/jvm/temurin-8-jdk-amd64
ENV PATH="${JAVA_HOME}/bin:${PATH}"

EXPOSE 5000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["python", "app.py"]
