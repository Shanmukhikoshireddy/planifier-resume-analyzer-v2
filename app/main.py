import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config.logging import logger
from app.config.settings import settings


class StripRootPathMiddleware:
    """Nginx often forwards /v1.0/planifier/cv-analysis/... without stripping it.

    FastAPI routes live at /api/... and /ws/cv-service. Strip the public prefix
    for both HTTP and WebSocket so those routes match.
    """

    def __init__(self, app, prefix: str):
        self.app = app
        self.prefix = (prefix or "").rstrip("/")

    async def __call__(self, scope, receive, send):
        if self.prefix and scope["type"] in ("http", "websocket"):
            path = scope.get("path") or ""
            if path == self.prefix or path.startswith(self.prefix + "/"):
                scope = dict(scope)
                scope["path"] = path[len(self.prefix):] or "/"
                raw_path = scope.get("raw_path")
                if isinstance(raw_path, (bytes, bytearray)):
                    prefix_bytes = self.prefix.encode("ascii")
                    if raw_path.startswith(prefix_bytes):
                        stripped = raw_path[len(prefix_bytes):]
                        scope["raw_path"] = stripped or b"/"
                root_path = scope.get("root_path") or ""
                if not root_path.endswith(self.prefix):
                    scope["root_path"] = f"{root_path}{self.prefix}"
        await self.app(scope, receive, send)
# API Routers
from app.services.resume.scheduler_runner import start_scheduler
from app.services.websocket.connection_manager import connection_manager
from app.api.health import router as health_router
from app.api.search import router as search_router
from app.api.shortlist import router as shortlist_router
from app.api.resume import router as resume_router
from app.api.websocket import router as websocket_router


# Application Startup / Shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("APPLICATION STARTING")

    connection_manager.attach_loop(asyncio.get_running_loop())

    # Start Resume Scheduler
    start_scheduler()
    logger.info(
        "Resume Scheduler Initialized."
    )
    yield
    logger.info("APPLICATION SHUTDOWN")


# FastAPI Application
# root_path makes Swagger/OpenAPI URLs correct behind
# https://api.edpedia.co/v1.0/planifier/cv-analysis
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    root_path=settings.ROOT_PATH,
    servers=[
        {
            "url": settings.ROOT_PATH or "/",
            "description": "Production (api.edpedia.co)",
        },
        {
            "url": "/",
            "description": "Direct (IP / local)",
        },
    ],
)

# CORS — required for browser calls from Planifier / Edpedia frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Routers
app.include_router(
    health_router,
)



app.include_router(search_router,)
app.include_router(shortlist_router,)
app.include_router(resume_router,)
app.include_router(websocket_router,)


# Root Endpoint
@app.get(
    "/",
    tags=["Home"],
)
def home():
    return {
        "application": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "architecture": "Resume Scheduler Based",
        "status": "Running",
        "docs": "/docs",
        "redoc": "/redoc",
        "websocket": "/ws/cv-service",
        "root_path": settings.ROOT_PATH,
    }


if settings.ROOT_PATH:
    app = StripRootPathMiddleware(app, settings.ROOT_PATH)
 