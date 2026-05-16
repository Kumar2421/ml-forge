-- ============================================================
-- MLForge Model Zoo — SQLite Schema
-- Version: 1.0.0
-- ============================================================

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ── Models ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS models (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    variant     TEXT,
    task        TEXT NOT NULL,
    framework   TEXT NOT NULL,
    source      TEXT NOT NULL DEFAULT 'hf',
    provider    TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    download_url TEXT,                            -- explicit download source URL
    size        INTEGER NOT NULL DEFAULT 0,
    size_label  TEXT NOT NULL DEFAULT '0B',
    tags        TEXT NOT NULL DEFAULT '[]',    -- JSON array
    hardware    TEXT NOT NULL DEFAULT '[]',    -- JSON array
    status      TEXT NOT NULL DEFAULT 'available',
    downloaded  INTEGER NOT NULL DEFAULT 0,
    active_version TEXT,
    local_path  TEXT,
    metrics     TEXT NOT NULL DEFAULT '{}',   -- JSON: latency, mAP, etc.
    downloads   INTEGER DEFAULT 0,
    rating      REAL,
    liked       INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ── Model Versions ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS model_versions (
    version_id   TEXT PRIMARY KEY,
    model_id     TEXT NOT NULL REFERENCES models(id) ON DELETE CASCADE,
    version      TEXT NOT NULL,
    label        TEXT NOT NULL DEFAULT 'Stable',   -- Latest|Stable|Legacy
    description  TEXT,
    metrics      TEXT NOT NULL DEFAULT '{}',       -- JSON: latency, mAP, etc.
    local_path   TEXT,
    downloaded   INTEGER NOT NULL DEFAULT 0,
    release_date TEXT,
    changelog    TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ── Jobs ─────────────────────────────────────────────────-
CREATE TABLE IF NOT EXISTS jobs (
    id         TEXT PRIMARY KEY,
    type       TEXT NOT NULL,                      -- download|benchmark|sync
    status     TEXT NOT NULL DEFAULT 'queued',     -- queued|running|completed|failed|cancelled
    model_id   TEXT REFERENCES models(id),
    model_name TEXT,
    progress   REAL NOT NULL DEFAULT 0.0,          -- 0.0–1.0
    error      TEXT,
    meta       TEXT NOT NULL DEFAULT '{}',         -- JSON extra data
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    started_at TEXT,
    ended_at   TEXT
);

-- ── Projects ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS projects (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    path        TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    last_opened TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'idle'
);

-- ── Session ───────────────────────────────────────────────
-- Stores the currently active project so backend services
-- (e.g. download manager) can link assets into the workspace.
CREATE TABLE IF NOT EXISTS session (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_projects_path ON projects(path);

-- ── Audit Log ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type  TEXT NOT NULL,   -- api_request|download_start|download_ok|error|sync
    model_id    TEXT,
    job_id      TEXT,
    payload     TEXT NOT NULL DEFAULT '{}',  -- JSON
    level       TEXT NOT NULL DEFAULT 'info',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ── FTS (Full-Text Search) ────────────────────────────────
CREATE VIRTUAL TABLE IF NOT EXISTS models_fts USING fts5(
    id UNINDEXED,
    name,
    description,
    tags,
    provider,
    task,
    framework,
    content='models',
    content_rowid='rowid'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS models_fts_insert AFTER INSERT ON models BEGIN
    INSERT INTO models_fts(rowid, id, name, description, tags, provider, task, framework)
    VALUES (new.rowid, new.id, new.name, new.description, new.tags, new.provider, new.task, new.framework);
END;

CREATE TRIGGER IF NOT EXISTS models_fts_delete BEFORE DELETE ON models BEGIN
    DELETE FROM models_fts WHERE rowid = old.rowid;
END;

CREATE TRIGGER IF NOT EXISTS models_fts_update AFTER UPDATE ON models BEGIN
    DELETE FROM models_fts WHERE rowid = old.rowid;
    INSERT INTO models_fts(rowid, id, name, description, tags, provider, task, framework)
    VALUES (new.rowid, new.id, new.name, new.description, new.tags, new.provider, new.task, new.framework);
END;

-- ── Inference History ────────────────────────────────────
CREATE TABLE IF NOT EXISTS inference_history (
    id               TEXT PRIMARY KEY,
    model_id         TEXT NOT NULL REFERENCES models(id) ON DELETE CASCADE,
    model_name       TEXT NOT NULL,
    adapter_type     TEXT NOT NULL,
    timestamp        REAL NOT NULL DEFAULT (unixepoch('now')),
    total_ms         REAL NOT NULL DEFAULT 0.0,
    quality_score    REAL,
    status           TEXT NOT NULL DEFAULT 'ok',
    request_snapshot TEXT NOT NULL DEFAULT '{}'   -- JSON
);

CREATE INDEX IF NOT EXISTS idx_inference_model   ON inference_history(model_id);
CREATE INDEX IF NOT EXISTS idx_inference_time    ON inference_history(timestamp DESC);

-- ── Indexes ───────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_models_task      ON models(task);
CREATE INDEX IF NOT EXISTS idx_models_framework ON models(framework);
CREATE INDEX IF NOT EXISTS idx_models_source    ON models(source);
CREATE INDEX IF NOT EXISTS idx_models_status    ON models(status);
CREATE INDEX IF NOT EXISTS idx_models_downloads ON models(downloads DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_status      ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_model       ON jobs(model_id);
CREATE INDEX IF NOT EXISTS idx_audit_event      ON audit_log(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_time       ON audit_log(created_at DESC);
