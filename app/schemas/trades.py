import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class TradeResponse(BaseModel):
    id: uuid.UUID
    connection_id: uuid.UUID
    provider: str
    external_trade_id: str | None = None
    symbol: str
    side: str
    open_time: datetime
    close_time: datetime | None = None
    open_price: float
    close_price: float | None = None
    volume: float
    pnl: float | None = None
    commission: float = 0
    swap: float = 0
    status: str
    metadata: dict = Field(default_factory=dict)
    created_at: datetime


class TradeListResponse(BaseModel):
    trades: list[TradeResponse]
    total: int
    has_more: bool = False


class DailyStatResponse(BaseModel):
    id: uuid.UUID
    connection_id: uuid.UUID
    provider: str
    date: str
    total_pnl: float
    trade_count: int
    winning_trades: int
    losing_trades: int
    volume: float
    metadata: dict = Field(default_factory=dict)


class DailyStatListResponse(BaseModel):
    stats: list[DailyStatResponse]
    total: int
