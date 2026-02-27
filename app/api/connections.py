import secrets
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.session import get_db
from app.schemas.auth import CurrentUser
from app.schemas.connections import (
    ConnectionCreate,
    ConnectionListResponse,
    ConnectionResponse,
    ConnectionUpdate,
)
from app.services import connection_service
from app.services.providers.provider_factory import get_credential_fields, SUPPORTED_PROVIDERS

router = APIRouter(prefix="/api/v1/broker/connections", tags=["broker-connections"])


def _connection_to_response(conn) -> ConnectionResponse:
    return ConnectionResponse(
        id=conn.id,
        user_id=conn.user_id,
        provider=conn.provider,
        account_identifier=conn.account_identifier,
        connection_status=conn.connection_status,
        last_sync_at=conn.last_sync_at,
        last_sync_status=conn.last_sync_status,
        metadata=conn.metadata_json or {},
        created_at=conn.created_at,
        updated_at=conn.updated_at,
    )


@router.get("/providers")
async def list_providers():
    result = {}
    for provider in SUPPORTED_PROVIDERS:
        result[provider] = get_credential_fields(provider)
    return {"providers": result}


@router.post("", response_model=ConnectionResponse, status_code=201)
async def create_connection(
    payload: ConnectionCreate,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conn = await connection_service.create_connection(
        db=db,
        user=user,
        provider=payload.provider.value,
        account_identifier=payload.account_identifier,
        credentials=payload.credentials,
        metadata=payload.metadata,
    )
    return _connection_to_response(conn)


@router.get("", response_model=ConnectionListResponse)
async def list_connections(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    connections = await connection_service.list_user_connections(db, user.user_id)
    return ConnectionListResponse(
        connections=[_connection_to_response(c) for c in connections],
        total=len(connections),
    )


@router.get("/{connection_id}", response_model=ConnectionResponse)
async def get_connection(
    connection_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conn = await connection_service.get_connection_with_auth(db, connection_id, user)
    return _connection_to_response(conn)


@router.put("/{connection_id}", response_model=ConnectionResponse)
async def update_connection(
    connection_id: uuid.UUID,
    payload: ConnectionUpdate,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conn = await connection_service.get_connection_with_auth(db, connection_id, user)
    updated = await connection_service.update_connection(
        db=db,
        connection=conn,
        account_identifier=payload.account_identifier,
        credentials=payload.credentials,
        connection_status=payload.connection_status,
        metadata=payload.metadata,
    )
    return _connection_to_response(updated)


@router.delete("/{connection_id}", status_code=204)
async def delete_connection(
    connection_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await connection_service.get_connection_with_auth(db, connection_id, user)
    await connection_service.delete_connection(db, connection_id)


@router.post("/{connection_id}/ea-token")
async def generate_ea_token(
    connection_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Genera (o rigenera) il token EA per questa connessione."""
    conn = await connection_service.get_connection_with_auth(db, connection_id, user)
    token = secrets.token_urlsafe(32)
    metadata = dict(conn.metadata_json or {})
    metadata["ea_token"] = token
    conn.metadata_json = metadata
    flag_modified(conn, "metadata_json")
    await db.commit()
    await db.refresh(conn)
    return {"ea_token": token, "connection_id": str(connection_id)}
