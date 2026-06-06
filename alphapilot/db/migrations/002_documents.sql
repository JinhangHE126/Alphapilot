CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    format TEXT NOT NULL,
    source TEXT NOT NULL,
    source_url TEXT,
    title TEXT,
    retrieved_at TEXT NOT NULL,
    as_of_date TEXT,
    content_hash TEXT NOT NULL UNIQUE,
    raw_content BLOB,
    storage_path TEXT,
    ingested_to_faiss INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_documents_symbol ON documents(symbol);
CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(content_hash);
CREATE INDEX IF NOT EXISTS idx_documents_faiss ON documents(ingested_to_faiss);