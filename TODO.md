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

## Pendiente — Integración con n8n

- [ ] **Configurar URL real de n8n en producción** — descomentar `N8N_CALLBACK_URL` en `.env.local` y en el servidor SERVICIOSIAS con la URL definitiva (no webhook-test)
- [ ] **Prueba end-to-end con n8n real** — disparar desde Jira → n8n → agente → callback → PR creado en Azure DevOps

---

## Pendiente — Calidad y robustez

- [x] **Timeout de tarea** — `BUILD_TIMEOUT_MINUTES` (default 20): mata el proceso Gradle si supera el límite y retorna `BuildCheckError`; lock liberado en el `finally`
- [x] **Limpieza de uploads** — `cleanup_old_uploads()` borra archivos de `/data/uploads/` al arrancar; configurable con `RETENTION_DAYS` (default 90)
- [x] **Limpieza de tareas SQLite** — `cleanup_old_records()` purga registros > `RETENTION_DAYS` días al arrancar
- [x] **Retry del callback** — `_notify_n8n()` reintenta hasta 3 veces con backoff exponencial (2s, 4s, 8s) antes de descartar

---

## Pendiente — Operaciones

- [x] **Código publicado en Azure DevOps** — repo `ov-code-agent`, rama `test` (branch protection en main/develop requiere PR)
- [ ] **Despliegue en SERVICIOSIAS** — subir imagen al registry interno, configurar variables de entorno, montar volumen persistente
- [x] **`gradle/local-repo.tar.gz`** — definir mecanismo de distribución al equipo de release (SharePoint, pipeline, etc.) dado que no está en git (384M)
- [x] **Renovar PAT** — PAT expuesto fue eliminado del historial git con `filter-repo`; generar nuevo PAT en Azure DevOps si aún no se hizo
- [ ] **Soporte para tipo `rules`** — validar y probar el flujo completo de `command=rules` con archivo adjunto via multipart (actualmente solo `ren-data` fue probado end-to-end)

---

## Pendiente — QA Agent (nuevo agente)

- [x] **Contrato de diseño** — `architecture/qa_agent_contract.md` generado con API, checks, callback, variables de entorno y dudas pendientes con backend
- [ ] **Confirmar esquema de BD DEV** — nombre de tablas, campos `migration_id` / `renewal_blocked` con equipo backend (ver §10 del contrato)
- [ ] **Implementar QA Agent** — container Python, endpoints `/validate` `/status` `/tasks` `/health`, checks SQL + HTTP, callback n8n con retry
- [ ] **Configurar en n8n** — wiring: pipeline DEV completado → POST /validate → esperar callback → actualizar Jira

---

## Recomendaciones futuras

- [ ] **Autenticación en la API** — agregar un header `X-Agent-Token` o API key para que solo n8n pueda llamar al agente (evitar ejecuciones no autorizadas en producción)
- [ ] **Logs centralizados** — enviar logs estructurados a un sistema externo (Elastic, Splunk) para auditoría de migraciones
- [ ] **Reconstrucción automática de la imagen base** — pipeline en Azure DevOps que regenere `ov-agent-base` cuando se actualice `local-repo.tar.gz` o el repo backend tenga cambios en dependencias
- [ ] **Progreso granular en `running`** — agregar sub-estados (`running:generating`, `running:compiling`, `running:pushing`) para que n8n pueda mostrar progreso real al operador
