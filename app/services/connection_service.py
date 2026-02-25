import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import encrypt_credentials, decrypt_credentials
from app.core.exceptions import (
    ConnectionNotFoundError,
    DuplicateConnectionError,
    UnauthorizedAccessError,
)
from app.models.broker_connection import BrokerConnection
from app.models.broker_daily_stat import BrokerDailyStat
from app.models.broker_sync_log import BrokerSyncLog
from app.models.broker_trade import BrokerTrade
from app.schemas.auth import CurrentUser

logger = logging.getLogger(__name__)


async def create_connection(
    db: AsyncSession,
    user: CurrentUser,
    provider: str,
    account_identifier: str,
    credentials: dict,
    metadata: dict | None = None,
) -> BrokerConnection:
    existing = await db.execute(
        select(BrokerConnection).where(
            BrokerConnection.user_id == user.user_id,
            BrokerConnection.provider == provider,
            BrokerConnection.account_identifier == account_identifier,
        )
    )
    if existing.scalar_one_or_none():
        raise DuplicateConnectionError()

    encrypted = encrypt_credentials(credentials) if credentials else None

    connection = BrokerConnection(
        user_id=user.user_id,
        provider=provider,
        account_identifier=account_identifier,
        credentials_encrypted=encrypted,
        connection_status="active",
        metadata_json=metadata or {},
    )
    db.add(connection)
    await db.commit()
    await db.refresh(connection)
    return connection


async def get_connection(
    db: AsyncSession, connection_id: uuid.UUID
) -> BrokerConnection:
    result = await db.execute(
        select(BrokerConnection).where(BrokerConnection.id == connection_id)
    )
    connection = result.scalar_one_or_none()
    if not connection:
        raise ConnectionNotFoundError()
    return connection


async def get_connection_with_auth(
    db: AsyncSession, connection_id: uuid.UUID, user: CurrentUser
) -> BrokerConnection:
    connection = await get_connection(db, connection_id)
    if connection.user_id != user.user_id and not user.is_admin:
        raise UnauthorizedAccessError()
    return connection


async def list_user_connections(
    db: AsyncSession, user_id: uuid.UUID
) -> list[BrokerConnection]:
    result = await db.execute(
        select(BrokerConnection)
        .where(BrokerConnection.user_id == user_id)
        .order_by(BrokerConnection.created_at.desc())
    )
    return list(result.scalars().all())


async def update_connection(
    db: AsyncSession,
    connection: BrokerConnection,
    account_identifier: str | None = None,
    credentials: dict | None = None,
    connection_status: str | None = None,
    metadata: dict | None = None,
) -> BrokerConnection:
    if account_identifier is not None:
        connection.account_identifier = account_identifier
    if credentials is not None:
        connection.credentials_encrypted = encrypt_credentials(credentials)
    if connection_status is not None:
        connection.connection_status = connection_status
    if metadata is not None:
        connection.metadata_json = metadata
    connection.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(connection)
    return connection


async def delete_connection(
    db: AsyncSession, connection_id: uuid.UUID
) -> None:
    connection = await get_connection(db, connection_id)
    await db.delete(connection)
    await db.commit()


async def get_decrypted_credentials(connection: BrokerConnection) -> dict:
    if not connection.credentials_encrypted:
        return {}
    return decrypt_credentials(connection.credentials_encrypted)


async def get_all_connections_grouped_by_user(
    db: AsyncSession,
) -> list[dict]:
    result = await db.execute(
        select(
            BrokerConnection.user_id,
            func.count(BrokerConnection.id).label("connections_count"),
            func.array_agg(func.distinct(BrokerConnection.provider)).label("providers"),
        )
        .group_by(BrokerConnection.user_id)
        .order_by(func.count(BrokerConnection.id).desc())
    )
    rows = result.all()
    return [
        {
            "user_id": row.user_id,
            "connections_count": row.connections_count,
            "providers": row.providers or [],
        }
        for row in rows
    ]


async def get_connections_for_user(
    db: AsyncSession, user_id: uuid.UUID
) -> list[BrokerConnection]:
    result = await db.execute(
        select(BrokerConnection)
        .where(BrokerConnection.user_id == user_id)
        .order_by(BrokerConnection.created_at.desc())
    )
    return list(result.scalars().all())


async def get_failed_sync_logs(
    db: AsyncSession, limit: int = 50
) -> list[BrokerSyncLog]:
    result = await db.execute(
        select(BrokerSyncLog)
        .where(BrokerSyncLog.status == "failed")
        .order_by(BrokerSyncLog.started_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
