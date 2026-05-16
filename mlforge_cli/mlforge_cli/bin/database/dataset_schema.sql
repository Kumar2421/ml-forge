-- ============================================================
-- MLForge Dataset Manager — SQLite Schema Extension
-- Appended to existing modelzoo.db (CREATE IF NOT EXISTS)
-- ============================================================

-- ── Datasets ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS datasets (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    task            TEXT NOT NULL,
    format          TEXT NOT NULL,
    source          TEXT NOT NULL DEFAULT 'roboflow',
    status          TEXT NOT NULL DEFAULT 'available',
    images          INTEGER NOT NULL DEFAULT 0,
    classes         INTEGER NOT NULL DEFAULT 0,
    class_names     TEXT NOT NULL DEFAULT '[]',   -- JSON array
    size_bytes      INTEGER NOT NULL DEFAULT 0,
    size_label      TEXT NOT NULL DEFAULT '0 B',
    local_path      TEXT,
    import_progress REAL NOT NULL DEFAULT 0.0,    -- 0.0–1.0
    tags            TEXT NOT NULL DEFAULT '[]',   -- JSON array
    versions        TEXT NOT NULL DEFAULT '[]',   -- JSON array
    active_version  TEXT NOT NULL DEFAULT 'v1',
    starred         INTEGER NOT NULL DEFAULT 0,
    roboflow_id     TEXT,                          -- workspace/project slug
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ── Dataset Jobs ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dataset_jobs (
    id           TEXT PRIMARY KEY,
    type         TEXT NOT NULL,                   -- import|extract|validate|analyze
    status       TEXT NOT NULL DEFAULT 'queued',  -- queued|running|completed|failed|cancelled
    dataset_id   TEXT NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    dataset_name TEXT NOT NULL DEFAULT '',
    progress     REAL NOT NULL DEFAULT 0.0,       -- 0.0–1.0
    message      TEXT NOT NULL DEFAULT '',
    error        TEXT,
    meta         TEXT NOT NULL DEFAULT '{}',      -- JSON extra data
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now')),
    started_at   TEXT,
    ended_at     TEXT
);

-- ── Dataset Images Index ──────────────────────────────────
-- Populated after extraction; enables fast paginated viewer queries
CREATE TABLE IF NOT EXISTS dataset_images (
    id          TEXT PRIMARY KEY,             -- sha1 or sequential id
    dataset_id  TEXT NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    filename    TEXT NOT NULL,
    rel_path    TEXT NOT NULL,                -- relative to dataset local_path
    width       INTEGER NOT NULL DEFAULT 0,
    height      INTEGER NOT NULL DEFAULT 0,
    split       TEXT NOT NULL DEFAULT 'train',
    ann_count   INTEGER NOT NULL DEFAULT 0,   -- fast count without parsing
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ── Dataset Annotations Cache ─────────────────────────────
-- Parsed annotations stored in normalised form for fast retrieval
CREATE TABLE IF NOT EXISTS dataset_annotations (
    id         TEXT PRIMARY KEY,
    image_id   TEXT NOT NULL REFERENCES dataset_images(id) ON DELETE CASCADE,
    dataset_id TEXT NOT NULL,
    label      TEXT NOT NULL,
    bbox_x     REAL,
    bbox_y     REAL,
    bbox_w     REAL,
    bbox_h     REAL,
    normalised INTEGER DEFAULT 1,
    area       REAL,
    confidence REAL,
    ann_type   TEXT DEFAULT 'detection',
    segmentation TEXT,                    -- JSON array of points [[x,y],...]
    keypoints    TEXT,                    -- JSON array of keypoints [x,y,v,...]
    metadata     TEXT                     -- Extra JSON metadata
);

-- ── Roboflow Metadata Cache ───────────────────────────────
-- Avoids redundant API calls; TTL enforced in Python layer
CREATE TABLE IF NOT EXISTS roboflow_cache (
    cache_key  TEXT PRIMARY KEY,              -- workspace/project or search query hash
    payload    TEXT NOT NULL,                 -- JSON blob
    fetched_at TEXT NOT NULL DEFAULT (datetime('now')),
    ttl_secs   INTEGER NOT NULL DEFAULT 3600  -- 1 hour default
);

-- ── Indexes ───────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_datasets_task    ON datasets(task);
CREATE INDEX IF NOT EXISTS idx_datasets_format  ON datasets(format);
CREATE INDEX IF NOT EXISTS idx_datasets_source  ON datasets(source);
CREATE INDEX IF NOT EXISTS idx_datasets_status  ON datasets(status);
CREATE INDEX IF NOT EXISTS idx_datasets_starred ON datasets(starred);

CREATE INDEX IF NOT EXISTS idx_djobs_status     ON dataset_jobs(status);
CREATE INDEX IF NOT EXISTS idx_djobs_dataset    ON dataset_jobs(dataset_id);

CREATE INDEX IF NOT EXISTS idx_dimages_dataset  ON dataset_images(dataset_id);
CREATE INDEX IF NOT EXISTS idx_dimages_split    ON dataset_images(dataset_id, split);

CREATE INDEX IF NOT EXISTS idx_dann_image       ON dataset_annotations(image_id);
CREATE INDEX IF NOT EXISTS idx_dann_dataset     ON dataset_annotations(dataset_id);
CREATE INDEX IF NOT EXISTS idx_dann_label       ON dataset_annotations(dataset_id, label);

-- ── Updated-at trigger for datasets ──────────────────────
CREATE TRIGGER IF NOT EXISTS datasets_updated_at
AFTER UPDATE ON datasets BEGIN
    UPDATE datasets SET updated_at = datetime('now') WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS dataset_jobs_updated_at
AFTER UPDATE ON dataset_jobs BEGIN
    UPDATE dataset_jobs SET updated_at = datetime('now') WHERE id = NEW.id;
END;
