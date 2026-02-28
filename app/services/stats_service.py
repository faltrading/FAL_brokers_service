import logging
import uuid
from collections import defaultdict
from datetime import date, datetime, timezone

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.broker_connection import BrokerConnection
from app.models.broker_daily_stat import BrokerDailyStat
from app.models.broker_trade import BrokerTrade
from app.schemas.dashboard import (
    CalendarDay,
    DailyPnlPoint,
    DashboardResponse,
    KpiData,
    OpenPosition,
    PerformanceScore,
    RecentTrade,
)

logger = logging.getLogger(__name__)


def _net_pnl(t: "BrokerTrade") -> float:
    """Return net P&L including commission and swap."""
    return float(t.pnl or 0) + float(t.commission or 0) + float(t.swap or 0)


async def recalculate_daily_stats(
    db: AsyncSession, connection: BrokerConnection
) -> None:
    await db.execute(
        delete(BrokerDailyStat).where(BrokerDailyStat.connection_id == connection.id)
    )

    result = await db.execute(
        select(BrokerTrade)
        .where(
            BrokerTrade.connection_id == connection.id,
            BrokerTrade.status == "closed",
            BrokerTrade.close_time.isnot(None),
        )
        .order_by(BrokerTrade.close_time)
    )
    trades = result.scalars().all()

    daily: dict[str, dict] = defaultdict(lambda: {
        "total_pnl": 0, "trade_count": 0, "winning_trades": 0,
        "losing_trades": 0, "volume": 0,
    })

    for trade in trades:
        day_key = trade.close_time.date()
        d = daily[day_key]
        pnl = _net_pnl(trade)
        d["total_pnl"] += pnl
        d["trade_count"] += 1
        d["volume"] += float(trade.volume or 0)
        if pnl > 0:
            d["winning_trades"] += 1
        elif pnl < 0:
            d["losing_trades"] += 1

    for day_key, stats in daily.items():
        stat = BrokerDailyStat(
            connection_id=connection.id,
            user_id=connection.user_id,
            provider=connection.provider,
            date=day_key,
            total_pnl=stats["total_pnl"],
            trade_count=stats["trade_count"],
            winning_trades=stats["winning_trades"],
            losing_trades=stats["losing_trades"],
            volume=stats["volume"],
        )
        db.add(stat)

    await db.commit()


async def get_dashboard(
    db: AsyncSession, connection: BrokerConnection
) -> DashboardResponse:
    logger.info(
        "[DASHBOARD] Querying DB for connection=%s provider=%s",
        connection.id, connection.provider,
    )

    result = await db.execute(
        select(BrokerTrade)
        .where(BrokerTrade.connection_id == connection.id, BrokerTrade.status == "closed")
        .order_by(BrokerTrade.close_time)
    )
    closed_trades = list(result.scalars().all())

    result = await db.execute(
        select(BrokerTrade)
        .where(BrokerTrade.connection_id == connection.id, BrokerTrade.status == "open")
        .order_by(BrokerTrade.open_time.desc())
    )
    open_trades = list(result.scalars().all())

    logger.info(
        "[DASHBOARD] DB result: closed_trades=%d open_trades=%d",
        len(closed_trades), len(open_trades),
    )

    if closed_trades:
        sample = closed_trades[0]
        logger.info(
            "[DASHBOARD] Sample trade: id=%s symbol=%s side=%s pnl=%s volume=%s "
            "open_time=%s close_time=%s status=%s source=%s",
            sample.id, sample.symbol, sample.side, sample.pnl, sample.volume,
            sample.open_time, sample.close_time, sample.status,
            (sample.metadata_json or {}).get("source", "unknown"),
        )
    else:
        logger.warning(
            "[DASHBOARD] ⚠ ZERO closed trades in DB for connection=%s — "
            "EA push may not have been received, or trade status is not 'closed'",
            connection.id,
        )

    kpi = _compute_kpi(closed_trades)
    daily_pnl = _compute_daily_pnl(closed_trades)
    calendar_data = _compute_calendar(closed_trades)
    recent = _compute_recent_trades(closed_trades, limit=20)
    positions = _compute_open_positions(open_trades)
    score = _compute_performance_score(closed_trades, daily_pnl)

    logger.info(
        "[DASHBOARD] KPI → total_pnl=%s total_trades=%d win_rate=%s%% profit_factor=%s max_dd=%s",
        kpi.total_pnl, kpi.total_trades, kpi.win_rate, kpi.profit_factor, kpi.max_drawdown,
    )
    logger.info(
        "[DASHBOARD] Response → daily_pnl_days=%d recent_trades=%d open_positions=%d",
        len(daily_pnl), len(recent), len(positions),
    )

    return DashboardResponse(
        kpi=kpi,
        daily_pnl=daily_pnl,
        calendar_data=calendar_data,
        recent_trades=recent,
        open_positions=positions,
        performance_score=score,
        last_sync_at=connection.last_sync_at.isoformat() if connection.last_sync_at else None,
        provider=connection.provider,
        account_identifier=connection.account_identifier,
    )


def _compute_kpi(trades: list[BrokerTrade]) -> KpiData:
    if not trades:
        return KpiData()

    total_pnl = sum(_net_pnl(t) for t in trades)
    total_trades = len(trades)
    wins = [t for t in trades if _net_pnl(t) > 0]
    losses = [t for t in trades if _net_pnl(t) < 0]
    win_rate = (len(wins) / total_trades * 100) if total_trades > 0 else 0

    total_win_amount = sum(_net_pnl(t) for t in wins) if wins else 0
    total_loss_amount = abs(sum(_net_pnl(t) for t in losses)) if losses else 0
    profit_factor = (total_win_amount / total_loss_amount) if total_loss_amount > 0 else 0

    avg_win = (total_win_amount / len(wins)) if wins else 0
    avg_loss = (total_loss_amount / len(losses)) if losses else 0
    avg_win_loss_ratio = (avg_win / avg_loss) if avg_loss > 0 else 0

    daily_pnls: dict[str, float] = defaultdict(float)
    for t in trades:
        if t.close_time:
            daily_pnls[t.close_time.date().isoformat()] += _net_pnl(t)

    winning_days = sum(1 for v in daily_pnls.values() if v > 0)
    total_days = len(daily_pnls)
    day_win_rate = (winning_days / total_days * 100) if total_days > 0 else 0

    # max drawdown from cumulative equity curve
    max_dd = 0.0
    peak = 0.0
    cumulative = 0.0
    for t in sorted(trades, key=lambda x: x.close_time or x.open_time):
        cumulative += _net_pnl(t)
        if cumulative > peak:
            peak = cumulative
        dd = peak - cumulative
        if dd > max_dd:
            max_dd = dd

    return KpiData(
        total_pnl=round(total_pnl, 2),
        total_trades=total_trades,
        win_rate=round(win_rate, 2),
        profit_factor=round(profit_factor, 2),
        max_drawdown=round(max_dd, 2),
        average_win=round(avg_win, 2),
        average_loss=round(avg_loss, 2),
        day_win_rate=round(day_win_rate, 2),
        avg_win_loss_ratio=round(avg_win_loss_ratio, 2),
    )


def _compute_daily_pnl(trades: list[BrokerTrade]) -> list[DailyPnlPoint]:
    daily: dict[str, float] = defaultdict(float)
    for t in trades:
        if t.close_time:
            daily[t.close_time.date().isoformat()] += _net_pnl(t)

    sorted_days = sorted(daily.keys())
    result = []
    cumulative = 0
    for day in sorted_days:
        pnl = daily[day]
        cumulative += pnl
        result.append(DailyPnlPoint(
            date=day,
            total_pnl=round(pnl, 2),
            cumulative_pnl=round(cumulative, 2),
        ))
    return result


def _compute_calendar(trades: list[BrokerTrade]) -> list[CalendarDay]:
    daily: dict[str, dict] = defaultdict(lambda: {"pnl": 0, "count": 0})
    for t in trades:
        if t.close_time:
            day = t.close_time.date().isoformat()
            daily[day]["pnl"] += _net_pnl(t)
            daily[day]["count"] += 1

    return [
        CalendarDay(date=day, pnl=round(data["pnl"], 2), trade_count=data["count"])
        for day, data in sorted(daily.items())
    ]


def _compute_recent_trades(trades: list[BrokerTrade], limit: int = 20) -> list[RecentTrade]:
    sorted_trades = sorted(trades, key=lambda t: t.close_time or t.open_time, reverse=True)
    return [
        RecentTrade(
            id=str(t.id),
            symbol=t.symbol,
            side=t.side,
            volume=round(float(t.volume or 0), 2),
            pnl=round(_net_pnl(t), 2),
            close_time=t.close_time.isoformat() if t.close_time else None,
        )
        for t in sorted_trades[:limit]
    ]


def _compute_open_positions(trades: list[BrokerTrade]) -> list[OpenPosition]:
    return [
        OpenPosition(
            symbol=t.symbol,
            side=t.side,
            open_time=t.open_time.isoformat(),
            open_price=float(t.open_price),
            volume=float(t.volume),
            current_pnl=round(float(t.pnl or 0), 2) if t.pnl else None,
        )
        for t in trades
    ]


def _compute_performance_score(
    trades: list[BrokerTrade], daily_pnl: list[DailyPnlPoint]
) -> PerformanceScore:
    if not trades:
        return PerformanceScore()

    total = len(trades)
    wins = sum(1 for t in trades if _net_pnl(t) > 0)
    win_rate_pct = (wins / total * 100) if total > 0 else 0

    win_amounts = [_net_pnl(t) for t in trades if _net_pnl(t) > 0]
    loss_amounts = [abs(_net_pnl(t)) for t in trades if _net_pnl(t) < 0]
    total_win = sum(win_amounts) if win_amounts else 0
    total_loss = sum(loss_amounts) if loss_amounts else 0
    profit_factor = (total_win / total_loss) if total_loss > 0 else 0

    avg_win = (total_win / len(win_amounts)) if win_amounts else 0
    avg_loss = (total_loss / len(loss_amounts)) if loss_amounts else 0
    avg_win_loss = (avg_win / avg_loss) if avg_loss > 0 else 0

    max_dd = 0.0
    peak = 0.0
    for point in daily_pnl:
        if point.cumulative_pnl > peak:
            peak = point.cumulative_pnl
        dd = peak - point.cumulative_pnl
        if dd > max_dd:
            max_dd = dd

    net_pnl = sum(_net_pnl(t) for t in trades)
    recovery_factor = (net_pnl / max_dd) if max_dd > 0 else 0

    daily_returns = [p.total_pnl for p in daily_pnl]
    consistency = 0
    if daily_returns:
        mean_return = sum(daily_returns) / len(daily_returns)
        variance = sum((r - mean_return) ** 2 for r in daily_returns) / len(daily_returns)
        std_dev = variance ** 0.5
        consistency = max(0, 100 - std_dev * 0.1) if std_dev > 0 else 100

    win_score = min(win_rate_pct, 100)
    pf_score = min(profit_factor * 20, 100)
    consistency_score = min(consistency, 100)
    dd_score = max(0, 100 - max_dd * 0.01)
    awl_score = min(avg_win_loss * 25, 100)
    rf_score = min(recovery_factor * 20, 100)

    overall = (win_score + pf_score + consistency_score + dd_score + awl_score + rf_score) / 6

    return PerformanceScore(
        win_rate=round(win_score, 2),
        profit_factor=round(pf_score, 2),
        consistency=round(consistency_score, 2),
        max_drawdown=round(dd_score, 2),
        avg_win_loss=round(awl_score, 2),
        recovery_factor=round(rf_score, 2),
        overall_score=round(overall, 2),
    )


async def get_trades_paginated(
    db: AsyncSession,
    connection_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
    status_filter: str | None = None,
) -> tuple[list[BrokerTrade], int]:
    query = select(BrokerTrade).where(BrokerTrade.connection_id == connection_id)
    count_query = select(func.count(BrokerTrade.id)).where(BrokerTrade.connection_id == connection_id)

    if status_filter:
        query = query.where(BrokerTrade.status == status_filter)
        count_query = count_query.where(BrokerTrade.status == status_filter)

    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    result = await db.execute(
        query.order_by(BrokerTrade.close_time.desc().nullslast(), BrokerTrade.open_time.desc())
        .offset(offset)
        .limit(limit)
    )
    trades = list(result.scalars().all())

    logger.info(
        "[TRADES] connection=%s status_filter=%s total_in_db=%d returning=%d",
        connection_id, status_filter or "all", total, len(trades),
    )
    if trades:
        sample = trades[0]
        logger.info(
            "[TRADES] Sample: id=%s symbol=%s side=%s pnl=%s status=%s close_time=%s",
            sample.id, sample.symbol, sample.side, sample.pnl, sample.status, sample.close_time,
        )
    else:
        logger.warning(
            "[TRADES] ⚠ ZERO trades found in DB for connection=%s status_filter=%s",
            connection_id, status_filter or "all",
        )

    return trades, total


async def get_daily_stats(
    db: AsyncSession,
    connection_id: uuid.UUID,
    from_date: str | None = None,
    to_date: str | None = None,
) -> list[BrokerDailyStat]:
    query = select(BrokerDailyStat).where(BrokerDailyStat.connection_id == connection_id)

    if from_date:
        query = query.where(BrokerDailyStat.date >= date.fromisoformat(from_date))
    if to_date:
        query = query.where(BrokerDailyStat.date <= date.fromisoformat(to_date))

    result = await db.execute(query.order_by(BrokerDailyStat.date))
    return list(result.scalars().all())
