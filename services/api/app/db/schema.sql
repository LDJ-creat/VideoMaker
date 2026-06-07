CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY,
  name TEXT,
  cookies_uri TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY,
  project_id TEXT,
  status TEXT NOT NULL,
  stage TEXT NOT NULL,
  progress INTEGER NOT NULL,
  message TEXT NOT NULL,
  error_json TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS artifacts (
  id TEXT PRIMARY KEY,
  project_id TEXT,
  task_id TEXT,
  type TEXT NOT NULL,
  uri TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS task_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id TEXT NOT NULL,
  event_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS samples (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  source_kind TEXT NOT NULL,
  source_url TEXT,
  video_uri TEXT,
  status TEXT NOT NULL,
  task_id TEXT,
  structure_json TEXT,
  upload_batch_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS project_assets (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  type TEXT NOT NULL,
  uri TEXT NOT NULL,
  description TEXT,
  tags_json TEXT,
  duration_sec REAL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS project_briefs (
  project_id TEXT PRIMARY KEY,
  brief_json TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS generations (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  structure_id TEXT,
  inventory_id TEXT,
  gap_report_json TEXT,
  plan_json TEXT,
  status TEXT NOT NULL,
  task_id TEXT,
  variant TEXT,
  generation_run_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS model_gateway_providers (
  provider TEXT PRIMARY KEY,
  base_url TEXT NOT NULL DEFAULT '',
  model TEXT NOT NULL DEFAULT '',
  driver TEXT NOT NULL DEFAULT 'openai_compatible',
  api_key_ciphertext BLOB,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stock_media_providers (
  provider TEXT PRIMARY KEY,
  api_key_ciphertext BLOB,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS knowledge_entries (
  id TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  title TEXT NOT NULL,
  category TEXT NOT NULL,
  category_slug TEXT NOT NULL,
  style TEXT NOT NULL,
  hook_type TEXT,
  tempo TEXT,
  duration_bucket TEXT,
  slot_pattern TEXT NOT NULL,
  summary TEXT NOT NULL,
  skill_md_uri TEXT NOT NULL,
  structure_json_uri TEXT NOT NULL,
  source_project_id TEXT,
  source_sample_id TEXT,
  version INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_knowledge_category ON knowledge_entries(category, status);
CREATE INDEX IF NOT EXISTS idx_knowledge_slot_pattern ON knowledge_entries(slot_pattern);

CREATE TABLE IF NOT EXISTS project_knowledge_selection (
  project_id TEXT PRIMARY KEY,
  primary_entry_id TEXT,
  reference_entry_ids_json TEXT NOT NULL DEFAULT '[]',
  mode TEXT NOT NULL DEFAULT 'auto',
  applied_as_structure INTEGER NOT NULL DEFAULT 0,
  recommendation_json TEXT,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS upload_batches (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  status TEXT NOT NULL,
  sample_ids_json TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE INDEX IF NOT EXISTS idx_upload_batches_project ON upload_batches(project_id, created_at DESC);

CREATE TABLE IF NOT EXISTS project_sample_selection (
  project_id TEXT PRIMARY KEY,
  primary_sample_id TEXT,
  reference_sample_ids_json TEXT NOT NULL DEFAULT '[]',
  active_upload_batch_id TEXT,
  mode TEXT NOT NULL DEFAULT 'auto',
  recommendation_json TEXT,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS generation_runs (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  sample_selection_json TEXT NOT NULL,
  synthesized_structure_id TEXT,
  provenance_id TEXT,
  variant_ids_json TEXT NOT NULL DEFAULT '[]',
  generation_ids_json TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE INDEX IF NOT EXISTS idx_generation_runs_project ON generation_runs(project_id, created_at DESC);
