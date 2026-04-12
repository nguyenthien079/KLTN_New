from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, Base
from app.routers import crawler, pipeline, ner, admin, feedback, auth, users, labeling, role_requests


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Starting Medical NER API...")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print("Database ready")
    yield

    # Shutdown
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(crawler.router, prefix="/api/crawl", tags=["Crawler"])
app.include_router(pipeline.router, prefix="/api/pipeline", tags=["Pipeline"])
app.include_router(ner.router, prefix="/api/ner", tags=["NER"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
app.include_router(feedback.router, prefix="/api/feedback", tags=["Feedback"])
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(labeling.router, prefix="/api/labeling", tags=["Labeling"])
app.include_router(role_requests.router, prefix="/api/role-requests", tags=["RoleRequests"])


@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
