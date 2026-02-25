import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import SyncInProgressError
from app.models.broker_connection import BrokerConnection
from app.models.broker_sync_log import BrokerSyncLog
from app.models.broker_trade import BrokerTrade
from app.services.connection_service import get_decrypted_credentials
from app.services.providers.provider_factory import get_provider
from app.services.stats_service import recalculate_daily_stats

logger = logging.getLogger(__name__)

SYNC_COOLDOWN_SECONDS = 120


async def trigger_sync(
    db: AsyncSession, connection: BrokerConnection
) -> BrokerSyncLog:
    running = await db.execute(
        select(BrokerSyncLog).where(
            BrokerSyncLog.connection_id == connection.id,
            BrokerSyncLog.status == "running",
        )
    )
    if running.scalar_one_or_none():
        raise SyncInProgressError()

    if connection.last_sync_at:
        elapsed = (datetime.now(timezone.utc) - connection.last_sync_at).total_seconds()
        if elapsed < SYNC_COOLDOWN_SECONDS and connection.last_sync_status == "success":
            raise SyncInProgressError()

    sync_log = BrokerSyncLog(connection_id=connection.id, status="running")
    db.add(sync_log)
    await db.commit()
    await db.refresh(sync_log)

    connection.last_sync_status = "in_progress"
    connection.last_sync_error = None
    await db.commit()

    try:
        credentials = await get_decrypted_credentials(connection)
        provider = get_provider(connection.provider, credentials)

        trades = await provider.fetch_trades()
        trades_synced = 0

        for trade in trades:
            existing = None
            if trade.external_trade_id:
                result = await db.execute(
                    select(BrokerTrade).where(
                        BrokerTrade.connection_id == connection.id,
                        BrokerTrade.external_trade_id == trade.external_trade_id,
                    )
                )
                existing = result.scalar_one_or_none()

            if existing:
                existing.symbol = trade.symbol
                existing.side = trade.side
                existing.open_time = trade.open_time
                existing.close_time = trade.close_time
                existing.open_price = trade.open_price
                existing.close_price = trade.close_price
                existing.volume = trade.volume
                existing.pnl = trade.pnl
                existing.commission = trade.commission
                existing.swap = trade.swap
                existing.status = trade.status
                existing.metadata_json = trade.metadata
                existing.updated_at = datetime.now(timezone.utc)
            else:
                db_trade = BrokerTrade(
                    connection_id=connection.id,
                    user_id=connection.user_id,
                    provider=connection.provider,
                    external_trade_id=trade.external_trade_id,
                    symbol=trade.symbol,
                    side=trade.side,
                    open_time=trade.open_time,
                    close_time=trade.close_time,
                    open_price=trade.open_price,
                    close_price=trade.close_price,
                    volume=trade.volume,
                    pnl=trade.pnl,
                    commission=trade.commission,
                    swap=trade.swap,
                    status=trade.status,
                    metadata_json=trade.metadata,
                )
                db.add(db_trade)
            trades_synced += 1

        await db.commit()

        await recalculate_daily_stats(db, connection)

        now = datetime.now(timezone.utc)
        sync_log.status = "success"
        sync_log.completed_at = now
        sync_log.trades_synced = trades_synced
        connection.last_sync_at = now
        connection.last_sync_status = "success"
        connection.last_sync_error = None
        await db.commit()
        await db.refresh(sync_log)

        logger.info(f"Sync completed for connection {connection.id}: {trades_synced} trades")
        return sync_log

    except Exception as e:
        now = datetime.now(timezone.utc)
        sync_log.status = "failed"
        sync_log.completed_at = now
        sync_log.error_message = str(e)[:1000]
        connection.last_sync_status = "failed"
        connection.last_sync_error = str(e)[:500]
        await db.commit()
        await db.refresh(sync_log)

        logger.error(f"Sync failed for connection {connection.id}: {e}")
        return sync_log


async def get_sync_status(
    db: AsyncSession, connection: BrokerConnection
) -> dict:
    running = await db.execute(
        select(BrokerSyncLog).where(
            BrokerSyncLog.connection_id == connection.id,
            BrokerSyncLog.status == "running",
        )
    )
    current_running = running.scalar_one_or_none() is not None

    return {
        "connection_id": connection.id,
        "status": connection.connection_status,
        "last_sync_at": connection.last_sync_at,
        "last_sync_status": connection.last_sync_status,
        "last_sync_error": connection.last_sync_error,
        "current_sync_running": current_running,
    }


async def get_sync_logs(
    db: AsyncSession, connection_id: uuid.UUID, limit: int = 20
) -> list[BrokerSyncLog]:
    result = await db.execute(
        select(BrokerSyncLog)
        .where(BrokerSyncLog.connection_id == connection_id)
        .order_by(BrokerSyncLog.started_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
