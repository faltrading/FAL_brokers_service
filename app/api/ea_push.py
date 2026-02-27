import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.broker_connection import BrokerConnection
from app.models.broker_trade import BrokerTrade
from app.services.stats_service import recalculate_daily_stats

router = APIRouter(prefix="/api/v1/broker/ea", tags=["broker-ea"])
logger = logging.getLogger(__name__)


class EATradePush(BaseModel):
    token: str
    ticket: int
    symbol: str
    type: str          # "buy" or "sell"
    lots: float
    open_price: float
    close_price: float
    open_time: str
    close_time: str
    profit: float
    commission: float = 0.0
    swap: float = 0.0
    magic: int = 0
    comment: str = ""


_DATE_FORMATS = [
    "%Y.%m.%d %H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y/%m/%d %H:%M:%S",
]


def _parse_dt(value: str) -> datetime | None:
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value.strip(), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


@router.post("/push", status_code=200)
async def ea_push_trade(payload: EATradePush, db: AsyncSession = Depends(get_db)):
    """
    Endpoint chiamato dall'EA (Expert Advisor) su MT4/MT5 per inviare i trade chiusi.
    Autenticazione tramite token EA (non JWT) memorizzato in metadata_json.ea_token.
    """
    # Trova la connessione tramite ea_token nel JSONB
    result = await db.execute(
        select(BrokerConnection).where(
            BrokerConnection.metadata_json["ea_token"].astext == payload.token
        )
    )
    connection = result.scalar_one_or_none()

    if not connection:
        logger.warning("[EA PUSH FAILED] Token non valido: %.8s...", payload.token)
        raise HTTPException(status_code=401, detail="Token EA non valido")

    logger.info(
        "[EA PUSH RECEIVED] connection=%s ticket=%s symbol=%s type=%s lots=%.2f pnl=%.2f",
        connection.id, payload.ticket, payload.symbol, payload.type, payload.lots, payload.profit,
    )

    external_id = str(payload.ticket)

    # Controlla duplicato
    existing = await db.execute(
        select(BrokerTrade).where(
            BrokerTrade.connection_id == connection.id,
            BrokerTrade.external_trade_id == external_id,
        )
    )
    if existing.scalar_one_or_none():
        logger.info(
            "[EA PUSH DUPLICATE] connection=%s ticket=%s symbol=%s — ignorato",
            connection.id, external_id, payload.symbol,
        )
        return {"status": "duplicate", "message": "Trade già registrato"}

    side = "buy" if payload.type.strip().lower() in ("buy", "long", "b") else "sell"
    open_time = _parse_dt(payload.open_time)
    close_time = _parse_dt(payload.close_time)

    if not open_time:
        raise HTTPException(status_code=422, detail=f"open_time non valido: {payload.open_time}")

    trade = BrokerTrade(
        connection_id=connection.id,
        user_id=connection.user_id,
        provider=connection.provider,
        external_trade_id=external_id,
        symbol=payload.symbol.strip(),
        side=side,
        open_time=open_time,
        close_time=close_time,
        open_price=payload.open_price,
        close_price=payload.close_price,
        volume=payload.lots,
        pnl=payload.profit,
        commission=payload.commission,
        swap=payload.swap,
        status="closed" if close_time else "open",
        metadata_json={
            "magic": payload.magic,
            "comment": payload.comment,
            "source": "ea",
        },
    )
    db.add(trade)
    await db.commit()

    await recalculate_daily_stats(db, connection)

    logger.info(
        "[EA PUSH OK] connection=%s provider=%s ticket=%s symbol=%s side=%s lots=%.2f "
        "open=%.5f close=%.5f pnl=%.2f commission=%.2f open_time=%s close_time=%s",
        connection.id,
        connection.provider,
        external_id,
        payload.symbol,
        side,
        payload.lots,
        payload.open_price,
        payload.close_price,
        payload.profit,
        payload.commission,
        payload.open_time,
        payload.close_time,
    )
    return {
        "status": "ok",
        "message": "Trade registrato",
        "connection_id": str(connection.id),
        "trade_id": str(trade.id),
        "symbol": trade.symbol,
        "side": trade.side,
        "pnl": float(trade.pnl) if trade.pnl else 0.0,
    }
