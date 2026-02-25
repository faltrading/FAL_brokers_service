# Guida Integrazione API Broker

Questo documento spiega come ottenere le credenziali API per ciascun broker/prop firm supportato e come configurarle nel microservizio.

---

## Architettura connettori

Ogni broker utilizza una o piu piattaforme di trading (MetaTrader 4/5, cTrader, Tradovate, Rithmic). Per accedere ai dati di trading in modo programmatico, si utilizzano le API di queste piattaforme (non dei broker direttamente).

Le credenziali vengono salvate nel database in modo sicuro, cifrate con Fernet (AES-128-CBC), e decifrate solo al momento della sincronizzazione.

---

## 1. FTMO (ftmo.com)

### Piattaforme supportate: cTrader, MT4, MT5, DXtrade

### Opzione A: cTrader Open API (gratuita, consigliata)

FTMO offre account cTrader. La cTrader Open API e' gratuita e permette accesso allo storico trade.

**Come ottenere le credenziali:**
1. Vai su https://openapi.ctrader.com/
2. Registra un account sviluppatore con il tuo cTrader ID
3. Crea una nuova applicazione (Application)
4. Ottieni: `Client ID` e `Client Secret`
5. Implementa il flusso OAuth2 per ottenere l'`Access Token` dell'utente
6. L'Access Token permette di leggere storico trade, posizioni, account info

**Campi credenziali da compilare:**
- `platform`: "ctrader"
- `ctrader_client_id`: Client ID dall'app registrata
- `ctrader_client_secret`: Client Secret
- `ctrader_access_token`: Token OAuth2 dell'utente

**Documentazione:**
- https://help.ctrader.com/open-api/
- https://help.ctrader.com/open-api/account-authentication/

### Opzione B: MetaApi (servizio a pagamento, ~$20-50/mese)

Per account MT4/MT5 su FTMO, MetaApi e' un servizio cloud che si connette ai server MetaTrader.

**Come ottenere le credenziali:**
1. Registrati su https://metaapi.cloud/
2. Ottieni il tuo API Token dalla dashboard
3. Aggiungi il tuo account MetaTrader (server FTMO + login + password MT)
4. MetaApi ti fornira un `Account ID` univoco

**Campi credenziali da compilare:**
- `platform`: "mt4" o "mt5"
- `metaapi_token`: API Token MetaApi
- `metaapi_account_id`: Account ID assegnato da MetaApi
- `server`: Nome del server (es. "FTMO-Demo2")
- `account_number`: Numero login MetaTrader

**Documentazione:**
- https://metaapi.cloud/docs/client/
- https://pypi.org/project/metaapi-cloud-sdk/

**SDK Python:**
- `pip install metaapi-cloud-sdk` (per trade history)
- `pip install metaapi-cloud-metastats-sdk` (per statistiche)

---

## 2. Fintokei (fintokei.com)

### Piattaforme supportate: cTrader, MT4, MT5

### Opzione A: cTrader Open API (stessa procedura di FTMO)

Fintokei utilizza cTrader come piattaforma principale. La procedura e' identica a FTMO.

**Campi credenziali:** stessi di FTMO con platform "ctrader"

### Opzione B: MetaApi (per account MT4/MT5)

Stessa procedura di FTMO. Cambiare solo il nome del server nel setup MetaApi.

**Campi credenziali:** stessi di FTMO con platform "mt4" o "mt5"

---

## 3. TopStep (topstep.com)

### Piattaforme supportate: TopStepX (ProjectX), Tradovate, NinjaTrader

### Opzione A: TopStepX / ProjectX API (consigliata, $29/mese)

TopStep ha lanciato la propria piattaforma TopStepX, basata su ProjectX, con API REST e WebSocket.

**Come ottenere le credenziali:**
1. Vai su https://help.topstep.com/en/articles/11187768-topstepx-api-access
2. Acquista l'abbonamento API Access ($29/mese)
3. Usa il codice promo "topstep" per lo sconto
4. Riceverai: API Key e API Secret
5. Accedi alla dashboard ProjectX per gestire il token

**Campi credenziali da compilare:**
- `platform`: "topstepx"
- `topstepx_api_key`: API Key fornita da ProjectX
- `topstepx_api_secret`: API Secret
- `account_number`: Numero account TopStep

**Documentazione:**
- https://help.topstep.com/en/articles/11187768-topstepx-api-access
- Per domande di billing/subscription, contattare ProjectX Support

### Opzione B: Tradovate API

Se l'utente usa Tradovate come piattaforma con TopStep.

**Come ottenere le credenziali:**
1. Accedi al tuo account Tradovate
2. Le credenziali sono username, password e device ID
3. L'API Tradovate usa REST + WebSocket

**Campi credenziali da compilare:**
- `platform`: "tradovate"
- `tradovate_username`: Username
- `tradovate_password`: Password
- `tradovate_device_id`: Device ID (generato dal client)

---

## 4. Tradeify (tradeify.co)

### Piattaforme supportate: Tradovate, NinjaTrader, Rithmic

### Opzione A: Tradovate API

Tradeify supporta Tradovate come piattaforma.

**Campi credenziali:** stessi di TopStep Opzione B (Tradovate)

### Opzione B: Rithmic

Per utenti che usano Rithmic come data feed.

**Campi credenziali da compilare:**
- `platform`: "rithmic"
- `rithmic_username`: Username Rithmic
- `rithmic_password`: Password Rithmic
- `account_number`: Numero account

**Nota:** L'integrazione Rithmic richiede un protocollo proprietario. Si consiglia di usare librerie come `rithmic-api-python` o il sync Rithmic di servizi terzi.

---

## 5. Lucid Trading (lucidtrading.com)

### Piattaforme supportate: Tradovate, NinjaTrader, Rithmic, Quantower

### Opzione A: Tradovate API (se usa Tradovate)

**Campi credenziali:** stessi di TopStep/Tradeify Tradovate

### Opzione B: Rithmic (se usa Rithmic o Quantower con feed Rithmic)

Lucid Trading usa Rithmic come data feed principale.

**Campi credenziali:** stessi di Tradeify Opzione B (Rithmic)

---

## Alternativa universale: Import CSV

Per TUTTI i broker, e' sempre disponibile l'import manuale via file CSV.

**Formati supportati automaticamente:**
- **MetaTrader 4**: Export dalla scheda "Account History"
- **MetaTrader 5**: Export dalla scheda "History"
- **cTrader**: Export dalla sezione "History" / "Trade History"
- **Tradovate**: Export ordini/fill dalla piattaforma
- **Formato generico**: CSV con colonne: symbol, side, open_time, close_time, open_price, close_price, volume, pnl

**Come esportare:**
1. Apri la piattaforma di trading
2. Vai alla sezione storico/history
3. Seleziona il periodo desiderato
4. Esporta come CSV/Excel
5. Carica il file tramite l'endpoint `POST /api/v1/broker/connections/{id}/import-csv`

---

## Riepilogo API per broker

| Broker | Piattaforma | API | Costo | Tipo |
|--------|-------------|-----|-------|------|
| FTMO | cTrader | cTrader Open API | Gratuita | OAuth2 REST |
| FTMO | MT4/MT5 | MetaApi | ~$20-50/mese | REST + SDK |
| Fintokei | cTrader | cTrader Open API | Gratuita | OAuth2 REST |
| Fintokei | MT4/MT5 | MetaApi | ~$20-50/mese | REST + SDK |
| TopStep | TopStepX | ProjectX API | $29/mese | REST + WebSocket |
| TopStep | Tradovate | Tradovate API | Inclusa | REST + WebSocket |
| Tradeify | Tradovate | Tradovate API | Inclusa | REST + WebSocket |
| Tradeify | Rithmic | Rithmic Protocol | Inclusa | Proprietario |
| Lucid | Tradovate | Tradovate API | Inclusa | REST + WebSocket |
| Lucid | Rithmic | Rithmic Protocol | Inclusa | Proprietario |
| TUTTI | Qualsiasi | CSV Import | Gratuita | Upload file |

---

## Sicurezza credenziali

- Le credenziali vengono cifrate con Fernet (AES-128-CBC) prima del salvataggio in database
- La chiave di cifratura deriva dalla variabile d'ambiente `BROKER_ENCRYPTION_KEY` (o dal JWT secret come fallback)
- Le credenziali non vengono MAI esposte nelle risposte API
- Le credenziali vengono decifrate SOLO durante la sincronizzazione
- I log non contengono MAI credenziali o dati sensibili
