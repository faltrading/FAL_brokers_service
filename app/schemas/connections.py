import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class BrokerProvider(str, Enum):
    FTMO = "ftmo"
    FINTOKEI = "fintokei"
    TOPSTEP = "topstep"
    TRADEIFY = "tradeify"
    LUCIDTRADING = "lucidtrading"


class ConnectionCreate(BaseModel):
    provider: BrokerProvider
    account_identifier: str = Field(min_length=1, max_length=255)
    credentials: dict = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)


class ConnectionUpdate(BaseModel):
    account_identifier: str | None = Field(default=None, min_length=1, max_length=255)
    credentials: dict | None = None
    connection_status: str | None = None
    metadata: dict | None = None


class ConnectionResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    provider: str
    account_identifier: str
    connection_status: str
    last_sync_at: datetime | None = None
    last_sync_status: str | None = None
    metadata: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class ConnectionListResponse(BaseModel):
    connections: list[ConnectionResponse]
    total: int
