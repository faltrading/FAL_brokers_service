from fastapi import HTTPException, status


class BrokerServiceError(HTTPException):
    def __init__(self, detail: str, status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR):
        super().__init__(status_code=status_code, detail=detail)


class ConnectionNotFoundError(BrokerServiceError):
    def __init__(self):
        super().__init__(detail="Connessione broker non trovata", status_code=status.HTTP_404_NOT_FOUND)


class ProviderNotSupportedError(BrokerServiceError):
    def __init__(self, provider: str = ""):
        detail = f"Provider '{provider}' non supportato" if provider else "Provider non supportato"
        super().__init__(detail=detail, status_code=status.HTTP_400_BAD_REQUEST)


class SyncInProgressError(BrokerServiceError):
    def __init__(self):
        super().__init__(detail="Sincronizzazione già in corso", status_code=status.HTTP_409_CONFLICT)


class CredentialsInvalidError(BrokerServiceError):
    def __init__(self):
        super().__init__(detail="Credenziali broker non valide", status_code=status.HTTP_400_BAD_REQUEST)


class UnauthorizedAccessError(BrokerServiceError):
    def __init__(self):
        super().__init__(detail="Accesso non autorizzato a questa connessione", status_code=status.HTTP_403_FORBIDDEN)


class InsufficientPermissionsError(BrokerServiceError):
    def __init__(self):
        super().__init__(detail="Permessi insufficienti", status_code=status.HTTP_403_FORBIDDEN)


class DuplicateConnectionError(BrokerServiceError):
    def __init__(self):
        super().__init__(
            detail="Connessione già esistente per questo broker e account",
            status_code=status.HTTP_409_CONFLICT,
        )


class CsvParsingError(BrokerServiceError):
    def __init__(self, detail: str = "Errore nel parsing del file CSV"):
        super().__init__(detail=detail, status_code=status.HTTP_400_BAD_REQUEST)
