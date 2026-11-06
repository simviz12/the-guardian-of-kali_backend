# The Guardian of Kaliche - Backend
> Motor de Inteligencia Artificial y auditoría Zero-Trust para **The Guardian of Kaliche**, construido sobre Python, FastAPI y SQLite.

---

## ⚡ INSTALACIÓN Y ARRANQUE EN 1 CLIC (`setup_and_run.bat`)

> **No instales este backend por separado.** La forma recomendada de instalar **y** ejecutar
> todo el ecosistema (frontend + backend) es un único script: **`setup_and_run.bat`**, que vive
> en el repositorio del **frontend**.

Descarga solo ese `.bat` en una carpeta vacía y haz **doble clic** — él se encarga de todo:

* 📥 **Clona ambos repos** (frontend + backend) desde GitHub.
* 🛠️ Instala **Git, Node.js y Python** si faltan (vía `winget`), crea el `.venv`, instala
  `requirements.txt` y las dependencias de Node, y compila la app de escritorio.
* 🚀 Arranca el backend FastAPI, espera a que `/health` responda y **abre la aplicación**.

👉 **Enlace directo del instalador:**
`https://raw.githubusercontent.com/simviz12/the-guardian-of-kali_frontend/main/setup_and_run.bat`

📖 **Guía paso a paso (incluye WSL2 + Kali):**
[INSTALACION.md](https://github.com/simviz12/the-guardian-of-kali_frontend/blob/main/INSTALACION.md)

> Requisito previo manual (una sola vez, necesita admin + reinicio):
> `wsl --install -d kali-linux`. El `.bat` avisa si falta WSL.

> _Scripts heredados: `Instalar_Guardian.bat` (solo instala) e `Iniciar_Guardian.bat` (solo lanza).
> `setup_and_run.bat` los reemplaza haciendo ambas cosas en un paso._

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
