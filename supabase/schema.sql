-- Telegram Sessions
CREATE TABLE IF NOT EXISTS telegram_sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  phone TEXT UNIQUE NOT NULL,
  session_string TEXT NOT NULL,
  username TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Scanned Groups
CREATE TABLE IF NOT EXISTS scanned_groups (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_phone TEXT NOT NULL,
  group_username TEXT,
  group_title TEXT NOT NULL,
  member_count INTEGER,
  keyword TEXT,
  scanned_at TIMESTAMPTZ DEFAULT now()
);

-- Candidates Found
CREATE TABLE IF NOT EXISTS candidates (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  group_id UUID REFERENCES scanned_groups(id) ON DELETE CASCADE,
  telegram_username TEXT,
  display_name TEXT,
  message_sample TEXT,
  ai_score INTEGER CHECK (ai_score BETWEEN 1 AND 10),
  ai_reason TEXT,
  status TEXT DEFAULT 'new',
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Outreach Logs
CREATE TABLE IF NOT EXISTS outreach_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  candidate_id UUID REFERENCES candidates(id) ON DELETE SET NULL,
  candidate_username TEXT NOT NULL,
  group_source TEXT,
  message_sent TEXT NOT NULL,
  sent_at TIMESTAMPTZ DEFAULT now(),
  sent_by_phone TEXT
);
