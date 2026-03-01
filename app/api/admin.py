import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_admin
from app.db.session import get_db
from app.schemas.admin import (
    AdminSyncErrorsResponse,
    AdminUserBrokerInfo,
    AdminUserConnectionsResponse,
    AdminUserListResponse,
)
from app.schemas.auth import CurrentUser
from app.schemas.connections import ConnectionResponse
from app.schemas.dashboard import DashboardResponse
from app.schemas.sync import SyncLogResponse, SyncTriggerResponse
from app.schemas.trades import DailyStatListResponse, DailyStatResponse, TradeListResponse, TradeResponse
from app.services import connection_service, sync_service, stats_service

router = APIRouter(prefix="/api/v1/broker/admin", tags=["broker-admin"])


@router.get("/users", response_model=AdminUserListResponse)
async def list_users_with_connections(
    admin: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    grouped = await connection_service.get_all_connections_grouped_by_user(db)
    return AdminUserListResponse(
        users=[
            AdminUserBrokerInfo(
                user_id=g["user_id"],
                connections_count=g["connections_count"],
                providers=g["providers"],
            )
            for g in grouped
        ],
        total=len(grouped),
    )


@router.get("/users/{user_id}/connections", response_model=AdminUserConnectionsResponse)
async def get_user_connections(
    user_id: uuid.UUID,
    admin: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    connections = await connection_service.get_connections_for_user(db, user_id)
    return AdminUserConnectionsResponse(
        user_id=user_id,
        connections=[
            ConnectionResponse(
                id=c.id,
                user_id=c.user_id,
                provider=c.provider,
                account_identifier=c.account_identifier,
                connection_status=c.connection_status,
                last_sync_at=c.last_sync_at,
                last_sync_status=c.last_sync_status,
                metadata=c.metadata_json or {},
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
            for c in connections
        ],
    )


@router.get("/connections/{connection_id}/dashboard", response_model=DashboardResponse)
async def get_connection_dashboard(
    connection_id: uuid.UUID,
    admin: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    conn = await connection_service.get_connection(db, connection_id)
    return await stats_service.get_dashboard(db, conn)


@router.get("/connections/{connection_id}/trades", response_model=TradeListResponse)
async def get_user_trades(
    connection_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None),
    admin: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    conn = await connection_service.get_connection(db, connection_id)
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


@router.get("/connections/{connection_id}/daily-stats", response_model=DailyStatListResponse)
async def get_user_daily_stats(
    connection_id: uuid.UUID,
    from_date: str | None = Query(default=None),
    to_date: str | None = Query(default=None),
    admin: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    conn = await connection_service.get_connection(db, connection_id)
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


@router.post("/connections/{connection_id}/sync", response_model=SyncTriggerResponse)
async def admin_trigger_sync(
    connection_id: uuid.UUID,
    admin: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    conn = await connection_service.get_connection(db, connection_id)
    sync_log = await sync_service.trigger_sync(db, conn)
    return SyncTriggerResponse(
        message="Sincronizzazione completata" if sync_log.status == "success" else "Sincronizzazione fallita",
        sync_log_id=sync_log.id,
    )


@router.get("/sync-errors", response_model=AdminSyncErrorsResponse)
async def get_sync_errors(
    limit: int = Query(default=50, ge=1, le=200),
    admin: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    logs = await connection_service.get_failed_sync_logs(db, limit)
    return AdminSyncErrorsResponse(
        errors=[
            SyncLogResponse(
                id=log.id,
                connection_id=log.connection_id,
                started_at=log.started_at,
                completed_at=log.completed_at,
                status=log.status,
                trades_synced=log.trades_synced,
                error_message=log.error_message,
            )
            for log in logs
        ],
        total=len(logs),
    )
