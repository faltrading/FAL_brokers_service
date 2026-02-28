import csv
import io
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import CsvParsingError
from app.models.broker_connection import BrokerConnection
from app.models.broker_trade import BrokerTrade
from app.services.stats_service import recalculate_daily_stats

logger = logging.getLogger(__name__)

MT4_COLUMNS = {"ticket", "open time", "type", "size", "item", "price", "s / l", "t / p", "close time", "close price", "commission", "swap", "profit"}
MT5_COLUMNS = {"position", "time", "type", "symbol", "volume", "price", "profit", "commission", "swap"}
CTRADER_COLUMNS = {"position id", "symbol", "direction", "volume", "open time", "close time", "open price", "close price", "net profit"}
TRADOVATE_COLUMNS = {"orderid", "symbol", "side", "qty", "filltime", "avgfillprice"}
GENERIC_COLUMNS = {"symbol", "side", "open_time", "close_time", "open_price", "close_price", "volume", "pnl"}


def _detect_format(headers: list[str]) -> str:
    lower_headers = {h.strip().lower() for h in headers}

    if lower_headers >= {"ticket", "open time", "close time", "item", "profit"}:
        return "mt4"
    if lower_headers >= {"position", "time", "symbol", "profit"}:
        return "mt5"
    if lower_headers >= {"position id", "symbol", "direction", "net profit"}:
        return "ctrader"
    if lower_headers >= {"orderid", "symbol", "side", "filltime"}:
        return "tradovate"
    if lower_headers >= {"symbol", "side", "pnl"}:
        return "generic"

    return "unknown"


def _parse_datetime(value: str) -> datetime | None:
    if not value or not value.strip():
        return None
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y.%m.%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M",
        "%Y.%m.%d %H:%M",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M",
        "%d/%m/%Y %H:%M:%S",
    ]
    value = value.strip()
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _parse_float(value: str) -> float:
    if not value or not value.strip():
        return 0.0
    cleaned = value.strip().replace(",", "").replace(" ", "")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _normalize_side(raw: str) -> str:
    lower = raw.strip().lower()
    if lower in ("buy", "long", "b"):
        return "buy"
    if lower in ("sell", "short", "s"):
        return "sell"
    return lower


def _parse_mt4_row(row: dict) -> dict | None:
    try:
        trade_type = row.get("type", "").strip().lower()
        if trade_type not in ("buy", "sell"):
            return None

        return {
            "external_trade_id": row.get("ticket", "").strip(),
            "symbol": row.get("item", row.get("symbol", "")).strip(),
            "side": _normalize_side(trade_type),
            "open_time": _parse_datetime(row.get("open time", "")),
            "close_time": _parse_datetime(row.get("close time", "")),
            "open_price": _parse_float(row.get("price", "0")),
            "close_price": _parse_float(row.get("close price", "0")),
            "volume": _parse_float(row.get("size", row.get("lots", "0"))),
            "pnl": _parse_float(row.get("profit", "0")),
            "commission": _parse_float(row.get("commission", "0")),
            "swap": _parse_float(row.get("swap", "0")),
        }
    except Exception:
        return None


def _parse_mt5_row(row: dict) -> dict | None:
    try:
        trade_type = row.get("type", "").strip().lower()
        if "buy" not in trade_type and "sell" not in trade_type:
            return None

        side = "buy" if "buy" in trade_type else "sell"

        return {
            "external_trade_id": row.get("position", row.get("deal", "")).strip(),
            "symbol": row.get("symbol", "").strip(),
            "side": side,
            "open_time": _parse_datetime(row.get("time", "")),
            "close_time": _parse_datetime(row.get("time", "")),
            "open_price": _parse_float(row.get("price", "0")),
            "close_price": _parse_float(row.get("price", "0")),
            "volume": _parse_float(row.get("volume", row.get("lots", "0"))),
            "pnl": _parse_float(row.get("profit", "0")),
            "commission": _parse_float(row.get("commission", "0")),
            "swap": _parse_float(row.get("swap", "0")),
        }
    except Exception:
        return None


def _parse_ctrader_row(row: dict) -> dict | None:
    try:
        return {
            "external_trade_id": row.get("position id", "").strip(),
            "symbol": row.get("symbol", "").strip(),
            "side": _normalize_side(row.get("direction", "")),
            "open_time": _parse_datetime(row.get("open time", "")),
            "close_time": _parse_datetime(row.get("close time", "")),
            "open_price": _parse_float(row.get("open price", "0")),
            "close_price": _parse_float(row.get("close price", "0")),
            "volume": _parse_float(row.get("volume", row.get("quantity", "0"))),
            "pnl": _parse_float(row.get("net profit", row.get("profit", "0"))),
            "commission": _parse_float(row.get("commission", "0")),
            "swap": _parse_float(row.get("swap", "0")),
        }
    except Exception:
        return None


def _parse_tradovate_row(row: dict) -> dict | None:
    try:
        return {
            "external_trade_id": row.get("orderid", row.get("order id", "")).strip(),
            "symbol": row.get("symbol", row.get("contract", "")).strip(),
            "side": _normalize_side(row.get("side", row.get("action", ""))),
            "open_time": _parse_datetime(row.get("filltime", row.get("fill time", ""))),
            "close_time": _parse_datetime(row.get("filltime", row.get("fill time", ""))),
            "open_price": _parse_float(row.get("avgfillprice", row.get("fill price", "0"))),
            "close_price": _parse_float(row.get("avgfillprice", row.get("fill price", "0"))),
            "volume": _parse_float(row.get("qty", row.get("quantity", "0"))),
            "pnl": _parse_float(row.get("pnl", row.get("profit", "0"))),
            "commission": _parse_float(row.get("commission", "0")),
            "swap": 0,
        }
    except Exception:
        return None


def _parse_generic_row(row: dict) -> dict | None:
    try:
        return {
            "external_trade_id": row.get("id", row.get("trade_id", "")),
            "symbol": row.get("symbol", row.get("instrument", "")).strip(),
            "side": _normalize_side(row.get("side", row.get("direction", ""))),
            "open_time": _parse_datetime(row.get("open_time", row.get("entry_time", ""))),
            "close_time": _parse_datetime(row.get("close_time", row.get("exit_time", ""))),
            "open_price": _parse_float(row.get("open_price", row.get("entry_price", "0"))),
            "close_price": _parse_float(row.get("close_price", row.get("exit_price", "0"))),
            "volume": _parse_float(row.get("volume", row.get("lots", row.get("size", "0")))),
            "pnl": _parse_float(row.get("pnl", row.get("profit", row.get("net_pnl", "0")))),
            "commission": _parse_float(row.get("commission", "0")),
            "swap": _parse_float(row.get("swap", "0")),
        }
    except Exception:
        return None


_PARSERS = {
    "mt4": _parse_mt4_row,
    "mt5": _parse_mt5_row,
    "ctrader": _parse_ctrader_row,
    "tradovate": _parse_tradovate_row,
    "generic": _parse_generic_row,
}


async def import_csv(
    db: AsyncSession,
    connection: BrokerConnection,
    file_content: bytes,
) -> int:
    try:
        text = file_content.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = file_content.decode("latin-1")
        except UnicodeDecodeError:
            raise CsvParsingError("Impossibile decodificare il file CSV")

    try:
        dialect = csv.Sniffer().sniff(text[:2048])
    except csv.Error:
        dialect = csv.excel

    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        raise CsvParsingError("Il file CSV non contiene intestazioni valide")

    headers = [h.strip().lower() for h in reader.fieldnames]
    fmt = _detect_format(headers)

    if fmt == "unknown":
        raise CsvParsingError(
            f"Formato CSV non riconosciuto. Intestazioni trovate: {', '.join(headers[:10])}"
        )

    parser = _PARSERS[fmt]
    trades_imported = 0

    for row_num, raw_row in enumerate(reader, start=2):
        row = {k.strip().lower(): v for k, v in raw_row.items() if k}
        parsed = parser(row)
        if not parsed:
            continue

        if not parsed.get("symbol") or not parsed.get("open_time"):
            continue

        close_time = parsed.get("close_time")
        status = "closed" if close_time else "open"

        trade = BrokerTrade(
            connection_id=connection.id,
            user_id=connection.user_id,
            provider=connection.provider,
            external_trade_id=parsed.get("external_trade_id") or None,
            symbol=parsed["symbol"],
            side=parsed.get("side", "buy"),
            open_time=parsed["open_time"],
            close_time=close_time,
            open_price=parsed.get("open_price", 0),
            close_price=parsed.get("close_price"),
            volume=parsed.get("volume", 0),
            pnl=parsed.get("pnl"),
            commission=parsed.get("commission", 0),
            swap=parsed.get("swap", 0),
            status=status,
            metadata_json={"source": "csv"},
        )
        db.add(trade)
        trades_imported += 1

    await db.commit()

    if trades_imported > 0:
        # Update connection timestamp so the dashboard shows the correct "Last import" time
        connection.last_sync_at = datetime.now(timezone.utc)
        connection.last_sync_status = "success"
        await db.commit()
        await recalculate_daily_stats(db, connection)

    logger.info(f"CSV import: {trades_imported} trades imported (format: {fmt})")
    return trades_imported
