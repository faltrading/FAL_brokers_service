import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class BrokerTrade(Base):
    __tablename__ = "broker_trades"
    __table_args__ = (
        Index("idx_broker_trades_connection_close", "connection_id", "close_time"),
        Index("idx_broker_trades_user_provider", "user_id", "provider"),
        Index("idx_broker_trades_symbol", "symbol"),
        Index("idx_broker_trades_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("broker_connections.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    external_trade_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    open_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    close_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    open_price: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    close_price: Mapped[float | None] = mapped_column(Numeric(18, 8), nullable=True)
    volume: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    pnl: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    commission: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    swap: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="closed")
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    connection = relationship("BrokerConnection", back_populates="trades")
