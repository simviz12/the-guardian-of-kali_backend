# The Guardian of Kaliche - Backend
> Motor de Inteligencia Artificial y auditoría Zero-Trust para **The Guardian of Kaliche**, construido sobre Python, FastAPI y SQLite.

---

## ⚡ EJECUCIÓN RÁPIDA MEDIANTE SCRIPTS (.BAT)

Para la ejecución conjunta de todo el ecosistema (Frontend + Backend), utiliza los scripts batch en la raíz del proyecto:

* 🛠️ **`Instalar_Guardian.bat`**: Instala el entorno virtual de Python `.venv`, dependencias de `requirements.txt` y prepara Node.js.
* 🚀 **`Iniciar_Guardian.bat`**: Lanza el servidor backend FastAPI en segundo plano y abre la aplicación en ~2 segundos.

---

## 🏗️ ARQUITECTURA DEL SISTEMA (CLEAN ARCHITECTURE)

Este backend ha sido diseñado siguiendo estrictamente los principios de **Clean Architecture** para garantizar que el código sea testeable, mantenible y totalmente desacoplado de frameworks e interfaces externas:

```text
the-guardian-of-kali_backend/
├── src/
│   ├── domain/               # Capa 1: Entidades del Negocio (Puras, sin dependencias)
│   │   ├── entities/         # Modelos de Dominio (command.py, session.py, chat_message.py)
│   │   ├── value_objects/    # Enums y constantes (RiskLevel, CommandOrigin)
│   │   └── policies/         # Reglas de validación y listas negras de comandos
│   │
│   ├── application/          # Capa 2: Casos de Uso (Lógica de la Aplicación)
│   │   ├── use_cases/        # Flujos operativos (execute_command.py, chat_with_ai.py, get_history.py)
│   │   └── ports/            # Interfaces abstractas (session_repository.py, ai_gateway.py)
│   │
│   ├── adapters/             # Capa 3: Adaptadores de Interfaces (Puentes externos)
│   │   ├── ai/               # Integración con Google Gemini (gemini_ai_gateway.py)
│   │   ├── storage/          # Persistencia SQLite (sqlite_session_repository.py)
│   │   └── terminal/         # Interfaz con la shell local (local_subprocess_terminal.py)
│   │
│   └── infrastructure/       # Capa 4: Frameworks y Controladores (FastAPI)
│       ├── config/           # Configuraciones y Prompts de SecOps (settings.py, system_prompt.py)
│       ├── dependencies.py   # Inyección de Dependencias
│       └── main.py           # Endpoints HTTP FastAPI (Controladores REST)
```

---

## 🛠️ EJECUCIÓN MANUAL (MODO DESARROLLO)

```bash
# 1. Crear entorno virtual
python -m venv .venv

# 2. Activar entorno virtual
.venv\Scripts\activate

# 3. Instalar librerías
pip install -r requirements.txt

# 4. Iniciar servidor FastAPI
python -m src.main
```

---

## 🔌 TERMINAL EN TIEMPO REAL Y EJECUCIÓN DE COMANDOS

El backend ofrece dos vías de ejecución sobre **Kali Linux en WSL2**:

- **REST `POST /execute`** — ejecución puntual, pasada por el motor de políticas Zero-Trust.
  Usa un `WSLShellExecutor` **100% asíncrono** (`asyncio.create_subprocess_exec`) que **no bloquea**
  el event loop, respeta pipes `|`, redirecciones, variables de entorno y códigos de salida, y aplica un
  **timeout robusto** que termina (`SIGTERM` → `SIGKILL`) y **recolecta** el proceso para no dejar
  procesos huérfanos/zombies.
- **WebSocket `GET /ws/terminal`** — canal de **streaming bidireccional** en tiempo real
  (stdin/stdout/stderr) contra una sesión `bash` interactiva por conexión. Protocolo de frames:
  - Cliente → servidor: texto plano, o JSON `{"type":"input","data":"..."}` / `{"type":"signal","data":"SIGTERM"}` / `{"type":"close"}`.
  - Servidor → cliente: JSON `{"type":"output","data":"..."}` y `{"type":"exit","code":N}` al terminar.
  - Cada conexión abre su propia sesión (concurrencia segura) y el proceso se cierra limpiamente al desconectar.

> La terminal interactiva con semántica de tty completa (p. ej. `Ctrl+C` a un proceso en primer plano, UIs curses)
> la proporciona el puente `node-pty` del frontend Electron; `/ws/terminal` es un transporte de streaming robusto.

> **Dependencias:** requiere `python-dotenv` (carga el `.env` al arrancar). El soporte WebSocket lo aporta
> `uvicorn[standard]`. Instala todo con `pip install -r requirements.txt`.

---

## 🧪 PRUEBAS AUTOMATIZADAS (CI/CD)

El backend cuenta con una suite completa de más de 300 tests automatizados (unitarios, integración y smoke tests):

```bash
pytest
```
*Suite amplia de tests unitarios, de integración y smoke. Los tests de integración de WSL se
omiten automáticamente (`skipif`) si `wsl.exe` no está disponible en el host (p. ej. runners de CI Linux).*
