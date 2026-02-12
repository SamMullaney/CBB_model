-- 020_arb_alerts.sql  –  Dedupe table for arb alerts
-- Prevents the same arb from being sent to Discord more than once.

CREATE TABLE IF NOT EXISTS arb_alerts_sent (
    id            bigserial       PRIMARY KEY,
    fingerprint   text            NOT NULL,
    sent_at       timestamptz     NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_arb_alerts_fingerprint
    ON arb_alerts_sent (fingerprint);
