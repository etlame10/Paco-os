-- =====================================================================
-- PACO OS — Envío automático de notificaciones (Supabase Cron)
-- Ejecútalo SOLO después de publicar la Edge Function "send-notifications"
-- y de haber ejecutado schema.sql. Pasos completos en docs/NOTIFICACIONES.md.
--
-- Qué hace: cada 5 minutos la base de datos llama a la Edge Function, que envía
-- los avisos cuya hora ya ha llegado. No borra ni modifica datos existentes.
-- Es idempotente: puedes ejecutarlo varias veces.
-- =====================================================================

-- 1. Extensiones necesarias (incluidas en el plan gratuito)
create extension if not exists pg_cron;
create extension if not exists pg_net;

-- 2. Secretos en Supabase Vault (cifrados dentro de tu base de datos, nunca en GitHub)
--    - paco_functions_url: dirección de tus Edge Functions
--    - paco_cron_secret:   token aleatorio que la función exige para enviar avisos.
--                          Se genera aquí y solo se crea si no existe.
do $$
begin
  if not exists (select 1 from vault.secrets where name = 'paco_functions_url') then
    perform vault.create_secret(
      'https://pwzkkmqtjkzvskwlopwh.supabase.co/functions/v1',
      'paco_functions_url',
      'URL base de las Edge Functions de PACO OS'
    );
  end if;
  if not exists (select 1 from vault.secrets where name = 'paco_cron_secret') then
    perform vault.create_secret(
      encode(extensions.gen_random_bytes(32), 'hex'),
      'paco_cron_secret',
      'Token que Supabase Cron envía a send-notifications'
    );
  end if;
end $$;

-- 3. Tarea programada: cada 5 minutos
select cron.schedule(
  'paco-send-notifications',
  '*/5 * * * *',
  $job$
  select net.http_post(
    url     := (select decrypted_secret from vault.decrypted_secrets where name = 'paco_functions_url') || '/send-notifications',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'x-cron-secret', (select decrypted_secret from vault.decrypted_secrets where name = 'paco_cron_secret')
    ),
    body    := jsonb_build_object('action', 'dispatch'),
    timeout_milliseconds := 20000
  );
  $job$
);

-- 4. Muestra el token para copiarlo en los secretos de la Edge Function (CRON_SECRET).
--    Cópialo y NO lo pegues en GitHub ni en ningún archivo del proyecto.
select decrypted_secret as copia_este_valor_en_CRON_SECRET
from vault.decrypted_secrets
where name = 'paco_cron_secret';

-- ---------------------------------------------------------------------
-- Utilidades (opcionales, ejecútalas por separado cuando las necesites):
--
-- Ver las últimas ejecuciones:
--   select status, return_message, start_time
--   from cron.job_run_details
--   where jobid = (select jobid from cron.job where jobname = 'paco-send-notifications')
--   order by start_time desc limit 20;
--
-- Pausar el envío automático (no borra ningún aviso):
--   select cron.unschedule('paco-send-notifications');
-- ---------------------------------------------------------------------
