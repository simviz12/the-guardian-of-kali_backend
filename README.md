# 🛡️ The Guardian of Kaliche

> **Una aplicación única para cada operador:** *The Guardian of Kaliche* no es un entorno genérico. Está diseñado para que **al momento de instalarse se ajuste automáticamente a tus componentes locales**. La aplicación se apropia de tu propio subsistema de Kali Linux, gestiona tu propia clave API de Inteligencia Artificial (Gemini) en un entorno seguro y genera una base de datos local cifrada y exclusiva para tu auditoría. **Tu entorno, tus reglas.**

**The Guardian of Kaliche** es un Copiloto de Seguridad Ofensiva y Defensiva estructurado bajo un estricto modelo de **Clean Architecture** e impulsado por Inteligencia Artificial (Gemini 2.5). Se integra bidireccionalmente y en tiempo real con tu entorno nativo de **Kali Linux WSL2**.

## 🚀 Instalación en 1 Solo Paso (Automática)

Para tener el sistema instalado "con todo y base de datos" en una carpeta nueva, simplemente abre la aplicación de **Windows PowerShell**, pega el siguiente bloque de código completo y presiona `Enter`. 

Este script descargará el sistema, configurará los entornos, instalará las dependencias y arrancará la aplicación de escritorio nativa:

```powershell
# 1. Crear carpeta maestra e ingresar
mkdir TheGuardianOfKaliche; cd TheGuardianOfKaliche

# 2. Descargar Repositorios de Clean Architecture (Frontend y Backend)
git clone https://github.com/simviz12/the-guardian-of-kali_backend.git
git clone https://github.com/simviz12/the-guardian-of-kali_frontend.git

# 3. Crear script de Auto-Ejecución (Iniciar_Guardian.bat)
$BatContent = @"
@echo off
cd /d "%~dp0"
taskkill /IM python.exe /F 2>nul
cd the-guardian-of-kali_backend
if not exist ".venv" ( python -m venv .venv )
call .venv\Scripts\activate.bat
pip install -r requirements.txt >nul 2>&1
start /B python -m src.main >nul 2>&1
cd ..\the-guardian-of-kali_frontend
if not exist "node_modules" ( call npm install >nul 2>&1 )
if not exist "dist" ( call npm run build >nul 2>&1 )
start /B npm run start >nul 2>&1
exit
"@
Set-Content -Path "Iniciar_Guardian.bat" -Value $BatContent

# 4. Iniciar la aplicación
.\Iniciar_Guardian.bat
```

> **NOTA:** Una vez ejecutado este bloque, el proyecto estará instalado. Para abrirlo todos los días en el futuro, **simplemente entra a la carpeta `TheGuardianOfKaliche` y haz doble clic en `Iniciar_Guardian.bat`**. ¡La aplicación se levantará sola en 3 segundos!

## 🏗️ Arquitectura del Sistema (Clean Architecture)
*   **Idioma:** Interfaz visual (UI) 100% en español. Arquitectura, variables, repositorios y funciones 100% en inglés.
*   **Backend (Python/FastAPI):**
    *   `src/core/entities` (Entidades centrales).
    *   `src/core/usecases` (Lógica Pura y Motor Zero-Trust).
    *   `src/adapters` (WSL PTY, Base de datos SQLite, IA de Gemini).
*   **Frontend (React/Electron):** Distribuido en `src/components`, `src/services` y `src/types` para total abstracción.

## ✨ Características Principales
*   **Terminal Permanente Root:** Tu sesión de PTY arranca como `root` en Kali Linux. Tus comandos en curso no se borran al cambiar de pestañas en la interfaz.
*   **Auditoría Integral:** Cada comando manual o asistido se guarda en `the_guardian_of_kali.db`.
*   **Copiloto Integrado:** Un módulo Zero-Trust de IA que analiza todo lo que escupe tu consola para enseñarte cómo vulnerar o asegurar el objetivo.
