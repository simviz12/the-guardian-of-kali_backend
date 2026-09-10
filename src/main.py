"""FastAPI application entrypoint for The Guardian of Kali backend service."""
from typing import Dict, Any
import uvicorn
from fastapi import FastAPI, Depends, status
from fastapi.middleware.cors import CORSMiddleware

from src.application.use_cases.execute_command import ExecuteCommandUseCase
from src.application.use_cases.evaluate_policy import EvaluatePolicyUseCase
from src.application.use_cases.chat_with_ai import ChatWithAIUseCase
from src.dependencies import (
    get_execute_command_use_case,
    get_evaluate_policy_use_case,
    get_chat_with_ai_use_case,
)


def create_app() -> FastAPI:
    """Creates and configures the FastAPI application instance.

    Configures CORS restricted to local Electron origins and mounts health check
    and dependency injection endpoints.

    Returns:
        FastAPI: The configured application instance.
    """
    app = FastAPI(
        title="The Guardian of Kali - Backend API",
        description="Backend API and Policy Engine co-pilot for Kali Linux WSL2",
        version="0.1.0",
    )

    # CORS configuration restricted strictly to local Electron origins
    allowed_origins = [
        "http://localhost:5173",  # Vite dev server default
        "http://127.0.0.1:5173",
        "app://-",                # Electron production custom protocol
        "file://",                # Electron local file rendering
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.get("/health", status_code=status.HTTP_200_OK, tags=["Health"])
    async def health_check() -> Dict[str, Any]:
        """Performs a service health check."""
        return {
            "status": "healthy",
            "service": "the-guardian-of-kali-backend",
            "version": "0.1.0",
        }

    @app.get("/api/di-check", status_code=status.HTTP_200_OK, tags=["Diagnostic"])
    async def di_check(
        execute_use_case: ExecuteCommandUseCase = Depends(get_execute_command_use_case),
        evaluate_use_case: EvaluatePolicyUseCase = Depends(get_evaluate_policy_use_case),
        chat_use_case: ChatWithAIUseCase = Depends(get_chat_with_ai_use_case),
    ) -> Dict[str, str]:
        """Diagnostic route verifying dependency injection of application use cases."""
        return {
            "execute_use_case": execute_use_case.__class__.__name__,
            "evaluate_use_case": evaluate_use_case.__class__.__name__,
            "chat_use_case": chat_use_case.__class__.__name__,
        }

    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host="127.0.0.1",
        port=8765,
        reload=False,
    )
