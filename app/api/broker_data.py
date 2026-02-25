import uuid

from fastapi import APIRouter, Depends, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.session import get_db
from app.schemas.auth import CurrentUser
from app.schemas.dashboard import DashboardResponse
from app.schemas.sync import SyncLogResponse, SyncStatusResponse, SyncTriggerResponse
from app.schemas.trades import DailyStatListResponse, DailyStatResponse, TradeListResponse, TradeResponse
from app.services import connection_service, sync_service, stats_service, csv_import_service

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
