from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db import init_db
from app.sandbox import _is_docker_available


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure SQLite tables and indexes exist on boot
    init_db()
    yield


app = FastAPI(
    title="Self-Improving Code Agent API",
    description="Backend API powering the sandboxed, self-repairing code generation agent.",
    version="1.0.0",
    lifespan=lifespan,
)

# Allow React dev server and local clients to call endpoints without CORS blocks
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["System"])
def health_check():
    return {
        "status": "healthy",
        "version": "1.0.0",
        "docker_available": _is_docker_available(),
    }
