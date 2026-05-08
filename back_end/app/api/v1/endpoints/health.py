from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import mongo_db

router = APIRouter()


@router.get(
    "/health",
    summary="Check API health",
    description=(
        "Returns a lightweight `ok` response when the FastAPI application is running. "
        "Use this for container health checks or quick connectivity tests."
    ),
    response_description="API process health status.",
)
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get(
    "/health/db",
    summary="Check API and MongoDB health",
    description=(
        "Pings MongoDB through the configured connection and returns the active database name. "
        "Use this when the API is up but data endpoints seem unavailable."
    ),
    response_description="API and MongoDB connectivity status.",
)
async def health_db(db: AsyncIOMotorDatabase = Depends(mongo_db)) -> dict[str, str]:
    await db.client.admin.command("ping")
    return {"status": "ok", "db": db.name}
