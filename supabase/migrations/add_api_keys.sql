create table if not exists api_keys (
  id uuid primary key default gen_random_uuid(),
  label text not null,
  provider text not null default 'gemini',
  api_key text not null,
  is_active boolean default true,
  rate_limited_until timestamptz null,
  created_at timestamptz default now()
);
