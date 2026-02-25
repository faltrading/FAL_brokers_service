from pydantic import BaseModel, Field


class KpiData(BaseModel):
    net_pnl: float = 0
    total_trades: int = 0
    win_rate: float = 0
    profit_factor: float = 0
    day_win_rate: float = 0
    avg_win_loss_ratio: float = 0
    avg_win_trade: float = 0
    avg_loss_trade: float = 0


class DailyPnlPoint(BaseModel):
    date: str
    pnl: float
    cumulative_pnl: float


class CalendarDay(BaseModel):
    date: str
    pnl: float
    trade_count: int


class RecentTrade(BaseModel):
    close_date: str
    symbol: str
    side: str
    pnl: float


class OpenPosition(BaseModel):
    symbol: str
    side: str
    open_time: str
    open_price: float
    volume: float
    current_pnl: float | None = None


class PerformanceScore(BaseModel):
    win_rate: float = 0
    profit_factor: float = 0
    consistency: float = 0
    max_drawdown: float = 0
    avg_win_loss: float = 0
    recovery_factor: float = 0
    overall_score: float = 0


class DashboardResponse(BaseModel):
    kpi: KpiData = Field(default_factory=KpiData)
    daily_pnl: list[DailyPnlPoint] = Field(default_factory=list)
    calendar_data: list[CalendarDay] = Field(default_factory=list)
    recent_trades: list[RecentTrade] = Field(default_factory=list)
    open_positions: list[OpenPosition] = Field(default_factory=list)
    performance_score: PerformanceScore = Field(default_factory=PerformanceScore)
    last_sync_at: str | None = None
    provider: str = ""
    account_identifier: str = ""
