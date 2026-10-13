CREATE TABLE IF NOT EXISTS platforms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    domain TEXT NOT NULL UNIQUE,
    registration_url TEXT,
    submission_url TEXT,
    relevance TEXT,
    da REAL,
    pa REAL,
    spam_score REAL,
    metric_provider TEXT,
    metrics_verified_at TEXT,
    eligibility_status TEXT NOT NULL DEFAULT 'DISCOVERED',
    rejection_reason TEXT,
    terms_url TEXT,
    available INTEGER DEFAULT 1,
    registration_requirements TEXT,
    link_attributes TEXT,
    public_visibility TEXT,
    posting_restrictions TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    target_url TEXT NOT NULL,
    tags TEXT,
    valid INTEGER NOT NULL DEFAULT 0,
    approval_status TEXT NOT NULL DEFAULT 'PENDING',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(platform_id, target_url),
    FOREIGN KEY(platform_id) REFERENCES platforms(id)
);

CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform_id INTEGER NOT NULL,
    draft_id INTEGER,
    target_url TEXT NOT NULL,
    status TEXT NOT NULL,
    published_url TEXT,
    error_message TEXT,
    screenshot_path TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(platform_id, target_url),
    FOREIGN KEY(platform_id) REFERENCES platforms(id),
    FOREIGN KEY(draft_id) REFERENCES drafts(id)
);

CREATE TABLE IF NOT EXISTS workflow_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS backlink_audits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform_id INTEGER,
    published_url TEXT NOT NULL,
    target_url TEXT NOT NULL,
    link_found INTEGER NOT NULL DEFAULT 0,
    is_dofollow INTEGER NOT NULL DEFAULT 0,
    rel_attribute TEXT,
    anchor_text TEXT,
    has_primary_keyword INTEGER NOT NULL DEFAULT 0,
    meta_robots TEXT,
    canonical_url TEXT,
    canonical_matched INTEGER DEFAULT 1,
    robots_txt_allowed INTEGER DEFAULT 1,
    status_code INTEGER,
    ttfb_ms REAL,
    quality_score INTEGER NOT NULL DEFAULT 0,
    indexability_grade TEXT DEFAULT 'A',
    issues TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(platform_id) REFERENCES platforms(id)
);

CREATE TABLE IF NOT EXISTS serp_rankings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword TEXT NOT NULL,
    search_engine TEXT NOT NULL,
    rank_position INTEGER,
    rank_delta INTEGER DEFAULT 0,
    found_url TEXT,
    page_title TEXT,
    snippet TEXT,
    checked_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS platform_health (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform_id INTEGER,
    domain TEXT NOT NULL,
    is_reachable INTEGER NOT NULL DEFAULT 1,
    status_code INTEGER,
    latency_ms REAL,
    ssl_valid INTEGER DEFAULT 1,
    error_message TEXT,
    checked_at TEXT NOT NULL,
    FOREIGN KEY(platform_id) REFERENCES platforms(id)
);

CREATE TABLE IF NOT EXISTS notification_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    channel TEXT NOT NULL,
    message TEXT NOT NULL,
    payload TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT NOT NULL UNIQUE,
    username TEXT NOT NULL,
    password TEXT NOT NULL,
    storage_state_path TEXT,
    last_login_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS content_evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    draft_id INTEGER,
    platform_id INTEGER,
    relevance_score REAL NOT NULL,
    accuracy_score REAL NOT NULL,
    readability_score REAL NOT NULL,
    safety_score REAL NOT NULL,
    composite_score REAL NOT NULL,
    grade TEXT NOT NULL,
    auto_approved INTEGER NOT NULL DEFAULT 0,
    justification TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(draft_id) REFERENCES drafts(id),
    FOREIGN KEY(platform_id) REFERENCES platforms(id)
);

CREATE TABLE IF NOT EXISTS public_verifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id INTEGER,
    platform_id INTEGER,
    published_url TEXT NOT NULL,
    is_publicly_visible INTEGER NOT NULL DEFAULT 0,
    public_link_verified INTEGER NOT NULL DEFAULT 0,
    destination_http_code INTEGER,
    moderation_status TEXT,
    details TEXT,
    verified_at TEXT NOT NULL,
    FOREIGN KEY(submission_id) REFERENCES submissions(id),
    FOREIGN KEY(platform_id) REFERENCES platforms(id)
);

CREATE TABLE IF NOT EXISTS campaign_analytics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform_id INTEGER,
    domain TEXT NOT NULL,
    utm_url TEXT NOT NULL,
    traffic_tier TEXT,
    estimated_monthly_impressions INTEGER DEFAULT 0,
    equity_value_score REAL DEFAULT 0.0,
    created_at TEXT NOT NULL,
    FOREIGN KEY(platform_id) REFERENCES platforms(id)
);
