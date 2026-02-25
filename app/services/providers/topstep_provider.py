import logging
from datetime import datetime

from app.services.providers.base_provider import AccountInfo, BaseProvider, NormalizedTrade

logger = logging.getLogger(__name__)


class TopstepProvider(BaseProvider):
    provider_name = "topstep"

    async def validate_credentials(self) -> bool:
        platform = self.credentials.get("platform", "")
        if not platform:
            return False

        if platform == "topstepx":
            return bool(
                self.credentials.get("topstepx_api_key")
                and self.credentials.get("topstepx_api_secret")
            )
        elif platform == "tradovate":
            return bool(
                self.credentials.get("tradovate_username")
                and self.credentials.get("tradovate_password")
            )

        return False

    async def fetch_trades(
        self, from_date: datetime | None = None, to_date: datetime | None = None
    ) -> list[NormalizedTrade]:
        platform = self.credentials.get("platform", "")
        logger.info(f"TopStep fetch_trades: platform={platform}, from={from_date}, to={to_date}")

        if platform == "topstepx" and self.credentials.get("topstepx_api_key"):
            return await self._fetch_via_projectx(from_date, to_date)
        elif platform == "tradovate" and self.credentials.get("tradovate_username"):
            return await self._fetch_via_tradovate(from_date, to_date)

        return []

    async def _fetch_via_projectx(
        self, from_date: datetime | None, to_date: datetime | None
    ) -> list[NormalizedTrade]:
        logger.info("TopStep: ProjectX API integration ready for implementation")
        return []

    async def _fetch_via_tradovate(
        self, from_date: datetime | None, to_date: datetime | None
    ) -> list[NormalizedTrade]:
        logger.info("TopStep: Tradovate API integration ready for implementation")
        return []

    async def fetch_account_info(self) -> AccountInfo | None:
        platform = self.credentials.get("platform", "")
        logger.info(f"TopStep fetch_account_info: platform={platform}")
        return AccountInfo(platform=platform)

    async def fetch_open_positions(self) -> list[NormalizedTrade]:
        logger.info("TopStep fetch_open_positions: ready for implementation")
        return []
