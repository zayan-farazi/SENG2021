create table if not exists public.parties (
  party_name text not null,
  contact_email text not null,
  created_at timestamptz not null default now(),
  party_id text not null,
  key_hash text not null,
  constraint parties_pkey primary key (contact_email),
  constraint app_keys_key_hash_key unique (key_hash),
  constraint parties_contact_email_valid check (
    contact_email ~* '^[^@\s]+@[^@\s]+\.[^@\s]+$'
  )
);

create index if not exists idx_app_keys_party_id
  on public.app_keys (party_id);

create index if not exists idx_app_keys_key_hash
  on public.app_keys (key_hash);
