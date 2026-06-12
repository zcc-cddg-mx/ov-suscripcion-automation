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
#     ov-code-agent:latest

FROM ams-ubuntu-lite:26

# ─────────────────────────────────────────────────────────────────────────────
# System dependencies
# ─────────────────────────────────────────────────────────────────────────────
RUN apt-get -qq update && \
    apt-get -qq -y install --no-install-recommends \
        python3.12 \
        python3-pip \
        git \
        unzip \
    && rm -rf /var/lib/apt/lists/*

RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1 && \
    update-alternatives --install /usr/bin/python  python  /usr/bin/python3.12 1

# ─────────────────────────────────────────────────────────────────────────────
# Gradle 6.8.3
# ─────────────────────────────────────────────────────────────────────────────
ARG GRADLE_VERSION=6.8.3
RUN wget -q "https://services.gradle.org/distributions/gradle-${GRADLE_VERSION}-bin.zip" \
        -O /tmp/gradle.zip && \
    unzip -q /tmp/gradle.zip -d /opt && \
    ln -s /opt/gradle-${GRADLE_VERSION}/bin/gradle /usr/local/bin/gradle && \
    rm /tmp/gradle.zip

# ─────────────────────────────────────────────────────────────────────────────
# Python dependencies
# ─────────────────────────────────────────────────────────────────────────────
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
