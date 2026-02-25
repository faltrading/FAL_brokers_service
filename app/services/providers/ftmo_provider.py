import logging
from datetime import datetime

from app.services.providers.base_provider import AccountInfo, BaseProvider, NormalizedTrade

logger = logging.getLogger(__name__)


class FtmoProvider(BaseProvider):
    provider_name = "ftmo"

    async def validate_credentials(self) -> bool:
        platform = self.credentials.get("platform", "")
        if not platform:
            return False

        if platform == "ctrader":
            return bool(self.credentials.get("ctrader_access_token"))
        elif platform in ("mt4", "mt5"):
            return bool(
                self.credentials.get("metaapi_token")
                and self.credentials.get("metaapi_account_id")
            )
        elif platform == "dxtrade":
            return bool(self.credentials.get("account_number"))

        return False

    async def fetch_trades(
        self, from_date: datetime | None = None, to_date: datetime | None = None
    ) -> list[NormalizedTrade]:
        platform = self.credentials.get("platform", "")
        logger.info(f"FTMO fetch_trades: platform={platform}, from={from_date}, to={to_date}")

        if platform == "ctrader" and self.credentials.get("ctrader_access_token"):
            return await self._fetch_via_ctrader(from_date, to_date)
        elif platform in ("mt4", "mt5") and self.credentials.get("metaapi_token"):
            return await self._fetch_via_metaapi(from_date, to_date)

        return []

    async def _fetch_via_ctrader(
        self, from_date: datetime | None, to_date: datetime | None
    ) -> list[NormalizedTrade]:
        logger.info("FTMO: cTrader Open API integration ready for implementation")
        return []

    async def _fetch_via_metaapi(
        self, from_date: datetime | None, to_date: datetime | None
    ) -> list[NormalizedTrade]:
        logger.info("FTMO: MetaApi integration ready for implementation")
        return []

    async def fetch_account_info(self) -> AccountInfo | None:
        platform = self.credentials.get("platform", "")
        logger.info(f"FTMO fetch_account_info: platform={platform}")
        return AccountInfo(platform=platform, server=self.credentials.get("server", ""))

    async def fetch_open_positions(self) -> list[NormalizedTrade]:
        logger.info("FTMO fetch_open_positions: ready for implementation")
        return []
