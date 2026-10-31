-- Gatekeeper ledger schema.
-- Rule of thumb: facts and judgments are append-only; only workflow state
-- (an idea's stage, an objection's status, a queue item's status) is updated,
-- and every such update also writes a row to `events`.

CREATE TABLE IF NOT EXISTS meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

-- Versioned configuration. The latest row per section is the live value.
CREATE TABLE IF NOT EXISTS config_versions (
  id         INTEGER PRIMARY KEY,
  section    TEXT NOT NULL CHECK (section IN
               ('profile','strategy','capabilities','taste','weights','rules','bench')),
  body       TEXT NOT NULL,              -- JSON
  reason     TEXT NOT NULL,
  actor      TEXT NOT NULL,
  created_at TEXT NOT NULL
);

-- Current lines and in-flight work. Steward cannot judge balance without these.
CREATE TABLE IF NOT EXISTS portfolio_items (
  id            TEXT PRIMARY KEY,         -- PF-0001
  kind          TEXT NOT NULL CHECK (kind IN ('line','in_flight')),
  name          TEXT NOT NULL,
  description   TEXT,
  ambition_cell TEXT NOT NULL CHECK (ambition_cell IN ('core','adjacent','transformational')),
  four_p        TEXT CHECK (four_p IN ('product','process','position','paradigm')),
  source        TEXT NOT NULL,            -- where the user said this came from
  active        INTEGER NOT NULL DEFAULT 1,
  created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
  id            INTEGER PRIMARY KEY,
  trigger       TEXT NOT NULL,
  started_at    TEXT NOT NULL,
  finished_at   TEXT,
  status        TEXT NOT NULL CHECK (status IN ('running','done','failed','abandoned')),
  strategy_hash TEXT,
  note          TEXT,
  counts        TEXT                      -- JSON
);

CREATE TABLE IF NOT EXISTS signals (
  id           TEXT PRIMARY KEY,          -- SIG-2026-0001
  run_id       INTEGER REFERENCES runs(id),
  sensor       TEXT NOT NULL,
  title        TEXT NOT NULL,
  url          TEXT NOT NULL,
  url_key      TEXT NOT NULL UNIQUE,
  retrieved_at TEXT NOT NULL,
  excerpt      TEXT NOT NULL,
  query        TEXT,
  status       TEXT NOT NULL CHECK (status IN ('new','kept','dropped')),
  novelty      REAL,
  four_p       TEXT,
  curator_note TEXT,
  created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS problems (
  id           TEXT PRIMARY KEY,          -- PRB-2026-0001
  signal_id    TEXT REFERENCES signals(id),
  run_id       INTEGER,
  statement    TEXT NOT NULL,
  for_whom     TEXT NOT NULL,
  why_now      TEXT NOT NULL,
  alternatives TEXT,                      -- JSON list of the statements not chosen
  created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ideas (
  id               TEXT PRIMARY KEY,      -- IDEA-2026-0001
  problem_id       TEXT REFERENCES problems(id),
  signal_id        TEXT REFERENCES signals(id),
  run_id           INTEGER,
  origin           TEXT NOT NULL CHECK (origin IN ('pipeline','human','exemplar')),
  thesis           TEXT NOT NULL,
  description      TEXT,
  technique        TEXT,
  four_p           TEXT CHECK (four_p IN ('product','process','position','paradigm')),
  ambition_cell    TEXT CHECK (ambition_cell IN ('core','adjacent','transformational')),
  first_check      TEXT,                  -- JSON: smallest commitment, uncertainty retired, what must be true
  sponsor          TEXT,
  notes            TEXT,
  stage            TEXT NOT NULL CHECK (stage IN
                     ('candidate','parked_auto','panel','board','promoted','killed','parked',
                      'need_evidence','exemplar','protected')),
  exemplar_outcome TEXT CHECK (exemplar_outcome IN ('funded','killed','regret_killed','regret_funded')),
  created_at       TEXT NOT NULL,
  last_activity_at TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS search_fts USING fts5(ref UNINDEXED, kind UNINDEXED, body);

-- Evidence. Every factual statement is either sourced or an explicit estimate.
CREATE TABLE IF NOT EXISTS claims (
  id           INTEGER PRIMARY KEY,
  idea_id      TEXT,
  signal_id    TEXT,
  field        TEXT NOT NULL,
  statement    TEXT NOT NULL,
  value        TEXT,
  kind         TEXT NOT NULL CHECK (kind IN ('source','estimate')),
  url          TEXT,
  retrieved_at TEXT,
  excerpt      TEXT,
  confidence   TEXT CHECK (confidence IN ('low','medium','high')),
  basis        TEXT,
  created_by   TEXT NOT NULL,
  created_at   TEXT NOT NULL,
  CHECK ((kind = 'source'   AND url IS NOT NULL AND retrieved_at IS NOT NULL AND excerpt IS NOT NULL)
      OR (kind = 'estimate' AND confidence IS NOT NULL AND basis IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS reviews (
  id              INTEGER PRIMARY KEY,
  idea_id         TEXT NOT NULL,
  run_id          INTEGER,
  role            TEXT NOT NULL CHECK (role IN ('analyst','registrar','steward')),
  round           INTEGER NOT NULL CHECK (round IN (1,2)),
  score           REAL NOT NULL CHECK (score BETWEEN 0 AND 1),
  sub             TEXT NOT NULL,          -- JSON of the role's sub-scores
  rationale       TEXT NOT NULL,
  confidence      TEXT NOT NULL CHECK (confidence IN ('low','medium','high')),
  revision_reason TEXT,
  created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS objections (
  id          INTEGER PRIMARY KEY,
  idea_id     TEXT NOT NULL,
  run_id      INTEGER,
  text        TEXT NOT NULL,
  severity    REAL NOT NULL CHECK (severity BETWEEN 0 AND 1),
  falsifier   TEXT NOT NULL,               -- what evidence would answer it
  status      TEXT NOT NULL CHECK (status IN ('open','answered','accepted','superseded')),  -- superseded: replaced by Red Team's later objection
  answer      TEXT,
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS board_snapshots (
  id         INTEGER PRIMARY KEY,
  run_id     INTEGER,
  idea_id    TEXT NOT NULL,
  rank       INTEGER,
  score      REAL,
  band       REAL,
  dispersion REAL,
  components TEXT NOT NULL,               -- JSON: per-role score, weight, contribution
  flags      TEXT NOT NULL,               -- JSON list
  action     TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rank_notes (
  id         INTEGER PRIMARY KEY,
  idea_id    TEXT NOT NULL,
  run_id     INTEGER,
  note       TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS queue_items (
  id                 INTEGER PRIMARY KEY,
  run_id             INTEGER,
  idea_id            TEXT NOT NULL,
  kind               TEXT NOT NULL CHECK (kind IN ('decision','kill')),
  recommended_action TEXT NOT NULL,
  default_action     TEXT NOT NULL,
  default_on         TEXT NOT NULL,       -- YYYY-MM-DD
  why                TEXT NOT NULL,
  status             TEXT NOT NULL CHECK (status IN ('open','decided','defaulted','superseded')),
  created_at         TEXT NOT NULL,
  resolved_at        TEXT
);

CREATE TABLE IF NOT EXISTS decisions (
  id         INTEGER PRIMARY KEY,
  idea_id    TEXT NOT NULL,
  action     TEXT NOT NULL CHECK (action IN ('promote','kill','park','need_evidence','keep')),
  reason     TEXT NOT NULL CHECK (length(reason) >= 10),
  actor      TEXT NOT NULL,               -- 'human' or 'default'
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS my_rank (
  id         INTEGER PRIMARY KEY,
  ranking    TEXT NOT NULL,               -- JSON list of idea ids, best first
  note       TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
  id         INTEGER PRIMARY KEY,
  kind       TEXT NOT NULL CHECK (kind IN ('need_evidence','rescore','resurrect_check')),
  idea_id    TEXT,
  role       TEXT,
  payload    TEXT,
  status     TEXT NOT NULL CHECK (status IN ('pending','running','done','failed')),
  note       TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS calibration_proposals (
  id            INTEGER PRIMARY KEY,
  kind          TEXT NOT NULL CHECK (kind IN ('weights','taste','rules')),
  body          TEXT NOT NULL,
  rationale     TEXT NOT NULL,
  status        TEXT NOT NULL CHECK (status IN ('open','accepted','rejected')),
  decided_reason TEXT,
  created_at    TEXT NOT NULL,
  decided_at    TEXT
);

CREATE TABLE IF NOT EXISTS briefs (
  id         INTEGER PRIMARY KEY,
  run_id     INTEGER,
  brief_date TEXT NOT NULL,
  body       TEXT NOT NULL,
  quiet      INTEGER NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rejections (
  id         INTEGER PRIMARY KEY,
  run_id     INTEGER,
  tool       TEXT NOT NULL,
  reason     TEXT NOT NULL,
  payload    TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
  id         INTEGER PRIMARY KEY,
  idea_id    TEXT,
  run_id     INTEGER,
  at         TEXT NOT NULL,
  actor      TEXT NOT NULL,
  event      TEXT NOT NULL,
  detail     TEXT
);

CREATE INDEX IF NOT EXISTS ix_events_idea   ON events(idea_id, at);
CREATE INDEX IF NOT EXISTS ix_reviews_idea  ON reviews(idea_id, role, round, id);
CREATE INDEX IF NOT EXISTS ix_claims_idea   ON claims(idea_id);
CREATE INDEX IF NOT EXISTS ix_snap_idea     ON board_snapshots(idea_id, id);
CREATE INDEX IF NOT EXISTS ix_signals_run   ON signals(run_id, sensor);
