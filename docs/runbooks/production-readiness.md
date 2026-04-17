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

## Piloto Operativo

Precondiciones del piloto:

- correr desde la raiz del repo
- tener `python` y `pwsh` disponibles en `PATH`
- usar `LOCAL_AI_AGENT_PROVIDER=stub` cuando se invoque el CLI `exec`

### Caso 1: comando valido

Objetivo:

- verificar passthrough transparente del middleware cuando el comando ya es valido

Comando:

```powershell
& .\scripts\powershell\middleware.ps1 pwsh --version
```

Resultado esperado:

- exit code `0`
- salida visible `PowerShell`
- no aparece `Router route:`

### Caso 2: comando invalido

Objetivo:

- verificar fallback real hacia correccion de comando

Comando:

```powershell
"y" | pwsh -NoProfile -File .\scripts\powershell\middleware.ps1 github.cli --version
```

Resultado esperado:

- exit code `0`
- aparece `Router route: command_fix`
- aparece `Suggested command:`
- se ejecuta `gh --version` despues de confirmar

### Caso 3: quoting complejo

Objetivo:

- verificar que el middleware respete un ejecutable citado cuyo path contiene espacios

Comando:

```powershell
$pwshPath = (Get-Command pwsh).Source
& .\scripts\powershell\middleware.ps1 "$pwshPath" --version
```

Resultado esperado:

- exit code `0`
- salida visible `PowerShell`
- no aparece fallback del router

### Caso 4: bloqueado por allowlist

Objetivo:

- verificar que la capa `exec` bloquee ejecucion cuando la allowlist no incluye la herramienta

Comando:

```powershell
$env:PYTHONPATH = "src"
$env:LOCAL_AI_AGENT_PROVIDER = "stub"
$env:LOCAL_AI_AGENT_EXEC_ALLOWLIST = "git"
python -m local_ai_agent.cli exec gh --version
```

Resultado esperado:

- exit code no cero
- salida visible `Execution blocked by allowlist: gh --version`

Limpieza:

```powershell
Remove-Item Env:LOCAL_AI_AGENT_EXEC_ALLOWLIST -ErrorAction SilentlyContinue
Remove-Item Env:LOCAL_AI_AGENT_PROVIDER -ErrorAction SilentlyContinue
Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
```

## Gate Go/No-Go

Usar esta matriz al cierre del piloto. Cada criterio debe marcarse con `PASS` o `FAIL` y debe tener evidencia concreta.

| Criterio | Verificacion | PASS cuando | FAIL cuando |
| --- | --- | --- | --- |
| Suite completa | `pytest -q` | devuelve exit code `0` | devuelve exit code no cero |
| Smoke readiness | `pwsh -NoProfile -File .\scripts\smoke\production_readiness.ps1` | devuelve exit code `0` | devuelve exit code no cero |
| Kill switch middleware | `LOCAL_AI_AGENT_MIDDLEWARE_DISABLED=1` con un comando que falle | ejecuta directo, conserva exit code y no invoca `local-ai-agent` | entra en fallback o cambia el exit code |
| Anti-recursion | invocacion recursiva del middleware | rechaza recursion con error explicito | permite recursion o entra en loop |
| Logs operativos | revisar `logs/` y `logs/router/` | los archivos esperados se crean y quedan trazas legibles | faltan logs o no se pueden interpretar |
| Piloto operativo | ejecutar los 4 casos del piloto | los 4 casos cumplen el resultado esperado | al menos un caso no cumple el resultado esperado |

Regla de decision:

- `GO`: todos los criterios anteriores estan en `PASS`.
- `NO-GO`: al menos un criterio esta en `FAIL`.

Plantilla de cierre:

```text
Decision: GO | NO-GO
Fecha:
Operador:
- Suite completa: PASS | FAIL | evidencia:
- Smoke readiness: PASS | FAIL | evidencia:
- Kill switch middleware: PASS | FAIL | evidencia:
- Anti-recursion: PASS | FAIL | evidencia:
- Logs operativos: PASS | FAIL | evidencia:
- Piloto operativo: PASS | FAIL | evidencia:
- Si la decision es NO-GO, documentar cual criterio fallo y por que.
```

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
