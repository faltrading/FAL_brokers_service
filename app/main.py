import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)

from app.api import admin, broker_data, connections, health
from app.db.session import engine
from app.services.gateway_client import close_gateway_client

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=== BROKER SERVICE STARTUP BEGIN ===")
    logger.info("Broker data aggregation service ready")
    logger.info("=== BROKER SERVICE STARTUP COMPLETE ===")

    yield

    await close_gateway_client()
    await engine.dispose()


app = FastAPI(
    title="Broker Data Aggregation - Microservizio",
    description="Microservizio per la raccolta e aggregazione dati di trading da broker/prop firm esterni",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(connections.router)
app.include_router(broker_data.router)
app.include_router(admin.router)
