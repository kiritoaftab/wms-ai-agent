"""
WMS AI Agent — FastAPI Application
Natural language query interface for the WMS database.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import query, threads
from app.models.schemas import HealthResponse
from app.services.query_executor import QueryExecutor


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="WMS AI Agent",
        description="Natural language query interface for the Warehouse Management System",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS for React frontend
    # Browsers disallow allow_credentials=True with wildcard origins
    cors_origins = settings.cors_origin_list
    allow_credentials = "*" not in cors_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    app.include_router(query.router)
    app.include_router(threads.router)

    # Health check
    @app.get("/health", response_model=HealthResponse)
    async def health_check():
        db_ok = QueryExecutor().test_connection()
        azure_ok = bool(settings.azure_openai_api_key and settings.azure_openai_endpoint)
        return HealthResponse(
            status="healthy" if (db_ok and azure_ok) else "degraded",
            db_connected=db_ok,
            azure_configured=azure_ok,
        )

    @app.get("/")
    async def root():
        return {
            "service": "WMS AI Agent",
            "version": "1.0.0",
            "docs": "/docs",
        }

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.app_port,
        reload=settings.app_env == "development",
    )
