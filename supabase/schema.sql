-- =====================================================================
-- PACO OS — Esquema de base de datos para Supabase
-- Ejecuta este archivo completo en: Supabase > SQL Editor > New query
-- Es idempotente: puedes ejecutarlo varias veces sin romper nada.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. ITEMS: tabla genérica que usan TODOS los módulos
--    (tareas, notas, estudios, películas, juegos, compras, viajes...)
--    Añadir un módulo nuevo NO requiere tocar la base de datos:
--    cada registro lleva el id de su módulo y sus campos extra en "data".
-- ---------------------------------------------------------------------
create table if not exists public.items (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null default auth.uid() references auth.users(id) on delete cascade,
  module      text not null,
  title       text not null default '',
  body        text not null default '',
  status      text,
  due_date    date,
  tags        text[] not null default '{}',
  data        jsonb not null default '{}'::jsonb,
  pinned      boolean not null default false,
  position    double precision not null default 0,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create index if not exists items_user_module_idx on public.items (user_id, module);
create index if not exists items_user_due_idx    on public.items (user_id, due_date);
create index if not exists items_user_pinned_idx on public.items (user_id) where pinned;

-- ---------------------------------------------------------------------
-- 2. FILES: metadatos de los archivos subidos a Supabase Storage
-- ---------------------------------------------------------------------
create table if not exists public.files (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null default auth.uid() references auth.users(id) on delete cascade,
  name        text not null,
  path        text not null unique,
  folder      text not null default '',
  size        bigint not null default 0,
  mime_type   text,
  created_at  timestamptz not null default now()
);

create index if not exists files_user_folder_idx on public.files (user_id, folder);

-- ---------------------------------------------------------------------
-- 3. USER_SETTINGS: preferencias (tema, módulos activos, orden...)
-- ---------------------------------------------------------------------
create table if not exists public.user_settings (
  user_id     uuid primary key default auth.uid() references auth.users(id) on delete cascade,
  settings    jsonb not null default '{}'::jsonb,
  updated_at  timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- 4. updated_at automático
-- ---------------------------------------------------------------------
create or replace function public.touch_updated_at()
returns trigger language plpgsql set search_path = '' as $$
begin
  new.updated_at = now();
  return new;
end $$;

drop trigger if exists items_touch on public.items;
create trigger items_touch before update on public.items
  for each row execute function public.touch_updated_at();

drop trigger if exists settings_touch on public.user_settings;
create trigger settings_touch before update on public.user_settings
  for each row execute function public.touch_updated_at();

-- ---------------------------------------------------------------------
-- 5. SEGURIDAD (Row Level Security): cada usuario solo ve lo suyo
-- ---------------------------------------------------------------------
alter table public.items         enable row level security;
alter table public.files         enable row level security;
alter table public.user_settings enable row level security;

drop policy if exists "items: own rows" on public.items;
create policy "items: own rows" on public.items
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "files: own rows" on public.files;
create policy "files: own rows" on public.files
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "settings: own row" on public.user_settings;
create policy "settings: own row" on public.user_settings
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- Permisos de la API: solo usuarios con sesión iniciada (rol "authenticated").
-- El rol "anon" (visitantes sin sesión) no puede acceder a ninguna tabla.
-- Algunos proyectos nuevos de Supabase no conceden estos permisos por defecto.
revoke all on public.items, public.files, public.user_settings from anon;
grant select, insert, update, delete on public.items, public.files, public.user_settings to authenticated;

-- ---------------------------------------------------------------------
-- 6. STORAGE: bucket privado "paco-files"
--    Cada usuario solo puede leer/escribir dentro de la carpeta <su user id>/
-- ---------------------------------------------------------------------
insert into storage.buckets (id, name, public)
values ('paco-files', 'paco-files', false)
on conflict (id) do nothing;

drop policy if exists "paco-files: read own"   on storage.objects;
drop policy if exists "paco-files: insert own" on storage.objects;
drop policy if exists "paco-files: update own" on storage.objects;
drop policy if exists "paco-files: delete own" on storage.objects;

create policy "paco-files: read own" on storage.objects
  for select using (bucket_id = 'paco-files' and (storage.foldername(name))[1] = auth.uid()::text);

create policy "paco-files: insert own" on storage.objects
  for insert with check (bucket_id = 'paco-files' and (storage.foldername(name))[1] = auth.uid()::text);

create policy "paco-files: update own" on storage.objects
  for update
  using (bucket_id = 'paco-files' and (storage.foldername(name))[1] = auth.uid()::text)
  with check (bucket_id = 'paco-files' and (storage.foldername(name))[1] = auth.uid()::text);

create policy "paco-files: delete own" on storage.objects
  for delete using (bucket_id = 'paco-files' and (storage.foldername(name))[1] = auth.uid()::text);
