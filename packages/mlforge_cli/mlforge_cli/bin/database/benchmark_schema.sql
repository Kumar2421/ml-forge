-- ============================================================
-- MLForge Benchmark Bridge — SQLite Schema
-- Version: 1.0.0
-- ============================================================

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ── Benchmark Jobs ────────────────────────────────────────────────────────────
-- Tracks every benchmark run from queued → running → completed/failed.
-- config stores the full BenchmarkContext JSON for full reproducibility.
CREATE TABLE IF NOT EXISTS benchmark_jobs (
    id          TEXT PRIMARY KEY,
    model_id    TEXT NOT NULL,
    dataset_id  TEXT NOT NULL,
    task        TEXT NOT NULL,
    framework   TEXT NOT NULL,
    hardware    TEXT NOT NULL DEFAULT 'cpu',
    precision   TEXT NOT NULL DEFAULT 'FP32',
    batch_size  INTEGER NOT NULL DEFAULT 1,
    config      TEXT NOT NULL DEFAULT '{}',      -- full BenchmarkContext JSON
    status      TEXT NOT NULL DEFAULT 'queued',  -- queued|running|completed|failed
    progress    REAL NOT NULL DEFAULT 0.0,       -- 0.0–1.0
    logs        TEXT NOT NULL DEFAULT '[]',      -- JSON array of timestamped log strings
    error       TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    started_at  TEXT,
    ended_at    TEXT
);

-- ── Benchmark Results ─────────────────────────────────────────────────────────
-- Stores final computed metrics + telemetry summary after job completion.
CREATE TABLE IF NOT EXISTS benchmark_results (
    id                TEXT PRIMARY KEY,
    job_id            TEXT NOT NULL REFERENCES benchmark_jobs(id) ON DELETE CASCADE,
    metrics           TEXT NOT NULL DEFAULT '{}',   -- JSON: BenchmarkMetrics
    telemetry_summary TEXT NOT NULL DEFAULT '{}',   -- JSON: TelemetrySummary
    created_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ── Validation Logs ───────────────────────────────────────────────────────────
-- Immutable audit trail of every compatibility check performed.
-- job_id = 'pre-check' for validations that blocked job creation.
CREATE TABLE IF NOT EXISTS benchmark_validation_logs (
    id          TEXT PRIMARY KEY,
    job_id      TEXT NOT NULL,
    model_id    TEXT NOT NULL,
    dataset_id  TEXT NOT NULL,
    checks      TEXT NOT NULL DEFAULT '[]',   -- JSON: list[ValidationCheck]
    passed      INTEGER NOT NULL DEFAULT 1,   -- 1=passed, 0=failed
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ── Indexes ───────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_bmark_jobs_status   ON benchmark_jobs(status);
CREATE INDEX IF NOT EXISTS idx_bmark_jobs_model    ON benchmark_jobs(model_id);
CREATE INDEX IF NOT EXISTS idx_bmark_jobs_dataset  ON benchmark_jobs(dataset_id);
CREATE INDEX IF NOT EXISTS idx_bmark_jobs_created  ON benchmark_jobs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_bmark_results_job   ON benchmark_results(job_id);
CREATE INDEX IF NOT EXISTS idx_bmark_valid_job     ON benchmark_validation_logs(job_id);
CREATE INDEX IF NOT EXISTS idx_bmark_valid_model   ON benchmark_validation_logs(model_id);
