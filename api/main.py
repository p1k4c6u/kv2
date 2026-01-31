# main.py
"""
FastAPI application for KV Listings Dashboard.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routes import auth, listings, analyze, scrape

# Initialize settings
settings = get_settings()

# Create FastAPI app
app = FastAPI(
    title="KV Listings API",
    description="API for Estonian real estate listings with AI analysis",
    version="1.0.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api")
app.include_router(listings.router, prefix="/api")
app.include_router(analyze.router, prefix="/api")
app.include_router(scrape.router, prefix="/api")


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "KV Listings API",
        "version": "1.0.0",
    }


@app.get("/api/health")
async def health():
    """Detailed health check."""
    return {
        "status": "healthy",
        "database": bool(settings.DATABASE_URL),
        "openrouter": bool(settings.OPENROUTER_API_KEY),
    }


# Initialize database on startup
@app.on_event("startup")
async def startup():
    """Initialize database tables on startup."""
    import sys
    from pathlib import Path

    # Add kv module to path
    sys.path.insert(0, str(Path(__file__).parent.parent / "kv"))

    try:
        from db import init_db

        init_db()
        print("Database initialized successfully")
    except Exception as e:
        print(f"Warning: Could not initialize database: {e}")
