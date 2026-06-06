CREATE TABLE IF NOT EXISTS facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    field TEXT NOT NULL,
    value TEXT NOT NULL,
    unit TEXT NOT NULL,
    period TEXT NOT NULL,
    source TEXT NOT NULL,
    source_url TEXT,
    as_of_date TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    expires_at TEXT,
    confidence REAL NOT NULL,
    confidence_tier TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    version INTEGER NOT NULL DEFAULT 1,
    superseded_by INTEGER,
    raw_payload_hash TEXT,
    UNIQUE(symbol, field, period, source, as_of_date),
    FOREIGN KEY (superseded_by) REFERENCES facts(id)
);

CREATE INDEX IF NOT EXISTS idx_facts_symbol_field ON facts(symbol, field);
CREATE INDEX IF NOT EXISTS idx_facts_status_expires ON facts(status, expires_at);
CREATE INDEX IF NOT EXISTS idx_facts_retrieved ON facts(retrieved_at);