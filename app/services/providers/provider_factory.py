from app.core.exceptions import ProviderNotSupportedError
from app.services.providers.base_provider import BaseProvider, PROVIDER_CREDENTIAL_FIELDS
from app.services.providers.fintokei_provider import FintokeiProvider
from app.services.providers.ftmo_provider import FtmoProvider
from app.services.providers.lucidtrading_provider import LucidtradingProvider
from app.services.providers.topstep_provider import TopstepProvider
from app.services.providers.tradeify_provider import TradeifyProvider

_PROVIDERS: dict[str, type[BaseProvider]] = {
    "ftmo": FtmoProvider,
    "fintokei": FintokeiProvider,
    "topstep": TopstepProvider,
    "tradeify": TradeifyProvider,
    "lucidtrading": LucidtradingProvider,
}

SUPPORTED_PROVIDERS = list(_PROVIDERS.keys())


def get_provider(provider_name: str, credentials: dict) -> BaseProvider:
    provider_class = _PROVIDERS.get(provider_name)
    if not provider_class:
        raise ProviderNotSupportedError(provider_name)
    return provider_class(credentials)


def get_credential_fields(provider_name: str) -> list[dict]:
    if provider_name not in _PROVIDERS:
        raise ProviderNotSupportedError(provider_name)
    return PROVIDER_CREDENTIAL_FIELDS.get(provider_name, [])
