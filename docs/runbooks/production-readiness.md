# Production Readiness Runbook

## Objetivo

Este runbook cubre la operacion base del middleware PowerShell y el smoke check de readiness para este repo.

## Habilitar y deshabilitar middleware

Middleware habilitado por defecto:

```powershell
"y" | pwsh -NoProfile -File .\scripts\powershell\middleware.ps1 github.cli --version
```

Deshabilitar middleware con kill switch operativo:

```powershell
$env:LOCAL_AI_AGENT_MIDDLEWARE_DISABLED = "1"
pwsh -NoProfile -File .\scripts\powershell\middleware.ps1 gh --version
```

Volver a habilitar middleware:

```powershell
Remove-Item Env:LOCAL_AI_AGENT_MIDDLEWARE_DISABLED
```

Notas:

- Con el kill switch activo, `middleware.ps1` ejecuta el comando directamente y no llama a `local-ai-agent`.
- La guardia anti-recursion sigue activa incluso si el kill switch esta encendido.

## Ubicacion de logs

Ubicacion por defecto:

- interacciones: `logs/<session-id>.jsonl`
- eventos del router: `logs/router/<session-id>.jsonl`

Cambiar directorio de logs:

```powershell
$env:LOCAL_AI_AGENT_LOGS_DIR = ".\logs"
```

Que revisar:

- `logs/<session-id>.jsonl` para request/response del agente
- `logs/router/<session-id>.jsonl` para eventos de resolucion del middleware
- los secretos sensibles quedan redactados como `[REDACTED]`

## Smoke Check

Ejecutar desde la raiz del repo:

```powershell
pwsh -NoProfile -File .\scripts\smoke\production_readiness.ps1
```

Que hace el smoke script:

- corre `pytest -q`
- levanta un E2E real del middleware con `LOCAL_AI_AGENT_PROVIDER=stub`
- falla explicitamente si cualquiera de los dos pasos devuelve exit code no cero o si el E2E no produce la salida esperada

## Fallos comunes y soluciones

### `pytest` no existe

Sintoma:

- el smoke script falla antes del E2E

Solucion:

```powershell
python -m pip install -e .[dev]
```

### `python` no existe o no resuelve el driver del smoke

Sintoma:

- el E2E falla al invocar el shim temporal de `local-ai-agent`

Solucion:

- verificar que `python` este en `PATH`
- si trabajas en venv, activarlo antes de correr el smoke script

### No se crea `logs/router/<session-id>.jsonl`

Sintoma:

- el E2E termina sin router log

Solucion:

- verificar `LOCAL_AI_AGENT_LOGS_DIR`
- confirmar que el provider sea `stub` u otro provider valido con credenciales
- revisar permisos de escritura en el directorio de logs

### El middleware no hace fallback

Sintoma:

- el comando falla directo y no aparece `Router route: command_fix`

Solucion:

- revisar si `LOCAL_AI_AGENT_MIDDLEWARE_DISABLED=1` sigue activo
- revisar si el comando original realmente falla o no existe
- confirmar que `local-ai-agent` este resolviendo desde el entorno activo

### Error de recursion del middleware

Sintoma:

- aparece `Refusing recursive middleware invocation.`

Solucion:

- no invoques `middleware.ps1` a traves de si mismo
- revisar wrappers shell o aliases que puedan reenviar al middleware
