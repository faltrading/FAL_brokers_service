import uuid
from datetime import datetime

from pydantic import BaseModel


class SyncStatusResponse(BaseModel):
    connection_id: uuid.UUID
    status: str
    last_sync_at: datetime | None = None
    last_sync_status: str | None = None
    last_sync_error: str | None = None
    current_sync_running: bool = False


class SyncLogResponse(BaseModel):
    id: uuid.UUID
    connection_id: uuid.UUID
    started_at: datetime
    completed_at: datetime | None = None
    status: str
    trades_synced: int
    error_message: str | None = None


class SyncTriggerResponse(BaseModel):
    message: str
    sync_log_id: uuid.UUID
    trades_synced: int = 0
    ea_pending: bool = False
