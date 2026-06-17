# Docker — Arquitectura de contenedores del Code Agent

## Imagen: ov-code-agent (Alpine)

```
python:3.12-alpine
  └── ov-code-agent:latest  (Dockerfile — build ~2 min)
```

Imagen única basada en Alpine. Sin JDK, sin Gradle, sin repo bakeado — ligera (~120-150 MB) y adecuada para entornos con restricciones de almacenamiento (SERVICIOSIAS).

Cubre el contrato completo del agente: `/run`, `/status`, `/tasks`, `/health`, callback n8n, SQLite.

### Comportamiento de `compile`

`compile` llega como campo del form en el POST `/run` y siempre se acepta sin error:

| `compile` recibido | Resultado |
|---|---|
| `false` | Omite build, push normal |
| `true` | Descartado silenciosamente — push normal (java no disponible) |

La detección es automática: `build_check._JAVA_AVAILABLE` evalúa al arrancar si `java` y `gradle` están en PATH. En Alpine no lo están, por lo que `verify()` retorna sin hacer nada.

---

## Dockerfile

```dockerfile
FROM python:3.12-alpine
RUN apk add --no-cache git gcc musl-dev libffi-dev
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt flask==3.1.1
COPY . .
RUN chmod +x /app/docker-entrypoint.sh
EXPOSE 5000
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["python", "app.py"]
```

`gcc`, `musl-dev` y `libffi-dev` son necesarios en build-time para compilar `cffi` (dependencia de `msoffcrypto-tool`). No quedan activos en runtime.

---

## docker-entrypoint.sh — secuencia de arranque

```
[1] Validar vars requeridas
      GIT_USERNAME, GIT_PAT

[2] Generar /app/config.json
      {"repo": "/repos/ov-arizona-backend-ecuador"}

[3] Configurar git credentials
      credential.helper store → ~/.git-credentials
      git config user.email, user.name, safe.directory

[4a] Primera vez (REPO_PATH/.git no existe):
      git clone → REPO_PATH
      git checkout developer

[4b] Reinicios (repo ya presente):
      git checkout developer
      git pull origin developer

[5] Arrancar Flask
      exec python app.py
```

El primer arranque tarda lo que dure el clone (~1-2 min según red). Los reinicios son rápidos — solo un `git pull`.

---

## Variables de entorno

| Variable | Requerida | Default | Uso |
|---|---|---|---|
| `GIT_USERNAME` | sí | — | Usuario para commits y credencial HTTPS |
| `GIT_PAT` | sí | — | PAT Azure Repos (Code Read+Write) |
| `REPO_PATH` | no | `/repos/ov-arizona-backend-ecuador` | Path donde clonar/actualizar el repo |
| `PORT` | no | `5000` | Puerto HTTP de Flask |
| `N8N_CALLBACK_URL` | no | (ninguno) | Webhook n8n para callback al terminar una tarea |
| `TASKS_DB` | no | `/data/tasks.db` | SQLite — historial de tareas |
| `UPLOADS_DIR` | no | `/data/uploads` | Directorio temporal para archivos Excel |
| `RETENTION_DAYS` | no | `90` | Días antes de purgar uploads e historial |
| `BUSINESS_EXCEL_PASSWORD` | no | — | Contraseña del cotizador cifrado (command=rules) |

---

## Persistencia en runtime

```
Docker volume: ov-agent-data:/data
  /data/tasks.db     ← SQLite: historial de tareas (queued/running/done/error/rejected)
  /data/uploads/     ← Archivos Excel recibidos (limpiados según RETENTION_DAYS)

Docker volume: ov-repo:/repos
  /repos/ov-arizona-backend-ecuador/   ← repo backend clonado en primer arranque
```

Montar `/repos` como volumen externo evita re-clonar en cada recreación del contenedor. Si el volumen se destruye, el siguiente arranque clona de nuevo automáticamente.

---

## Scripts operativos

| Script | Qué hace |
|---|---|
| `1-build-agent.sh` | `docker build Dockerfile` → `ov-code-agent:latest`. Opcional: push a registry si `REGISTRY` está definido. |
| `2-start-agent.sh` | `docker run -d` con `GIT_PAT`, volúmenes `/data` y `/repos`. Espera hasta que `/health` responde. |
| `3-test-agent.sh` | 8 casos de prueba HTTP: health, validación 400, sin commit, con commit, con compile, concurrencia, historial, callback n8n. |

### Backup de referencia

```
docker/
  full/   ← archivos de la variante Ubuntu+Java (histórico)
  lite/   ← copia de los archivos activos actuales (Alpine)
```

Los archivos activos en la raíz son la fuente de verdad. Los de `docker/` son referencia estática.

---

## Flujo primera vez

```
1. Preparar .env.local con PAT y AZURE_USERNAME

2. Construir imagen (~2 min):
   PAT=<pat> ./1-build-agent.sh

3. Levantar contenedor:
   PAT=<pat> ./2-start-agent.sh
   # Primer arranque clona el repo (~1-2 min)
   # /health responde cuando Flask está listo

4. Probar endpoints:
   ./3-test-agent.sh
```

## Flujo en actualizaciones de código

```
git pull
PAT=<pat> ./1-build-agent.sh
docker stop ov-code-agent && docker rm ov-code-agent
PAT=<pat> ./2-start-agent.sh
# El repo ya existe en el volumen — reinicio rápido (git pull)
```

## Cuándo reconstruir la imagen

| Evento | Reconstruir |
|---|---|
| Cambio en código Python (`src/`, `app.py`, `main.py`) | **Sí** |
| Nueva dependencia Python en `requirements.txt` | **Sí** |
| Cambio de rama base del repo backend | No — el entrypoint actualiza en cada arranque |

---

## Observaciones y gaps conocidos

### 1. Primer arranque lento

El clone inicial del repo puede tardar 1-2 minutos según la red. Durante ese tiempo `/health` no responde todavía. `2-start-agent.sh` espera con polling hasta que responde.

### 2. Rama sucia al reiniciar

Si el contenedor fue detenido a mitad de una operación git, el `git checkout developer` puede fallar por archivos sin commit. Las tareas del agente crean ramas feature propias (nunca trabajan directamente en `developer`), por lo que este escenario es improbable. Si ocurre, borrar el volumen `/repos` fuerza un clone limpio en el siguiente arranque.

### 3. compile=true silencioso

Si n8n envía `compile=true`, la compilación se descarta sin error HTTP — la tarea completa normalmente y `build_status` queda como `null` en el callback (no `"success"`). n8n debe interpretar `build_status=null` como "no aplica", no como fallo.
