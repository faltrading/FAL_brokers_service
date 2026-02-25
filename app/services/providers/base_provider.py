from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class NormalizedTrade:
    external_trade_id: str | None = None
    symbol: str = ""
    side: str = ""
    open_time: datetime | None = None
    close_time: datetime | None = None
    open_price: float = 0
    close_price: float | None = None
    volume: float = 0
    pnl: float | None = None
    commission: float = 0
    swap: float = 0
    status: str = "closed"
    metadata: dict = field(default_factory=dict)


@dataclass
class AccountInfo:
    account_id: str = ""
    account_name: str = ""
    balance: float = 0
    equity: float = 0
    currency: str = "USD"
    server: str = ""
    platform: str = ""
    metadata: dict = field(default_factory=dict)


PROVIDER_CREDENTIAL_FIELDS: dict[str, list[dict]] = {
    "ftmo": [
        {"name": "platform", "type": "select", "options": ["ctrader", "mt4", "mt5", "dxtrade"], "required": True,
         "description": "Piattaforma di trading utilizzata su FTMO"},
        {"name": "ctrader_client_id", "type": "string", "required": False,
         "description": "cTrader Open API Client ID (se usi cTrader)"},
        {"name": "ctrader_client_secret", "type": "string", "required": False,
         "description": "cTrader Open API Client Secret"},
        {"name": "ctrader_access_token", "type": "string", "required": False,
         "description": "cTrader OAuth2 Access Token"},
        {"name": "metaapi_token", "type": "string", "required": False,
         "description": "MetaApi API Token (se usi MT4/MT5)"},
        {"name": "metaapi_account_id", "type": "string", "required": False,
         "description": "MetaApi Account ID per il tuo account FTMO"},
        {"name": "server", "type": "string", "required": False,
         "description": "Nome del server broker (es. FTMO-Demo)"},
        {"name": "account_number", "type": "string", "required": False,
         "description": "Numero account sulla piattaforma"},
    ],
    "fintokei": [
        {"name": "platform", "type": "select", "options": ["ctrader", "mt4", "mt5"], "required": True,
         "description": "Piattaforma di trading utilizzata su Fintokei"},
        {"name": "ctrader_client_id", "type": "string", "required": False,
         "description": "cTrader Open API Client ID"},
        {"name": "ctrader_client_secret", "type": "string", "required": False,
         "description": "cTrader Open API Client Secret"},
        {"name": "ctrader_access_token", "type": "string", "required": False,
         "description": "cTrader OAuth2 Access Token"},
        {"name": "metaapi_token", "type": "string", "required": False,
         "description": "MetaApi API Token (se usi MT4/MT5)"},
        {"name": "metaapi_account_id", "type": "string", "required": False,
         "description": "MetaApi Account ID"},
        {"name": "server", "type": "string", "required": False,
         "description": "Nome del server broker"},
        {"name": "account_number", "type": "string", "required": False,
         "description": "Numero account sulla piattaforma"},
    ],
    "topstep": [
        {"name": "platform", "type": "select", "options": ["topstepx", "tradovate", "ninjatrader"], "required": True,
         "description": "Piattaforma di trading utilizzata su TopStep"},
        {"name": "topstepx_api_key", "type": "string", "required": False,
         "description": "TopStepX/ProjectX API Key ($29/mese da ProjectX)"},
        {"name": "topstepx_api_secret", "type": "string", "required": False,
         "description": "TopStepX/ProjectX API Secret"},
        {"name": "tradovate_username", "type": "string", "required": False,
         "description": "Username Tradovate (se usi Tradovate)"},
        {"name": "tradovate_password", "type": "string", "required": False,
         "description": "Password Tradovate"},
        {"name": "tradovate_device_id", "type": "string", "required": False,
         "description": "Device ID Tradovate (per API auth)"},
        {"name": "account_number", "type": "string", "required": False,
         "description": "Numero account TopStep"},
    ],
    "tradeify": [
        {"name": "platform", "type": "select", "options": ["tradovate", "ninjatrader", "rithmic"], "required": True,
         "description": "Piattaforma di trading utilizzata su Tradeify"},
        {"name": "tradovate_username", "type": "string", "required": False,
         "description": "Username Tradovate"},
        {"name": "tradovate_password", "type": "string", "required": False,
         "description": "Password Tradovate"},
        {"name": "tradovate_device_id", "type": "string", "required": False,
         "description": "Device ID Tradovate"},
        {"name": "rithmic_username", "type": "string", "required": False,
         "description": "Username Rithmic (se usi Rithmic)"},
        {"name": "rithmic_password", "type": "string", "required": False,
         "description": "Password Rithmic"},
        {"name": "account_number", "type": "string", "required": False,
         "description": "Numero account Tradeify"},
    ],
    "lucidtrading": [
        {"name": "platform", "type": "select", "options": ["tradovate", "ninjatrader", "rithmic", "quantower"],
         "required": True,
         "description": "Piattaforma di trading utilizzata su Lucid Trading"},
        {"name": "rithmic_username", "type": "string", "required": False,
         "description": "Username Rithmic"},
        {"name": "rithmic_password", "type": "string", "required": False,
         "description": "Password Rithmic"},
        {"name": "tradovate_username", "type": "string", "required": False,
         "description": "Username Tradovate (se usi Tradovate)"},
        {"name": "tradovate_password", "type": "string", "required": False,
         "description": "Password Tradovate"},
        {"name": "tradovate_device_id", "type": "string", "required": False,
         "description": "Device ID Tradovate"},
        {"name": "account_number", "type": "string", "required": False,
         "description": "Numero account Lucid Trading"},
    ],
}


class BaseProvider(ABC):
    provider_name: str = ""

    def __init__(self, credentials: dict):
        self.credentials = credentials

    @abstractmethod
    async def validate_credentials(self) -> bool:
        pass

    @abstractmethod
    async def fetch_trades(self, from_date: datetime | None = None, to_date: datetime | None = None) -> list[NormalizedTrade]:
        pass

    @abstractmethod
    async def fetch_account_info(self) -> AccountInfo | None:
        pass

    @abstractmethod
    async def fetch_open_positions(self) -> list[NormalizedTrade]:
        pass

    @classmethod
    def get_credential_fields(cls) -> list[dict]:
        return PROVIDER_CREDENTIAL_FIELDS.get(cls.provider_name, [])
