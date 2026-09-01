
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config.logging import logger
from app.config.settings import settings
# API Routers
from app.services.resume.scheduler_runner import start_scheduler
from app.api.health import router as health_router
from app.api.search import router as search_router
from app.api.shortlist import router as shortlist_router
from app.api.resume import router as resume_router


# Application Startup / Shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("APPLICATION STARTING")

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
        "root_path": settings.ROOT_PATH,
    }
 