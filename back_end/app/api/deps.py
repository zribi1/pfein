from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.mongodb import get_db


def mongo_db() -> AsyncIOMotorDatabase:
    return get_db()
