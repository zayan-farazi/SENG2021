create table if not exists public.parties (
  party_name text,
  contact_email text,
  created_at timestamptz default now(),
  key_hash text
);

alter table public.parties
  add column if not exists party_name text,
  add column if not exists contact_email text,
  add column if not exists created_at timestamptz default now(),
  add column if not exists key_hash text;

create unique index if not exists idx_parties_contact_email
  on public.parties (contact_email)
  where contact_email is not null;

create unique index if not exists idx_parties_key_hash
  on public.parties (key_hash)
  where key_hash is not null;
