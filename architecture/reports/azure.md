● Para configurar el CLI de Azure DevOps (o el SDK Python equivalente) correctamente en un entorno de automatización, necesitas pedir al equipo de release
  lo siguiente:
     
  ---
  Lo que necesitas del equipo de release

  1. Service Account / PAT de servicio

  El más importante. No usar un PAT personal — si la persona rota o sale del equipo, la automatización se rompe.

  Pedir que creen una cuenta de servicio (ej. svc-code-agent@zurichec.com) con un PAT generado desde esa cuenta, con estos scopes mínimos:
  - Code (Read & Write) — para push de ramas
  - Pull Request Contribute — para abrir PRs

  Si usan Azure Service Principal (más robusto), necesitas: client_id, client_secret, tenant_id.

  ---
  2. Permisos en el repositorio

  Confirmar que la cuenta de servicio tiene rol Contributor en el repo ov-arizona-backend-ecuador, específicamente:
  - Permiso de push a ramas feature/*
  - Permiso de crear Pull Requests hacia develop

  ---
  3. Branch policies de develop

  Si develop tiene políticas configuradas (revisores obligatorios, aprobación mínima, build requerido), el PR se creará pero no podrá auto-mergearse — lo
  cual está bien para el flujo actual (el agente abre el PR, un humano lo aprueba).

  Pedir que confirmen:
  - ¿Cuántos revisores mínimos requiere develop?
  - ¿Hay reviewers automáticos asignados (ej. el team lead siempre se agrega)?
  - ¿Hay una política de build/CI obligatoria antes del merge?

  Esto determina qué campos incluir al crear el PR (auto-completar, reviewers iniciales).

  - Permiso de crear Pull Requests hacia develop

  ---
  3. Branch policies de develop

  Si develop tiene políticas configuradas (revisores obligatorios, aprobación mínima, build requerido), el PR se creará pero no podrá auto-mergearse — lo
  cual está bien para el flujo actual (el agente abre el PR, un humano lo aprueba).

  Pedir que confirmen:
  - ¿Cuántos revisores mínimos requiere develop?
  - ¿Hay reviewers automáticos asignados (ej. el team lead siempre se agrega)?
  - ¿Hay una política de build/CI obligatoria antes del merge?

  Esto determina qué campos incluir al crear el PR (auto-completar, reviewers iniciales).

  ---
  4. Configuración de n8n (si el push lo hace n8n, no el servidor local)

  Si en producción n8n es quien invoca el agente (no un desarrollador desde su máquina local), el PAT debe estar almacenado en las variables de
  entorno/secretos de n8n, no en config.json de una máquina individual.

  Pedir al equipo de release que confirmen dónde se desplegará el agente para definir cómo se inyectan las credenciales.

  ---
  Resumen de lo que pedir

  ┌──────────────────────────────────────────────────────┬─────────────────────────────────────────────┐
  │                         Item                         │                  Para qué                   │
  ├──────────────────────────────────────────────────────┼─────────────────────────────────────────────┤
  │ PAT de cuenta de servicio (scopes: Code RW + PR)     │ Autenticar el agente contra Azure Repos     │
  ├──────────────────────────────────────────────────────┼─────────────────────────────────────────────┤
  │ Rol Contributor en ov-arizona-backend-ecuador        │ Push de ramas + creación de PRs             │
  ├──────────────────────────────────────────────────────┼─────────────────────────────────────────────┤
  │ Branch policies de develop                           │ Saber qué campos configurar en el PR        │
  ├──────────────────────────────────────────────────────┼─────────────────────────────────────────────┤
  │ Estrategia de secretos (config local vs n8n secrets) │ Definir cómo almacenar el PAT en producción │
  └──────────────────────────────────────────────────────┴─────────────────────────────────────────────┘
