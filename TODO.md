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
- [x] **Verificar contrato de respuesta con n8n** — confirmar que los campos `branch` y `aux_branch` que recibe n8n son suficientes para crear los dos PRs via Azure CLI

---

## En curso — equipo n8n + operaciones

- [ ] **Configurar URL real de n8n en producción** — `N8N_CALLBACK_URL` con URL definitiva en SERVICIOSIAS
- [ ] **Despliegue en SERVICIOSIAS** — imagen al registry, variables de entorno, volumen persistente
- [ ] **Prueba end-to-end con n8n real** — Jira → n8n → agente → callback → PR en Azure DevOps
- [ ] **Soporte `rules` end-to-end** — validar flujo completo de `command=rules` con multipart
- [ ] **QA Agent: confirmar esquema BD DEV** — tablas/campos con equipo backend (§10 del contrato)
- [ ] **QA Agent: implementar** — container Python, checks SQL + HTTP, callback n8n con retry
- [ ] **QA Agent: configurar en n8n** — pipeline DEV completado → POST /validate → callback → Jira

---

## Calidad y robustez — completado

- [x] **Timeout de tarea** — `BUILD_TIMEOUT_MINUTES` (default 20)
- [x] **Limpieza de uploads** — `cleanup_old_uploads()` al arrancar, configurable con `RETENTION_DAYS`
- [x] **Limpieza de tareas SQLite** — `cleanup_old_records()` al arrancar
- [x] **Retry del callback** — 3 reintentos con backoff exponencial (2s, 4s, 8s)

---

## Recomendaciones futuras

- [ ] **Autenticación en la API** — agregar un header `X-Agent-Token` o API key para que solo n8n pueda llamar al agente (evitar ejecuciones no autorizadas en producción)
- [ ] **Logs centralizados** — enviar logs estructurados a un sistema externo (Elastic, Splunk) para auditoría de migraciones
- [ ] **Reconstrucción automática de la imagen base** — pipeline en Azure DevOps que regenere `ov-agent-base` cuando se actualice `local-repo.tar.gz` o el repo backend tenga cambios en dependencias
- [ ] **Progreso granular en `running`** — agregar sub-estados (`running:generating`, `running:compiling`, `running:pushing`) para que n8n pueda mostrar progreso real al operador
