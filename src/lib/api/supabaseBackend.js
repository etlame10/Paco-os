import { supabase, STORAGE_BUCKET } from '../supabase'

function check({ data, error }) {
  if (error) throw error
  return data
}

async function currentUserId() {
  const { data } = await supabase.auth.getSession()
  const id = data.session?.user?.id
  if (!id) throw new Error('No hay sesión iniciada')
  return id
}

function safeName(name) {
  return name.normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^\w.\-]+/g, '_')
}

export const supabaseBackend = {
  mode: 'supabase',

  auth: {
    async getSession() {
      const { data } = await supabase.auth.getSession()
      return data.session
    },
    onChange(cb) {
      // event: 'SIGNED_IN' | 'SIGNED_OUT' | 'PASSWORD_RECOVERY' | 'TOKEN_REFRESHED' | ...
      const { data } = supabase.auth.onAuthStateChange((event, session) => cb(session, event))
      return () => data.subscription.unsubscribe()
    },
    async signIn(email, password) {
      check(await supabase.auth.signInWithPassword({ email, password }))
    },
    async signUp(email, password) {
      return check(
        await supabase.auth.signUp({
          email,
          password,
          options: { emailRedirectTo: window.location.origin + window.location.pathname },
        }),
      )
    },
    async magicLink(email) {
      check(
        await supabase.auth.signInWithOtp({
          email,
          options: { emailRedirectTo: window.location.origin + window.location.pathname },
        }),
      )
    },
    async resetPassword(email) {
      check(
        await supabase.auth.resetPasswordForEmail(email, {
          redirectTo: window.location.origin + window.location.pathname,
        }),
      )
    },
    async updatePassword(password) {
      check(await supabase.auth.updateUser({ password }))
    },
    async signOut() {
      await supabase.auth.signOut()
    },
  },

  items: {
    async get(id) {
      return check(await supabase.from('items').select('*').eq('id', id).maybeSingle())
    },
    async list({ module, orderBy = 'created_at', ascending = false } = {}) {
      let q = supabase.from('items').select('*')
      if (module) q = q.eq('module', module)
      return check(await q.order(orderBy, { ascending }))
    },
    async listByDateRange(from, to) {
      return check(
        await supabase
          .from('items')
          .select('*')
          .gte('due_date', from)
          .lte('due_date', to)
          .order('due_date', { ascending: true }),
      )
    },
    async listPinned() {
      return check(
        await supabase.from('items').select('*').eq('pinned', true).order('updated_at', { ascending: false }),
      )
    },
    async listRecent(limit = 10) {
      return check(
        await supabase.from('items').select('*').order('updated_at', { ascending: false }).limit(limit),
      )
    },
    async search(text, limit = 30) {
      const t = text.replace(/[%,()]/g, ' ').trim()
      if (!t) return []
      return check(
        await supabase
          .from('items')
          .select('*')
          .or(`title.ilike.%${t}%,body.ilike.%${t}%`)
          .order('updated_at', { ascending: false })
          .limit(limit),
      )
    },
    async create(item) {
      return check(await supabase.from('items').insert(item).select().single())
    },
    async update(id, patch) {
      return check(await supabase.from('items').update(patch).eq('id', id).select().single())
    },
    async remove(id) {
      check(await supabase.from('items').delete().eq('id', id))
    },
    async bulkInsert(items) {
      if (!items.length) return []
      return check(await supabase.from('items').insert(items).select())
    },
  },

  files: {
    async list() {
      return check(await supabase.from('files').select('*').order('created_at', { ascending: false }))
    },
    async upload(file, folder = '') {
      const uid = await currentUserId()
      const path = `${uid}/${crypto.randomUUID()}-${safeName(file.name)}`
      check(
        await supabase.storage
          .from(STORAGE_BUCKET)
          .upload(path, file, { contentType: file.type || undefined, upsert: false }),
      )
      try {
        return check(
          await supabase
            .from('files')
            .insert({ name: file.name, path, folder, size: file.size, mime_type: file.type || null })
            .select()
            .single(),
        )
      } catch (e) {
        await supabase.storage.from(STORAGE_BUCKET).remove([path])
        throw e
      }
    },
    async getUrl(file, { download = false } = {}) {
      const data = check(
        await supabase.storage
          .from(STORAGE_BUCKET)
          .createSignedUrl(file.path, 60 * 60, download ? { download: file.name } : undefined),
      )
      return data.signedUrl
    },
    async update(id, patch) {
      return check(await supabase.from('files').update(patch).eq('id', id).select().single())
    },
    async remove(file) {
      check(await supabase.storage.from(STORAGE_BUCKET).remove([file.path]))
      check(await supabase.from('files').delete().eq('id', file.id))
    },
  },

  settings: {
    async get() {
      const row = check(await supabase.from('user_settings').select('settings').maybeSingle())
      return row?.settings ?? null
    },
    async save(settings) {
      const user_id = await currentUserId()
      check(await supabase.from('user_settings').upsert({ user_id, settings }))
    },
  },

  // Avisos programados (tabla notifications). Los envía la Edge Function "send-notifications".
  notifications: {
    async listUpcoming(limit = 30) {
      return check(
        await supabase
          .from('notifications')
          .select('*')
          .in('status', ['pending', 'sending', 'failed'])
          .order('remind_at', { ascending: true })
          .limit(limit),
      )
    },
    async listRecent(limit = 30) {
      return check(
        await supabase
          .from('notifications')
          .select('*')
          .in('status', ['sent', 'skipped'])
          .order('sent_at', { ascending: false, nullsFirst: false })
          .limit(limit),
      )
    },
    async listForItem(itemId) {
      return check(await supabase.from('notifications').select('*').eq('item_id', itemId))
    },
    async create(row) {
      return check(await supabase.from('notifications').insert(row).select().single())
    },
    async update(id, patch) {
      return check(await supabase.from('notifications').update(patch).eq('id', id).select().single())
    },
    async remove(id) {
      check(await supabase.from('notifications').delete().eq('id', id))
    },
    async markAllRead() {
      check(
        await supabase
          .from('notifications')
          .update({ read_at: new Date().toISOString() })
          .eq('status', 'sent')
          .is('read_at', null),
      )
    },
  },

  // Dispositivos suscritos a Web Push (tabla push_subscriptions).
  push: {
    available: true,
    async listSubscriptions() {
      return check(await supabase.from('push_subscriptions').select('*').order('created_at', { ascending: false }))
    },
    async saveSubscription({ endpoint, p256dh, auth, device_name, user_agent }) {
      const user_id = await currentUserId()
      return check(
        await supabase
          .from('push_subscriptions')
          .upsert(
            { user_id, endpoint, p256dh, auth, device_name, user_agent, last_seen_at: new Date().toISOString() },
            { onConflict: 'endpoint' },
          )
          .select()
          .single(),
      )
    },
    async removeSubscription(id) {
      check(await supabase.from('push_subscriptions').delete().eq('id', id))
    },
    async removeByEndpoint(endpoint) {
      check(await supabase.from('push_subscriptions').delete().eq('endpoint', endpoint))
    },
    // Envía un aviso de prueba solo a los dispositivos del usuario con sesión iniciada.
    async sendTest() {
      const { data, error } = await supabase.functions.invoke('send-notifications', { body: { action: 'test' } })
      if (error) {
        let detail = ''
        try {
          detail = (await error.context?.json())?.error || ''
        } catch {
          /* sin detalle */
        }
        throw new Error(
          detail ||
            'No se pudo contactar con la función "send-notifications". ¿Está publicada en Supabase? (ver docs/NOTIFICACIONES.md)',
        )
      }
      return data
    },
  },

  // PACO AI: cada paso de la conversación pasa por la Edge Function "paco-ai",
  // que guarda la clave de la IA. Las herramientas se ejecutan aquí (src/lib/ai).
  ai: {
    available: true,
    async status() {
      return invokeAi({ action: 'status' })
    },
    async chat(messages) {
      return invokeAi({ action: 'chat', messages })
    },
  },
}

async function invokeAi(body) {
  const { data, error } = await supabase.functions.invoke('paco-ai', { body })
  if (!error) return data
  let detail = null
  try {
    detail = await error.context?.json()
  } catch {
    /* sin detalle */
  }
  const e = new Error(
    detail?.error ||
      'No se pudo contactar con PACO AI. ¿Está publicada la función "paco-ai" en Supabase? (ver docs/PACO_AI.md)',
  )
  e.code = detail?.code || (error.context?.status ? 'http_' + error.context.status : 'unreachable')
  throw e
}
