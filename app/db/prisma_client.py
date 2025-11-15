from typing import Optional
from prisma import Prisma

class PrismaClient:
    _instance: Optional[Prisma] = None

    @staticmethod
    async def get_instance() -> Prisma:
        if PrismaClient._instance is None:
            PrismaClient._instance = Prisma()
            await PrismaClient._instance.connect()
        return PrismaClient._instance

    @staticmethod
    async def close_connection() -> None:
        if PrismaClient._instance is not None:
            await PrismaClient._instance.disconnect()
            PrismaClient._instance = None

async def get_prisma():
    """Get Prisma client instance"""
    client = await PrismaClient.get_instance()
    return client