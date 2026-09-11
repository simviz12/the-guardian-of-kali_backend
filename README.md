# The Guardian of Kali — Backend y Motor de Políticas (`the-guardian-of-kali_backend`)

Servicio de backend, orquestador de terminal y motor de políticas de seguridad para **The Guardian of Kali**, un entorno de terminal asistido por inteligencia artificial diseñado para la práctica de hacking ético (CTFs, HackTheBox, TryHackMe y laboratorios locales) ejecutado nativamente sobre **Kali Linux en WSL2**.

---

## 🏛️ Arquitectura de Software

Este backend está estrictamente estructurado siguiendo los principios de **Clean Architecture** (Arquitectura Limpia) con el flujo de dependencias siempre apuntando hacia el interior:

```
src/
├── domain/                    # Entidades puras y reglas de seguridad
│   ├── entities/              # Command, Session, Target, PolicyRule
│   ├── value_objects/         # RiskLevel, PolicyAction, CommandOrigin, PolicyDecision
│   ├── policies/              # Policy rules, Blacklist regex, Validator, Risk Classifier
│   └── exceptions.py          # Excepciones de dominio
├── application/               # Casos de uso y orquestación
│   ├── use_cases/             # ExecuteCommandUseCase, EvaluatePolicyUseCase, ChatWithAIUseCase, GetSessionHistoryUseCase
│   ├── ports/                 # ShellExecutor, AIGateway, SessionRepository
│   └── dtos/                  # Data Transfer Objects (CommandResult, AIResponse, ChatResult)
├── adapters/                  # Implementaciones tecnológicas
│   ├── terminal/              # WSLShellExecutor (wsl.exe -d kali-linux -u ia-user)
│   ├── storage/               # SQLiteSessionRepository (the_guardian_of_kali.db)
│   └── ai/                    # ClaudeAIGateway (Anthropic Python SDK con backoff exponencial)
└── infrastructure/            # Entrega HTTP y configuración
    ├── api/                   # FastAPI schemas (Pydantic con extra="forbid")
    └── config/                # System prompts y ajustes del sistema
```

---

## 🛡️ Modelo de Seguridad y Defensa en Profundidad

El sistema implementa una arquitectura defensiva estricta para garantizar que la asistencia de IA nunca comprometa el entorno anfitrión ni el sistema operativo Kali Linux:

1. **Aislamiento por Usuarios en Linux**:
   - **Usuario Operador (`carlos`)**: Cuenta con privilegios regulares para interacción directa en la terminal interactiva.
   - **Usuario Restringido de IA (`ia-user`)**: Cuenta con permisos estrictamente limitados donde se ejecutan los comandos propuestos por la IA.
2. **Whitelist de Sudoers & Prevención de GTFOBins**:
   - Solo se permite ejecutar comandos específicos autorizados (`/usr/bin/ping`, `/usr/bin/nmap`, `/usr/sbin/traceroute`) vía `sudo -n`.
   - **Protección contra scripts de Nmap**: El motor de políticas bloquea activamente banderas como `--script` o `--interactive` con `sudo` para impedir la ejecución de código arbitrario como root.
3. **Compuerta Obligatoria de Políticas (`EvaluatePolicyUseCase`)**:
   - Ningún comando sugerido por la IA puede alcanzar el ejecutor de terminal sin pasar por la evaluación de políticas.
   - Si el comando viola listas negras destructivas (`rm -rf /`, `mkfs`, `fdisk`, `reboot`, `iptables -F`, etc.) o tiene como objetivo una IP/dominio fuera del alcance autorizado, el sistema responde con `HTTP 403 Forbidden` y el ejecutor jamás invoca el subproceso.
4. **Registro de Auditoría Forense**:
   - Toda orden ejecutada se registra en SQLite (`commands` y `policy_logs`), incluyendo origen (`AI` vs `MANUAL_USER`), nivel de riesgo, resultado, tiempo de ejecución y justificación.

---

## 🚀 Stack Tecnológico

- **Lenguaje**: Python 3.11+
- **API Framework**: FastAPI + Uvicorn
- **Integración IA**: Anthropic Claude API (`claude-3-5-sonnet-20241022`) vía Tool Calling estructurado
- **Persistencia**: SQLite asíncrono en hilo desacoplado (`asyncio.to_thread`)
- **Ejecución WSL**: `wsl.exe` nativo con timeouts estrictos (30s) y captura de salida
- **Validación**: Pydantic v2
- **Testing**: Pytest (296 pruebas unitarias, de integración y adversariales con 100% de éxito)

---

## 📋 Endpoints de la API REST

| Método | Ruta | Descripción |
| :--- | :--- | :--- |
| `GET` | `/health` | Chequeo de estado del servicio y versión. |
| `POST` | `/execute` | Ejecuta un comando en WSL2 aplicando la compuerta de políticas de seguridad. |
| `POST` | `/chat` | Conversación con Claude AI y generación de propuestas estructuradas de comandos. |
| `GET` | `/history` | Consulta el historial auditado con filtros por sesión, usuario, fecha o nivel de riesgo. |
| `GET` | `/api/di-check` | Endpoint de diagnóstico de inyección de dependencias. |

---

## ⚙️ Requisitos Previos e Instalación

### Requisitos
- Windows 10/11 con **WSL2** instalado.
- Distribución **Kali Linux** (`wsl --install -d kali-linux`).
- Usuario `ia-user` configurado en Kali Linux.
- Python 3.11 o superior.

### Instalación Rápida

```bash
# 1. Clonar el repositorio
git clone https://github.com/simviz12/the-guardian-of-kali_backend.git
cd the-guardian-of-kali_backend

# 2. Crear y activar el entorno virtual
python -m venv .venv
.\.venv\Scripts\activate   # En Linux/WSL: source .venv/bin/activate

# 3. Instalar dependencias
pip install --upgrade pip
pip install -r requirements.txt

# 4. Configurar variables de entorno
copy .env.example .env
# Editar .env e introducir tu clave de Anthropic (opcional para ejecución offline / mocks)

# 5. Ejecutar la suite de pruebas
pytest -v

# 6. Iniciar el backend
python -m src.main
```

El servidor estará escuchando en `http://127.0.0.1:8765`.

---

## 🧪 Pruebas Automatizadas

El proyecto cuenta con una cobertura integral de pruebas unitarias, de integración y adversariales:

```bash
# Ejecutar todas las pruebas (296 tests)
pytest

# Ejecutar pruebas adversariales de seguridad
pytest tests/unit/domain/test_policy_engine_security_audit.py

# Ejecutar pruebas end-to-end con WSL2 real
pytest tests/integration/test_full_e2e_flow.py
```

---

## 📄 Licencia

Este proyecto se encuentra bajo la Licencia MIT. Consulta el archivo [LICENSE](LICENSE) para más detalles.
