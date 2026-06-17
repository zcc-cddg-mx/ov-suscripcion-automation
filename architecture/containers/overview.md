# Docker — Arquitectura de contenedores del Code Agent

## Estrategia: dos imágenes

El agente se construye en dos capas para separar dependencias pesadas del código de aplicación.

```
zurcontainerreg.azurecr.io/ov-ams-ubuntu-lite:12
  └── ov-agent-base:latest        (Dockerfile.base — build lento, ~10-15 min, se hace una vez)
        └── ov-code-agent:latest  (Dockerfile — build rápido, ~5 seg, se hace con cada cambio de código)
```

**Por qué dos imágenes:**  
`ov-agent-base` acumula todo lo que no cambia: JDK, Gradle, repo backend clonado, cache Maven (~243M de JARs). Reconstruirlo en cada cambio de código tomaría 10+ minutos. `ov-code-agent` solo copia el código Python — reconstruirlo cuesta segundos.

---

## ov-agent-base (Dockerfile.base)

### Qué se hornea (build-time)

| Capa | Contenido | Por qué va en base |
|---|---|---|
| OS | Ubuntu 24.04 vía `ams-ubuntu-lite:12` | Imagen corporativa estándar |
| Runtime Java | Temurin 8 JDK (`JAVA_HOME=/usr/lib/jvm/temurin-8-jdk-amd64`) | Flyway migrations requieren Java 8 |
| Build Java | Gradle 6.8.3 (de `gradle/gradle-6.8.3.zip`) | Versión fija del proyecto backend |
| Plugins Gradle | `gradle/plugins/maven2` → `/opt/gradle-plugins/maven2` | Plugins no publicados en Azure Artifacts (gorylenko y otros) |
| Init script | `gradle/init.d/baked-plugins.gradle` → `/root/.gradle/init.d/` | Aplica los plugins bakeados a cualquier build |
| Python venv | `/opt/venv` con openpyxl, requests, msoffcrypto-tool, flask==3.1.1 | Evita re-instalar en cada rebuild del agente |
| Repo backend | `/repos/ov-arizona-backend-ecuador` (clon completo + ramas main/develop/test/developer) | El agente escribe archivos aquí y hace push |
| Cache Maven | `/repos/ov-arizona-backend-ecuador/.project/local-repo` (~243M, de `gradle/local-repo.tar.gz`) | Evita descargas desde Azure Artifacts en compilaciones normales |
| Configuración Gradle | `setup-local-gradle.sh` inyecta bloques `local-repo` en `build.gradle` y `dependencies.gradle` | Los bloques Maven apuntan al local-repo bakeado |

### Cómo se construye

```bash
PAT=<azure-pat> ./1-build-base.sh
```

El script:
1. Extrae `gradle/local-repo.tar.gz` → `gradle/local-repo/` si no existe
2. Corre `docker build --build-arg GIT_PAT="${PAT}" -f Dockerfile.base -t ov-agent-base:latest .`
3. Si `REGISTRY` está definido, hace tag y push al registry remoto

El `GIT_PAT` llega como `ARG` (build-time) y se usa solo para el `git clone`. No persiste como `ENV` — no queda en capas de la imagen.

**Credenciales en la imagen bakeada:** el `.git/config` del repo clonado contiene la URL con el PAT incrustado. Esto es aceptable en un entorno controlado (imagen privada en registry corporativo), pero conviene rotar el PAT periódicamente y reconstruir la base.

---

## ov-code-agent (Dockerfile)

### Qué se agrega sobre la base

```dockerfile
FROM ov-agent-base:latest
WORKDIR /app
COPY requirements.txt .
RUN /opt/venv/bin/pip install --no-cache-dir -r requirements.txt
COPY . .
RUN chmod +x /app/docker-entrypoint.sh
EXPOSE 5000
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["python", "app.py"]
```

Solo se copia el código Python. El `pip install` re-ejecuta sobre el venv ya existente en la base (idempotente y rápido porque las dependencias ya están ahí).

### Build normal (tras cambios de código)

```bash
docker build -t ov-code-agent:latest .
```

No necesita PAT ni argumentos especiales.

---

## docker-entrypoint.sh — arranque del contenedor

El entrypoint genera configuración en tiempo de ejecución a partir de variables de entorno, antes de lanzar Flask.

### Secuencia de arranque

```
[1] Validar vars requeridas
      GRADLE_USERNAME, GRADLE_DEV_PASSWORD, GIT_USERNAME, GIT_PAT

[2] Generar /app/config.json
      {"repo": "/repos/ov-arizona-backend-ecuador"}
      (usado por el agente Python para ubicar el repo backend)

[3] Generar ~/.gradle/gradle.properties
      Credenciales Azure Artifacts (dev/test/prod feeds)
      JVM args, workers, env=dev, customerOverlay=ecuador

[4] Configurar git credentials (PAT-based HTTPS)
      git config --global credential.helper store
      Escribe ~/.git-credentials con las URLs de Azure Repos
      git config user.email, user.name
      safe.directory para el repo bakeado

[5] Actualizar ramas del repo bakeado
      git fetch origin
      fetch main / develop / test / developer
      git checkout developer
      Reaplica setup-local-gradle.sh (idempotente)

[6] Arrancar Flask
      exec python app.py
```

Si el repo no existe en `REPO_PATH`, emite WARNING y continúa (permite correr en modo solo-generación).

---

## Variables de entorno

| Variable | Requerida | Default | Uso |
|---|---|---|---|
| `GRADLE_USERNAME` | sí | — | Usuario Azure DevOps para git y Gradle |
| `GRADLE_DEV_PASSWORD` | sí | — | PAT Azure Artifacts (feed dev) |
| `GIT_USERNAME` | sí | — | Nombre de usuario para commits git |
| `GIT_PAT` | sí | — | PAT Azure Repos (Code Read+Write) |
| `REPO_PATH` | no | `/repos/ov-arizona-backend-ecuador` | Path al repo backend bakeado |
| `PORT` | no | `5000` | Puerto HTTP de Flask |
| `GRADLE_TEST_PASSWORD` | no | `$GRADLE_DEV_PASSWORD` | PAT feed test |
| `GRADLE_PROD_PASSWORD` | no | `$GRADLE_DEV_PASSWORD` | PAT feed prod |
| `GRADLE_WORKERS_MAX` | no | `nproc` | Paralelismo Gradle |
| `N8N_CALLBACK_URL` | no | (ninguno) | URL del webhook n8n para callback al terminar una tarea |
| `TASKS_DB` | no | `/data/tasks.db` | SQLite — historial de tareas |
| `UPLOADS_DIR` | no | `/data/uploads` | Directorio temporal para archivos Excel recibidos |
| `BUILD_TIMEOUT_MINUTES` | no | `20` | Timeout para `gradle compileJava`; `0` = sin límite |
| `RETENTION_DAYS` | no | `90` | Días antes de purgar uploads y registros históricos |
| `BUSINESS_EXCEL_PASSWORD` | no | — | Contraseña del cotizador cifrado (command=rules) |

---

## Persistencia en runtime

```
Docker volume: ov-agent-data:/data
  /data/tasks.db        ← SQLite: historial de tareas (queued/running/done/error/rejected)
  /data/uploads/        ← Archivos Excel recibidos (limpiados según RETENTION_DAYS)
```

El volumen persiste entre reinicios del contenedor. Si se destruye el volumen se pierde el historial de tareas pero no hay impacto en migraciones ya pusheadas al repo.

---

## Scripts operativos

| Script | Qué hace |
|---|---|
| `1-build-base.sh` | Extrae local-repo.tar.gz + `docker build Dockerfile.base`. Opcional: push a registry si `REGISTRY` está definido. |
| `2-start-agent.sh` | `docker run -d` con env vars y volumen. Espera hasta que `/health` responde. Lee credenciales de `.env.local`. |
| `3-test-agent.sh` | 8 casos de prueba HTTP: health, validación 400, sin commit, con commit, con compile, concurrencia, historial, callback n8n. |

---

## Flujo completo primera vez

```
1. Preparar .env.local con PAT y AZURE_USERNAME

2. Construir imagen base (una sola vez, ~10-15 min):
   PAT=<pat> ./1-build-base.sh

3. Construir imagen agente (~5 seg):
   docker build -t ov-code-agent:latest .

4. Levantar contenedor:
   PAT=<pat> ./2-start-agent.sh
   # Espera hasta que /health devuelva 200

5. Probar endpoints:
   ./3-test-agent.sh

6. Tras cambios de código, solo paso 3 + 4
```

---

## Flujo en actualizaciones de código

```
git pull  (o editar código local)
docker build -t ov-code-agent:latest .
docker stop ov-code-agent && docker rm ov-code-agent
PAT=<pat> ./2-start-agent.sh
```

No es necesario reconstruir la base a menos que cambien: JDK, Gradle, plugins, dependencias Maven, o la URL/rama del repo backend.

---

## Cuándo reconstruir ov-agent-base

| Evento | Reconstruir base |
|---|---|
| Cambio en código Python (`src/`, `app.py`, `main.py`) | No — solo agente |
| Nueva dependencia Python en `requirements.txt` | No — solo agente (ya instaladas en venv base) |
| Actualización de plugins Gradle (`gradle/plugins/`) | **Sí** |
| Nueva versión de Gradle | **Sí** |
| Nuevas dependencias Maven no en local-repo | **Sí** — actualizar `gradle/local-repo.tar.gz` |
| Rotación del PAT de Azure (gitcreds bakeadas) | **Sí** |
| Cambio de rama base del repo backend | **Sí** |

---

## Observaciones y gaps conocidos

### 1. PAT bakeado en el repo clonado

El `.git/config` dentro del repo bakeado tiene la URL con el PAT de clonación. Si el PAT expira o se revoca, el `git fetch origin` en el entrypoint fallará en el siguiente arranque. Solución: el entrypoint reconfigura las credenciales con `~/.git-credentials` (el PAT de runtime), lo que sobrescribe las del clone. En la práctica el flujo es robusto, pero conviene documentarlo al rotar PATs.

### 2. Rama sucia al reiniciar

Si un proceso anterior dejó el repo en estado dirty (merge conflict, archivos sin commit de una tarea interrumpida), el `git checkout developer` en el entrypoint puede fallar. El entrypoint no hace `git reset --hard` ni `git clean -fd`. Las tareas individuales de `placer.py` crean ramas feature propias, por lo que este escenario solo ocurre si el contenedor es detenido a mitad de una operación git.

### 3. Un solo REPO_PATH por contenedor

`customerOverlay=ecuador` está hardcodeado en `gradle.properties`. No hay soporte multi-tenant en el mismo contenedor. Si en el futuro se soporta otro país/overlay, se necesitaría o una instancia separada o parametrizar el overlay vía env var.

### 4. local-repo como snapshot

El `local-repo` bakeado es un snapshot en el tiempo. Si el proyecto backend agrega nuevas dependencias Maven que no están en el snapshot, el build cae a Azure Artifacts (fallback funcional, pero más lento). Actualizar el snapshot requiere reconstruir la base.

### 5. compile=true — tiempo de respuesta

Una tarea con `compile=true` corre `gradle :ams-rule:flyway:compileJava` (o ams-policy). El primer compile en un contenedor recién levantado puede tomar varios minutos aunque el local-repo esté bakeado (Gradle daemon frío, configuración inicial). `BUILD_TIMEOUT_MINUTES=20` es suficiente. Tareas posteriores en el mismo contenedor son más rápidas (daemon caliente).
