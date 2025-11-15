import logging, os
from logging.handlers import TimedRotatingFileHandler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.db.prisma_client import PrismaClient
from app.redis.redis_client import redis_handler
from app.api.v1.user.auth.routes.user import router as user_auth_router
from app.api.v1.user.auth.routes.google_auth import router as google_auth_router
from app.api.v1.user.info.routes import router as user_info_router
from app.api.v1.evaluation.routes import router as evaluation_router
from env import env


# Configure logging

LOG_DIR = env.LOG_DIR
LOG_PATH = os.path.join(LOG_DIR, "app.log")
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(message)s"

os.makedirs(LOG_DIR, exist_ok=True)

file_handler = TimedRotatingFileHandler(
    LOG_PATH,
    when='midnight',
    interval=1,
    backupCount=7,
    encoding='utf-8'
)

file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
file_handler.setLevel(logging.INFO)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(logging.Formatter(LOG_FORMAT))
stream_handler.setLevel(logging.INFO)

logging.basicConfig(
    level=logging.INFO,
    handlers=[file_handler, stream_handler]
)

logger = logging.getLogger(__name__)

for logger_name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
    uvicorn_logger = logging.getLogger(logger_name)
    uvicorn_logger.addHandler(file_handler)
    uvicorn_logger.setLevel(logging.INFO)
    uvicorn_logger.propagate = False

logger.info("Logging is set up correctly.")


# Initialize FastAPI application and include routers

@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("Starting Prisma client")
    await PrismaClient.get_instance()

    logger.info("Starting Redis client")
    client = await redis_handler.get_client()

    logger.info("Flushing Redis database")
    await client.flushdb()

    yield

    logger.info("Shutting down Prisma client")
    await PrismaClient.close_connection()

    logger.info("Shutting down Redis client")
    await redis_handler.disconnect()

app = FastAPI(
    title="SmartGrader Backend",
    description="API for managing all operations",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://smartgrader.online", "http://127.0.0.1:5500"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(user_auth_router, prefix="/api/v1", tags=["User Auth"])
app.include_router(google_auth_router, prefix="/api/v1", tags=["Google Auth"])
app.include_router(user_info_router, prefix="/api/v1", tags=["User Info"])

app.include_router(evaluation_router, prefix="/api/v1", tags=["Evaluation"])

@app.get("/")
async def root():
    logger.info("Root endpoint accessed")
    return {"message": "Welcome to the API"}
