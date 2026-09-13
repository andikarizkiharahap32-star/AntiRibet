"""
AutoAccount Creator (AAC) - Main Application Entry Point
FastAPI backend for automated Discord and Gmail account creation
"""
from contextlib import asynccontextmanager
import logging
import time

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, make_asgi_app
from sqlalchemy import text

from app.api.v1 import accounts, auth, jobs, proxies, stats, websocket
from app.core.config import settings
from app.core.database import Base, engine

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Prometheus metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)
http_request_duration = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration",
    ["method", "endpoint"],
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    logger.info("Starting AAC Application...")

    # Create database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database tables created/verified")
    logger.info(f"Celery workers configured: {settings.MIN_WORKERS}-{settings.MAX_WORKERS}")

    yield

    logger.info("Shutting down AAC Application...")
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Automated Discord and Gmail account creator with enterprise features",
    docs_url=f"{settings.API_V1_PREFIX}/docs",
    redoc_url=f"{settings.API_V1_PREFIX}/redoc",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    lifespan=lifespan,
)

# CORS middleware (CLI-first defaults from settings)
cors_origins = settings.cors_allow_origins
allow_credentials = cors_origins != ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gzip middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)

    http_requests_total.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code,
    ).inc()
    http_request_duration.labels(
        method=request.method,
        endpoint=request.url.path,
    ).observe(process_time)

    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors(), "body": exc.body},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


@app.get("/health")
async def health_check():
    """Basic health check"""
    return {"status": "healthy", "version": settings.APP_VERSION}


@app.get("/health/ready")
async def readiness_check():
    """Readiness check for orchestrators"""
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ready", "database": "connected"}
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not ready", "database": "disconnected"},
        )


app.include_router(auth.router, prefix=f"{settings.API_V1_PREFIX}/auth", tags=["Authentication"])
app.include_router(jobs.router, prefix=f"{settings.API_V1_PREFIX}/jobs", tags=["Jobs"])
app.include_router(accounts.router, prefix=f"{settings.API_V1_PREFIX}/accounts", tags=["Accounts"])
app.include_router(proxies.router, prefix=f"{settings.API_V1_PREFIX}/proxies", tags=["Proxies"])
app.include_router(stats.router, prefix=f"{settings.API_V1_PREFIX}/stats", tags=["Statistics"])
app.include_router(websocket.router, prefix="/ws", tags=["WebSocket"])

if settings.PROMETHEUS_ENABLED:
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "application": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": f"{settings.API_V1_PREFIX}/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        workers=settings.WORKERS,
        reload=settings.DEBUG,
    )
