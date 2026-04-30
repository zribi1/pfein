from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import mongo_db

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/db")
async def health_db(db: AsyncIOMotorDatabase = Depends(mongo_db)) -> dict[str, str]:
    await db.client.admin.command("ping")
    return {"status": "ok", "db": db.name}
