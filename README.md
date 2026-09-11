# The Guardian of Kali — Backend y Motor de Políticas (`the-guardian-of-kali_backend`)

Servicio de backend, orquestador de ejecución y motor de políticas de seguridad para **The Guardian of Kali**, un entorno de terminal asistido por inteligencia artificial diseñado para la práctica de hacking ético (CTFs, HackTheBox, TryHackMe y laboratorios locales) ejecutado nativamente sobre Kali Linux en WSL2.

---

## Arquitectura de Software

Este proyecto está estrictamente estructurado siguiendo los principios de **Clean Architecture** organizados en cuatro capas:

- **Dominio (`src/domain/`)**: Entidades puras, objetos de valor (`RiskLevel`, `PolicyAction`, `CommandOrigin`), reglas de negocio y excepciones de dominio sin dependencias externas.
- **Aplicación (`src/application/`)**: Casos de uso (`ExecuteCommandUseCase`, `EvaluatePolicyUseCase`, `ChatWithAIUseCase`, `GetSessionHistoryUseCase`) e interfaces abstractas de puertos (`ShellExecutor`, `AIGateway`, `SessionRepository`).
- **Adaptadores (`src/adapters/`)**: Implementaciones concretas de la infraestructura (cliente oficial de Anthropic Claude con backoff exponencial, ejecutor de comandos WSL2, repositorio SQLite).
- **Infraestructura (`src/infrastructure/`)**: Configuración de servicios web, rutas y esquemas de validación estricta con FastAPI y Pydantic.

Las dependencias de código siempre apuntan hacia el interior, salvaguardando la pureza del Dominio.

---

## Modelo de Seguridad

El backend interactúa con Kali Linux sobre WSL2 mediante dos cuentas de usuario independientes a nivel del sistema operativo:
1. **Usuario Operador (`carlos`)**: Cuenta interactiva para operaciones manuales del usuario.
2. **Usuario Restringido de IA (`ia-user`)**: Cuenta de mínima exposición sin permisos de `sudo`, impidiendo escalada de privilegios por parte de la IA.

Cada comando propuesto por la IA pasa obligatoriamente por el **Policy Engine** (filtro de lista negra destructiva, clasificación de riesgo y verificación de objetivos autorizados) antes de alcanzar el ejecutor de terminal. Este filtro no puede ser eludido desde ningún endpoint.

---

## Stack Tecnológico

- **Lenguaje**: Python 3.11+
- **Framework API**: FastAPI + Uvicorn
- **Integración con IA**: Anthropic Claude API (`claude-3-5-sonnet`) mediante Tool Use / Function Calling estructurado
- **Base de Datos de Auditoría**: SQLite asíncrono con consultas parametrizadas
- **Entorno de Ejecución**: WSL2 nativo (distribución `kali-linux`)
- **Calidad y Testing**: Pytest (283 pruebas unitarias y adversariales pasando al 100%), Ruff, Mypy

---

## Instalación y Ejecución

```bash
# 1. Clonar el repositorio
git clone https://github.com/simviz12/the-guardian-of-kali_backend.git
cd the-guardian-of-kali_backend

# 2. Crear y activar entorno virtual
python -m venv venv
venv\Scripts\activate  # En Linux/WSL: source venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar clave de Anthropic (opcional para desarrollo offline)
set ANTHROPIC_API_KEY=tu_api_key_aqui

# 5. Iniciar servidor FastAPI
python -m src.main
```

---

## Licencia

Este proyecto está licenciado bajo la Licencia MIT. Consulta el archivo [LICENSE](LICENSE) para más detalles.

