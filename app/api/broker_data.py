import logging
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, UploadFile, File
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.broker_sync_log import BrokerSyncLog
from app.models.broker_trade import BrokerTrade
from app.schemas.auth import CurrentUser
from app.schemas.dashboard import DashboardResponse
from app.schemas.sync import SyncLogResponse, SyncStatusResponse, SyncTriggerResponse
from app.schemas.trades import DailyStatListResponse, DailyStatResponse, TradeListResponse, TradeResponse
from app.services import connection_service, sync_service, stats_service, csv_import_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/broker/connections", tags=["broker-data"])


@router.post("/{connection_id}/sync", response_model=SyncTriggerResponse)
async def trigger_sync(
    connection_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conn = await connection_service.get_connection_with_auth(db, connection_id, user)
    sync_log = await sync_service.trigger_sync(db, conn)
    return SyncTriggerResponse(
        message="Sincronizzazione completata" if sync_log.status == "success" else "Sincronizzazione fallita",
        sync_log_id=sync_log.id,
    )


@router.post("/{connection_id}/sync/reset")
async def reset_stuck_sync(
    connection_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Azzera manualmente i log di sincronizzazione bloccati ('running').
    Utile quando una sincronizzazione precedente è crashata e il lock è rimasto attivo.
    """
    conn = await connection_service.get_connection_with_auth(db, connection_id, user)
    result = await db.execute(
        select(BrokerSyncLog).where(
            BrokerSyncLog.connection_id == conn.id,
            BrokerSyncLog.status == "running",
        )
    )
    stuck_logs = result.scalars().all()
    reset_count = 0
    for log in stuck_logs:
        age = (datetime.now(timezone.utc) - log.started_at).total_seconds()
        log.status = "failed"
        log.completed_at = datetime.now(timezone.utc)
        log.error_message = f"Reset manuale (age={age:.0f}s)"
        reset_count += 1
        logger.warning(
            "Manual sync reset: connection=%s log_id=%s age=%.0fs",
            conn.id, log.id, age,
        )
    if reset_count:
        conn.last_sync_status = "failed"
        await db.commit()
    return {"message": f"{reset_count} lock azzerati", "reset_count": reset_count}


@router.get("/{connection_id}/debug")
async def debug_connection(
    connection_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Endpoint diagnostico: mostra lo stato completo della connessione,
    il token EA, i trade nel DB e cosa l'EA deve configurare.
    """
    conn = await connection_service.get_connection_with_auth(db, connection_id, user)

    # --- Trade counts ---
    total_count = (await db.execute(
        select(func.count(BrokerTrade.id)).where(BrokerTrade.connection_id == conn.id)
    )).scalar() or 0

    closed_count = (await db.execute(
        select(func.count(BrokerTrade.id)).where(
            BrokerTrade.connection_id == conn.id, BrokerTrade.status == "closed"
        )
    )).scalar() or 0

    open_count = (await db.execute(
        select(func.count(BrokerTrade.id)).where(
            BrokerTrade.connection_id == conn.id, BrokerTrade.status == "open"
        )
    )).scalar() or 0

    ea_count = (await db.execute(
        select(func.count(BrokerTrade.id)).where(
            BrokerTrade.connection_id == conn.id,
            BrokerTrade.metadata_json["source"].astext == "ea",
        )
    )).scalar() or 0

    # --- Last 3 trades ---
    last_trades_result = await db.execute(
        select(BrokerTrade)
        .where(BrokerTrade.connection_id == conn.id)
        .order_by(BrokerTrade.created_at.desc())
        .limit(3)
    )
    last_trades = [
        {
            "id": str(t.id),
            "symbol": t.symbol,
            "side": t.side,
            "pnl": float(t.pnl) if t.pnl is not None else None,
            "status": t.status,
            "source": (t.metadata_json or {}).get("source", "unknown"),
            "external_trade_id": t.external_trade_id,
            "created_at": t.created_at.isoformat(),
        }
        for t in last_trades_result.scalars().all()
    ]

    # --- Last sync log ---
    last_log_result = await db.execute(
        select(BrokerSyncLog)
        .where(BrokerSyncLog.connection_id == conn.id)
        .order_by(BrokerSyncLog.started_at.desc())
        .limit(1)
    )
    last_log = last_log_result.scalar_one_or_none()

    # --- EA token & push URL ---
    metadata = conn.metadata_json or {}
    ea_token = metadata.get("ea_token")
    base_url = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
    ea_push_url = f"{base_url}/api/v1/broker/ea/push" if base_url else "<PUBLIC_BASE_URL env not set>"

    logger.info(
        "[DEBUG] connection=%s total_trades=%d closed=%d open=%d ea_sourced=%d ea_token_set=%s",
        conn.id, total_count, closed_count, open_count, ea_count, bool(ea_token),
    )

    return {
        "connection": {
            "id": str(conn.id),
            "provider": conn.provider,
            "account_identifier": conn.account_identifier,
            "status": conn.connection_status,
            "last_sync_at": conn.last_sync_at.isoformat() if conn.last_sync_at else None,
            "last_sync_status": conn.last_sync_status,
        },
        "ea_config": {
            "ea_token_set": bool(ea_token),
            "ea_token_preview": (ea_token[:8] + "..." + ea_token[-4:]) if ea_token else None,
            "ea_push_url": ea_push_url,
            "instruction": (
                "EA token non impostato. Chiama POST /{connection_id}/ea-token per generarlo."
                if not ea_token
                else f"Configura l'EA con: URL={ea_push_url} e TOKEN={ea_token[:8]}..."
            ),
        },
        "trades_in_db": {
            "total": total_count,
            "closed": closed_count,
            "open": open_count,
            "from_ea_push": ea_count,
            "last_3": last_trades,
        },
        "last_sync_log": {
            "status": last_log.status if last_log else None,
            "started_at": last_log.started_at.isoformat() if last_log and last_log.started_at else None,
            "completed_at": last_log.completed_at.isoformat() if last_log and last_log.completed_at else None,
            "trades_synced": last_log.trades_synced if last_log else 0,
            "error_message": last_log.error_message if last_log else None,
        } if last_log else None,
    }


@router.get("/{connection_id}/sync-status", response_model=SyncStatusResponse)
async def get_sync_status(
    connection_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conn = await connection_service.get_connection_with_auth(db, connection_id, user)
    status = await sync_service.get_sync_status(db, conn)
    return SyncStatusResponse(**status)


@router.get("/{connection_id}/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    connection_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conn = await connection_service.get_connection_with_auth(db, connection_id, user)
    return await stats_service.get_dashboard(db, conn)


@router.get("/{connection_id}/trades", response_model=TradeListResponse)
async def get_trades(
    connection_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conn = await connection_service.get_connection_with_auth(db, connection_id, user)
    trades, total = await stats_service.get_trades_paginated(
        db, conn.id, limit=limit, offset=offset, status_filter=status,
    )
    return TradeListResponse(
        trades=[
            TradeResponse(
                id=t.id,
                connection_id=t.connection_id,
                provider=t.provider,
                external_trade_id=t.external_trade_id,
                symbol=t.symbol,
                side=t.side,
                open_time=t.open_time,
                close_time=t.close_time,
                open_price=float(t.open_price),
                close_price=float(t.close_price) if t.close_price else None,
                volume=float(t.volume),
                pnl=float(t.pnl) if t.pnl else None,
                commission=float(t.commission),
                swap=float(t.swap),
                status=t.status,
                metadata=t.metadata_json or {},
                created_at=t.created_at,
            )
            for t in trades
        ],
        total=total,
        has_more=(offset + limit) < total,
    )


@router.get("/{connection_id}/daily-stats", response_model=DailyStatListResponse)
async def get_daily_stats(
    connection_id: uuid.UUID,
    from_date: str | None = Query(default=None),
    to_date: str | None = Query(default=None),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conn = await connection_service.get_connection_with_auth(db, connection_id, user)
    stats = await stats_service.get_daily_stats(db, conn.id, from_date, to_date)
    return DailyStatListResponse(
        stats=[
            DailyStatResponse(
                id=s.id,
                connection_id=s.connection_id,
                provider=s.provider,
                date=s.date.isoformat(),
                total_pnl=float(s.total_pnl),
                trade_count=s.trade_count,
                winning_trades=s.winning_trades,
                losing_trades=s.losing_trades,
                volume=float(s.volume),
                metadata=s.metadata_json or {},
            )
            for s in stats
        ],
        total=len(stats),
    )


@router.get("/{connection_id}/open-positions")
async def get_open_positions(
    connection_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conn = await connection_service.get_connection_with_auth(db, connection_id, user)
    trades, total = await stats_service.get_trades_paginated(
        db, conn.id, limit=100, offset=0, status_filter="open",
    )
    return {
        "positions": [
            {
                "id": str(t.id),
                "symbol": t.symbol,
                "side": t.side,
                "open_time": t.open_time.isoformat(),
                "open_price": float(t.open_price),
                "volume": float(t.volume),
                "current_pnl": float(t.pnl) if t.pnl else None,
            }
            for t in trades
        ],
        "total": total,
    }


@router.post("/{connection_id}/import-csv")
async def import_csv(
    connection_id: uuid.UUID,
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conn = await connection_service.get_connection_with_auth(db, connection_id, user)
    content = await file.read()
    trades_imported = await csv_import_service.import_csv(db, conn, content)
    return {
        "message": f"{trades_imported} trades importati con successo",
        "trades_imported": trades_imported,
    }
