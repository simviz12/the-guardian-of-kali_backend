# The Guardian of Kaliche - Backend

Motor de Inteligencia Artificial y auditoría Zero-Trust para **The Guardian of Kaliche**, construido sobre Python, FastAPI y SQLite.

## Arquitectura del Sistema (Clean Architecture)

Este backend ha sido diseñado siguiendo estrictamente los principios de **Clean Architecture** para garantizar que el código sea testeable, mantenible y totalmente independiente de las herramientas externas (bases de datos, APIs de terceros o frameworks web). 

La distribución de carpetas está estructurada en 4 capas concéntricas:

```text
the-guardian-of-kali_backend/
├── src/
│   ├── domain/               # Capa 1: Entidades del Negocio (Independiente)
│   │   ├── entities/         # Modelos puros (command.py, session.py, chat_message.py)
│   │   └── value_objects/    # Enums y constantes (RiskLevel, CommandOrigin)
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
│       ├── config/           # Configuraciones y Prompts del Sistema (settings.py, system_prompt.py)
│       ├── dependencies.py   # Inyección de Dependencias
│       └── main.py           # Endpoints HTTP FastAPI (Controladores REST)
```

### Flujo de Trabajo (Zero-Trust Flow)
1. **Frontend (Capa Externa)** hace una petición REST (`/execute`, `/history/log`, `/chat`).
2. **Infrastructure (`main.py`)** recibe la petición y delega a un **Use Case** inyectando los adaptadores correspondientes.
3. El **Use Case** ejecuta la lógica del negocio utilizando las **Entidades del Dominio** puras y llama a los **Ports** (Interfaces abstractas).
4. Los **Adaptadores** (ej. `SQLiteSessionRepository` o `GeminiAIGateway`) implementan los Ports y realizan el trabajo sucio de E/S.

## Instalación y Ejecución

*Nota: Es recomendable utilizar el archivo `Iniciar_Guardian.bat` que automatiza todo el proceso de compilación del Frontend y Backend simultáneamente.*

Para iniciarlo manualmente:
```bash
# 1. Crear entorno virtual
python -m venv .venv

# 2. Activar entorno
.venv\Scripts\activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Iniciar servidor FastAPI
python -m src.main
```

## Características Clave
* **Auditoría Inmutable:** Registro automatizado de cada comando ejecutado en SQLite (`the_guardian_of_kali.db`).
* **Copiloto Hacking IA:** Integración nativa con `gemini-2.5-flash` para sugerencias y resoluciones.
* **Trazabilidad Absoluta:** Identificación del origen del comando (`MANUAL_USER` vs `AI`).
