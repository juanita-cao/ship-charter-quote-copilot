CREATE TABLE quote_records (
    id                      SERIAL PRIMARY KEY,
    created_at              TIMESTAMPTZ DEFAULT now(),
    route                   TEXT NOT NULL,
    cargo_description       TEXT,
    quantity                NUMERIC,
    freight_rate            NUMERIC,
    commission_rate         NUMERIC,
    market_benchmark        NUMERIC,
    shipowner_asking_tce    NUMERIC,
    tce                     NUMERIC,
    profit_margin_pct       NUMERIC,
    decision                TEXT,
    quote_input_snapshot    JSONB,   -- full QuoteInput, for audit/reference
    deal_decision_snapshot  JSONB,   -- full DealDecision
    reverse_quote_snapshot  JSONB    -- full ReverseQuoteResult; NULL if reverse quote unused
);
