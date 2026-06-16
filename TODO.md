# TODO — ov-suscripcion-automation

## Completado

- [x] HTTP API Flask — `POST /run`, `GET /status`, `GET /tasks`, `GET /health`
- [x] Recepción de archivo Excel via `multipart/form-data`
- [x] Validación de campos requeridos (file, command, ticket, year, month) → 400
- [x] Guardado de archivo subido en `/data/uploads/`
- [x] Generación de archivos Flyway (.xlsx + .java)
- [x] Creación de `feature/` branch + `_developer_auxiliar` branch
- [x] Verificación de compilación Java (`compile=true`) con javac antes del push
- [x] git push robusto con retry `--force-with-lease` si la rama ya existe
- [x] Persistencia de tareas en SQLite (`/data/tasks.db`)
- [x] Callback POST a n8n al finalizar tarea (éxito o error)
- [x] Imagen base `ov-agent-base` con repo clonado + local-repo Maven 455M bakeado
- [x] `setup-local-gradle.sh` — parche idempotente en cada checkout de rama
- [x] `gradle.workers.max` dinámico via `nproc`
- [x] Scripts numerados: `1-build-base.sh`, `2-start-agent.sh`, `3-test-agent.sh`
- [x] Mock n8n local (`tests/mock_n8n.py`) para pruebas de callback

---

## Pendiente — Integración con n8n

- [ ] **Configurar URL real de n8n en producción** — descomentar `N8N_CALLBACK_URL` en `.env.local` y en el servidor SERVICIOSIAS con la URL definitiva (no webhook-test)
- [ ] **Verificar contrato de respuesta con n8n** — confirmar que los campos `branch` y `aux_branch` que recibe n8n son suficientes para crear los dos PRs via Azure CLI
- [ ] **Prueba end-to-end con n8n real** — disparar desde Jira → n8n → agente → callback → PR creado en Azure DevOps

---

## Pendiente — Calidad y robustez

- [ ] **Progreso granular en `running`** — agregar sub-estados (`running:generating`, `running:compiling`, `running:pushing`) para que n8n pueda mostrar progreso real al operador
- [ ] **Timeout de tarea** — si compile=true tarda más de N minutos, matar el proceso Gradle y responder error (evita que el lock quede tomado indefinidamente si Gradle se cuelga)
- [ ] **Limpieza de uploads** — borrar archivos de `/data/uploads/` después de N días para evitar acumulación de Excel en disco
- [ ] **Limpieza de tareas SQLite** — purgar registros antiguos (> 30 días) automáticamente al arrancar
- [ ] **Retry del callback** — si n8n no responde al primer intento, reintentar 2-3 veces con backoff antes de descartar

---

## Pendiente — Operaciones

- [ ] **Despliegue en SERVICIOSIAS** — subir imagen al registry interno, configurar variables de entorno, montar volumen persistente
- [ ] **`gradle/local-repo.tar.gz`** — definir mecanismo de distribución al equipo de release (SharePoint, pipeline, etc.) dado que no está en git (384M)
- [ ] **Renovar PAT** — el PAT actual en `.env.local` fue expuesto en el historial git (commit `18fa1ec1`); generar uno nuevo en Azure DevOps si no se hizo ya
- [ ] **Soporte para tipo `rules`** — validar y probar el flujo completo de `command=rules` con archivo adjunto via multipart (actualmente solo `ren-data` fue probado end-to-end)

---

## Recomendaciones futuras

- [ ] **Autenticación en la API** — agregar un header `X-Agent-Token` o API key para que solo n8n pueda llamar al agente (evitar ejecuciones no autorizadas en producción)
- [ ] **Logs centralizados** — enviar logs estructurados a un sistema externo (Elastic, Splunk) para auditoría de migraciones
- [ ] **Reconstrucción automática de la imagen base** — pipeline en Azure DevOps que regenere `ov-agent-base` cuando se actualice `local-repo.tar.gz` o el repo backend tenga cambios en dependencias
