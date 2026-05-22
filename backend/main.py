import logging
import sys

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from routers import ask, briefings, logs, meetings
from runtime_config import validate_runtime_config

# ── Logging configuration ────────────────────────────────────────────
# Use explicit handler on "pharmaops" namespace so uvicorn can't override it
_handler = logging.StreamHandler(sys.stderr)
_handler.setFormatter(
    logging.Formatter(
        fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
)
_pharma_logger = logging.getLogger("pharmaops")
_pharma_logger.setLevel(logging.DEBUG)
_pharma_logger.addHandler(_handler)
_pharma_logger.propagate = False

logger = logging.getLogger("pharmaops.main")

app = FastAPI(title="PharmaOps API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
        "https://your-frontend-domain.com",
    ],
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1):\d+$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, dict) else {}
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "code": detail.get("code", "HTTP_ERROR"),
            "message": detail.get("message", str(exc.detail)),
        },
    )


@app.exception_handler(Exception)
async def exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Unhandled exception on %s %s: %s",
        request.method,
        request.url.path,
        exc,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "code": "INTERNAL_ERROR",
            "message": str(exc),
        },
    )


app.include_router(meetings.router, prefix="/meetings", tags=["meetings"])
app.include_router(meetings.singular_router, prefix="/meeting", tags=["meetings"])
app.include_router(briefings.router, prefix="/meeting", tags=["briefing"])
app.include_router(ask.router, prefix="/ask", tags=["ask"])
app.include_router(logs.router, prefix="/ws", tags=["logs"])


@app.on_event("startup")
async def startup_checks() -> None:
    logger.info("Starting PharmaOps API — running config validation")
    validate_runtime_config()
    logger.info("PharmaOps API startup complete")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "pharmaops-api"}
