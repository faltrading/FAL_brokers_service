/*
  # Create Broker Data Aggregation Tables

  1. New Tables
    - `broker_connections`
      - `id` (uuid, primary key) - Unique connection identifier
      - `user_id` (uuid, not null) - Owner user from auth microservice
      - `provider` (varchar) - Broker name: ftmo, fintokei, topstep, tradeify, lucidtrading
      - `account_identifier` (varchar) - Account reference at the broker
      - `credentials_encrypted` (text) - Fernet-encrypted API credentials (never exposed)
      - `connection_status` (varchar) - active, inactive, error
      - `last_sync_at` (timestamptz) - Last successful sync timestamp
      - `last_sync_status` (varchar) - success, failed, in_progress
      - `last_sync_error` (text) - Last sync error message (internal)
      - `metadata` (jsonb) - Flexible extra data per connection
      - `created_at`, `updated_at` (timestamptz)
      - Unique constraint on (user_id, provider, account_identifier)

    - `broker_trades`
      - `id` (uuid, primary key) - Unique trade identifier
      - `connection_id` (uuid, FK cascade) - Parent broker connection
      - `user_id` (uuid) - Owner user
      - `provider` (varchar) - Broker name (denormalized for query performance)
      - `external_trade_id` (varchar) - Trade ID from the broker platform
      - `symbol` (varchar) - Trading instrument (e.g., EURUSD, US30, XAUUSD)
      - `side` (varchar) - buy or sell
      - `open_time`, `close_time` (timestamptz) - Trade timestamps
      - `open_price`, `close_price` (numeric) - Entry and exit prices
      - `volume` (numeric) - Lot size / contract size
      - `pnl` (numeric) - Net profit/loss
      - `commission`, `swap` (numeric) - Trading costs
      - `status` (varchar) - open or closed
      - `metadata` (jsonb) - Extra data (stop loss, take profit, etc.)
      - `created_at`, `updated_at` (timestamptz)

    - `broker_daily_stats`
      - `id` (uuid, primary key) - Unique stat record
      - `connection_id` (uuid, FK cascade) - Parent broker connection
      - `user_id` (uuid) - Owner user
      - `provider` (varchar) - Broker name
      - `date` (date) - Trading day
      - `total_pnl` (numeric) - Day total P&L
      - `trade_count` (int) - Number of trades
      - `winning_trades`, `losing_trades` (int) - Win/loss counts
      - `volume` (numeric) - Total volume traded
      - `metadata` (jsonb) - Extra aggregated data
      - `created_at` (timestamptz)
      - Unique constraint on (connection_id, date)

    - `broker_sync_logs`
      - `id` (uuid, primary key) - Unique log entry
      - `connection_id` (uuid, FK cascade) - Parent broker connection
      - `started_at`, `completed_at` (timestamptz) - Sync timestamps
      - `status` (varchar) - running, success, failed
      - `trades_synced` (int) - Number of trades synced
      - `error_message` (text) - Error details if failed

  2. Indexes
    - broker_connections: user_id, provider
    - broker_trades: (connection_id, close_time), (user_id, provider), symbol, status
    - broker_daily_stats: user_id, date
    - broker_sync_logs: connection_id, status

  3. Security
    - RLS enabled on all tables
    - Service role has full access (application uses service_role key)

  4. Notes
    - Credentials are encrypted at application level with Fernet before storage
    - Daily stats are computed from trades and cached for dashboard performance
    - Sync logs provide audit trail for data synchronization operations
*/

CREATE TABLE IF NOT EXISTS broker_connections (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  provider varchar(50) NOT NULL,
  account_identifier varchar(255) NOT NULL,
  credentials_encrypted text,
  connection_status varchar(20) NOT NULL DEFAULT 'active',
  last_sync_at timestamptz,
  last_sync_status varchar(20),
  last_sync_error text,
  metadata jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_user_provider_account UNIQUE (user_id, provider, account_identifier)
);

CREATE TABLE IF NOT EXISTS broker_trades (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  connection_id uuid NOT NULL REFERENCES broker_connections(id) ON DELETE CASCADE,
  user_id uuid NOT NULL,
  provider varchar(50) NOT NULL,
  external_trade_id varchar(255),
  symbol varchar(50) NOT NULL,
  side varchar(10) NOT NULL,
  open_time timestamptz NOT NULL,
  close_time timestamptz,
  open_price numeric(18, 8) NOT NULL,
  close_price numeric(18, 8),
  volume numeric(18, 8) NOT NULL,
  pnl numeric(18, 4),
  commission numeric(18, 4) NOT NULL DEFAULT 0,
  swap numeric(18, 4) NOT NULL DEFAULT 0,
  status varchar(20) NOT NULL DEFAULT 'closed',
  metadata jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS broker_daily_stats (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  connection_id uuid NOT NULL REFERENCES broker_connections(id) ON DELETE CASCADE,
  user_id uuid NOT NULL,
  provider varchar(50) NOT NULL,
  date date NOT NULL,
  total_pnl numeric(18, 4) NOT NULL DEFAULT 0,
  trade_count integer NOT NULL DEFAULT 0,
  winning_trades integer NOT NULL DEFAULT 0,
  losing_trades integer NOT NULL DEFAULT 0,
  volume numeric(18, 8) NOT NULL DEFAULT 0,
  metadata jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_connection_date UNIQUE (connection_id, date)
);

CREATE TABLE IF NOT EXISTS broker_sync_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  connection_id uuid NOT NULL REFERENCES broker_connections(id) ON DELETE CASCADE,
  started_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz,
  status varchar(20) NOT NULL DEFAULT 'running',
  trades_synced integer NOT NULL DEFAULT 0,
  error_message text
);

CREATE INDEX IF NOT EXISTS idx_broker_connections_user ON broker_connections(user_id);
CREATE INDEX IF NOT EXISTS idx_broker_connections_provider ON broker_connections(provider);

CREATE INDEX IF NOT EXISTS idx_broker_trades_connection_close ON broker_trades(connection_id, close_time DESC);
CREATE INDEX IF NOT EXISTS idx_broker_trades_user_provider ON broker_trades(user_id, provider);
CREATE INDEX IF NOT EXISTS idx_broker_trades_symbol ON broker_trades(symbol);
CREATE INDEX IF NOT EXISTS idx_broker_trades_status ON broker_trades(status);

CREATE INDEX IF NOT EXISTS idx_broker_daily_stats_user ON broker_daily_stats(user_id);
CREATE INDEX IF NOT EXISTS idx_broker_daily_stats_date ON broker_daily_stats(date);

CREATE INDEX IF NOT EXISTS idx_broker_sync_logs_connection ON broker_sync_logs(connection_id);
CREATE INDEX IF NOT EXISTS idx_broker_sync_logs_status ON broker_sync_logs(status);

ALTER TABLE broker_connections ENABLE ROW LEVEL SECURITY;
ALTER TABLE broker_trades ENABLE ROW LEVEL SECURITY;
ALTER TABLE broker_daily_stats ENABLE ROW LEVEL SECURITY;
ALTER TABLE broker_sync_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access to broker_connections"
  ON broker_connections FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access to broker_trades"
  ON broker_trades FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access to broker_daily_stats"
  ON broker_daily_stats FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access to broker_sync_logs"
  ON broker_sync_logs FOR ALL TO service_role USING (true) WITH CHECK (true);
