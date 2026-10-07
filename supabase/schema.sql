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

-- =====================================================================
-- 7. NOTIFICACIONES (ver docs/NOTIFICACIONES.md)
--    Tablas nuevas: no modifican ni borran nada de las anteriores.
-- =====================================================================

-- Dispositivos suscritos a Web Push (uno por navegador/app instalada)
create table if not exists public.push_subscriptions (
  id               uuid primary key default gen_random_uuid(),
  user_id          uuid not null default auth.uid() references auth.users(id) on delete cascade,
  endpoint         text not null unique,
  p256dh           text not null,
  auth             text not null,
  device_name      text,
  user_agent       text,
  failure_count    integer not null default 0,
  created_at       timestamptz not null default now(),
  last_seen_at     timestamptz not null default now(),
  last_success_at  timestamptz
);

create index if not exists push_subscriptions_user_idx on public.push_subscriptions (user_id);

-- Avisos programados y su historial (la bandeja de la campana).
--   kind:   task | exam | event | custom | system
--   status: pending (programado) | sending (enviándose) | sent | failed | cancelled | skipped
create table if not exists public.notifications (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null default auth.uid() references auth.users(id) on delete cascade,
  item_id     uuid references public.items(id) on delete cascade,
  dedupe_key  text not null default gen_random_uuid()::text,
  kind        text not null default 'custom'
              check (kind in ('task', 'exam', 'event', 'custom', 'system')),
  title       text not null default '',
  body        text not null default '',
  url         text,
  remind_at   timestamptz not null,
  status      text not null default 'pending'
              check (status in ('pending', 'sending', 'sent', 'failed', 'cancelled', 'skipped')),
  attempts    integer not null default 0,
  last_error  text,
  sent_at     timestamptz,
  read_at     timestamptz,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  unique (user_id, dedupe_key)
);

create index if not exists notifications_due_idx  on public.notifications (remind_at) where status in ('pending', 'sending');
create index if not exists notifications_user_idx on public.notifications (user_id, remind_at desc);
create index if not exists notifications_item_idx on public.notifications (item_id);

drop trigger if exists notifications_touch on public.notifications;
create trigger notifications_touch before update on public.notifications
  for each row execute function public.touch_updated_at();

alter table public.push_subscriptions enable row level security;
alter table public.notifications      enable row level security;

drop policy if exists "push_subscriptions: own rows" on public.push_subscriptions;
create policy "push_subscriptions: own rows" on public.push_subscriptions
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "notifications: own rows" on public.notifications;
create policy "notifications: own rows" on public.notifications
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

revoke all on public.push_subscriptions, public.notifications from anon;
grant select, insert, update, delete on public.push_subscriptions, public.notifications to authenticated;
-- La Edge Function "send-notifications" usa el rol de servicio dentro de Supabase
-- (nunca expuesto en la web) para leer los avisos pendientes de todos los usuarios.

-- =====================================================================
-- 8. PACO AI (ver docs/PACO_AI.md)
--    Solo añade una tabla de uso y dos funciones: no modifica ni borra nada.
--    La conversación NO se guarda en la base de datos (queda en el dispositivo).
-- =====================================================================

-- Uso diario de PACO AI por usuario (límite de peticiones y tokens consumidos).
create table if not exists public.ai_usage (
  user_id       uuid not null references auth.users (id) on delete cascade,
  day           date not null,
  requests      integer not null default 0,
  input_tokens  bigint not null default 0,
  output_tokens bigint not null default 0,
  updated_at    timestamptz not null default now(),
  primary key (user_id, day)
);

alter table public.ai_usage enable row level security;

-- Cada usuario puede VER su propio uso; solo la Edge Function "paco-ai" lo modifica.
drop policy if exists "ai_usage: read own" on public.ai_usage;
create policy "ai_usage: read own" on public.ai_usage
  for select using (auth.uid() = user_id);

revoke all on public.ai_usage from anon, authenticated;
grant select on public.ai_usage to authenticated;
grant select, insert, update, delete on public.ai_usage to service_role;

-- Suma una petición si no se ha llegado al límite. Devuelve el nuevo total del día,
-- o NULL si ya se alcanzó (de forma atómica, aunque lleguen varias a la vez).
create or replace function public.paco_ai_take_request(p_user uuid, p_limit integer)
returns integer
language plpgsql
security definer
set search_path = ''
as $$
declare
  n integer;
begin
  insert into public.ai_usage as u (user_id, day, requests)
  values (p_user, (now() at time zone 'Europe/Madrid')::date, 1)
  on conflict (user_id, day) do update
    set requests = u.requests + 1, updated_at = now()
    where u.requests < p_limit
  returning u.requests into n;
  return n;
end;
$$;

create or replace function public.paco_ai_add_tokens(p_user uuid, p_input bigint, p_output bigint)
returns void
language sql
security definer
set search_path = ''
as $$
  update public.ai_usage
     set input_tokens = input_tokens + greatest(p_input, 0),
         output_tokens = output_tokens + greatest(p_output, 0),
         updated_at = now()
   where user_id = p_user and day = (now() at time zone 'Europe/Madrid')::date;
$$;

-- Solo el rol de servicio (la Edge Function) puede llamarlas.
revoke all on function public.paco_ai_take_request(uuid, integer) from public, anon, authenticated;
revoke all on function public.paco_ai_add_tokens(uuid, bigint, bigint) from public, anon, authenticated;
grant execute on function public.paco_ai_take_request(uuid, integer) to service_role;
grant execute on function public.paco_ai_add_tokens(uuid, bigint, bigint) to service_role;

-- =====================================================================
-- 9. PACO AI: un uso = una interacción del usuario (ver docs/PACO_AI.md)
--    Una pregunta puede necesitar varias llamadas internas al modelo (usar
--    herramientas, reintentos...). Todas comparten el mismo interaction_id y
--    solo la primera suma 1 al contador diario de ai_usage.
--    Solo añade una tabla y dos funciones: no modifica ni borra nada.
-- =====================================================================

create table if not exists public.ai_interactions (
  user_id        uuid not null references auth.users (id) on delete cascade,
  interaction_id uuid not null,
  day            date not null,
  steps          integer not null default 1,
  created_at     timestamptz not null default now(),
  primary key (user_id, interaction_id)
);

create index if not exists ai_interactions_day_idx on public.ai_interactions (day);

alter table public.ai_interactions enable row level security;
-- Sin políticas para usuarios: solo la Edge Function (rol de servicio) la usa.
revoke all on public.ai_interactions from anon, authenticated;
grant select, insert, update, delete on public.ai_interactions to service_role;

-- Registra un paso de una interacción. Devuelve una fila:
--   status = 'counted'   -> interacción nueva: suma 1 uso
--            'continued' -> paso más de una interacción ya contada: no suma
--            'limit'     -> límite diario alcanzado (no se registra nada)
--            'too_many_steps' -> la interacción ya ha hecho demasiados pasos
--   requests = usos de hoy tras la operación
-- Bloquea la fila de uso del día: dos peticiones simultáneas no pueden saltarse el límite.
create or replace function public.paco_ai_take_interaction(p_user uuid, p_interaction uuid, p_limit integer, p_max_steps integer)
returns table (status text, requests integer)
language plpgsql
security definer
set search_path = ''
as $$
declare
  d date := (now() at time zone 'Europe/Madrid')::date;
  n integer;
  s integer;
begin
  insert into public.ai_usage (user_id, day, requests) values (p_user, d, 0)
  on conflict (user_id, day) do nothing;
  select u.requests into n from public.ai_usage u where u.user_id = p_user and u.day = d for update;

  update public.ai_interactions i set steps = i.steps + 1
   where i.user_id = p_user and i.interaction_id = p_interaction and i.steps < p_max_steps
  returning i.steps into s;
  if found then
    return query select 'continued'::text, n;
    return;
  end if;
  if exists (select 1 from public.ai_interactions i where i.user_id = p_user and i.interaction_id = p_interaction) then
    return query select 'too_many_steps'::text, n;
    return;
  end if;
  if n >= p_limit then
    return query select 'limit'::text, n;
    return;
  end if;

  insert into public.ai_interactions (user_id, interaction_id, day) values (p_user, p_interaction, d);
  update public.ai_usage u set requests = u.requests + 1, updated_at = now()
   where u.user_id = p_user and u.day = d
  returning u.requests into n;
  return query select 'counted'::text, n;
end;
$$;

-- Si el primer paso de una interacción falla del todo (p. ej. Gemini no responde
-- tras los reintentos), se devuelve el uso: un error no gasta cuota.
create or replace function public.paco_ai_refund_interaction(p_user uuid, p_interaction uuid)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  d date;
begin
  delete from public.ai_interactions i
   where i.user_id = p_user and i.interaction_id = p_interaction and i.steps = 1
  returning i.day into d;
  if found then
    update public.ai_usage u set requests = greatest(u.requests - 1, 0), updated_at = now()
     where u.user_id = p_user and u.day = d;
  end if;
end;
$$;

revoke all on function public.paco_ai_take_interaction(uuid, uuid, integer, integer) from public, anon, authenticated;
revoke all on function public.paco_ai_refund_interaction(uuid, uuid) from public, anon, authenticated;
grant execute on function public.paco_ai_take_interaction(uuid, uuid, integer, integer) to service_role;
grant execute on function public.paco_ai_refund_interaction(uuid, uuid) to service_role;
