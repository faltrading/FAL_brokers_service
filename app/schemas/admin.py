import uuid

from pydantic import BaseModel, Field

from app.schemas.connections import ConnectionResponse
from app.schemas.sync import SyncLogResponse


class AdminUserBrokerInfo(BaseModel):
    user_id: uuid.UUID
    username: str | None = None
    connections_count: int = 0
    providers: list[str] = Field(default_factory=list)


class AdminUserListResponse(BaseModel):
    users: list[AdminUserBrokerInfo]
    total: int


class AdminUserConnectionsResponse(BaseModel):
    user_id: uuid.UUID
    connections: list[ConnectionResponse]


class AdminSyncErrorsResponse(BaseModel):
    errors: list[SyncLogResponse]
    total: int
