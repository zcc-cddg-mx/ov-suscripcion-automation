# ov-code-agent — Code Agent para automatización de migraciones OV
#
# Hereda de ov-agent-base que ya contiene:
#   - Ubuntu 24.04 + Temurin 8 JDK + Gradle 6.8.3 + baked plugins
#   - Python 3.12 venv con openpyxl + flask
#   - Cache Maven (~243M) con todas las JARs del proyecto
#
# Build (segundos — sin descarga de dependencias):
#   docker build -t ov-code-agent:latest .
#
# Prerequisito: ov-agent-base:latest debe existir localmente o en el registry.
#   Construir con: GRADLE_DEV_PASSWORD=<pat> ./build-base.sh

FROM ov-agent-base:latest

WORKDIR /app
COPY . .
RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 5000
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["python", "app.py"]
