// Lectura del contenido de documentos para PACO AI (PDF y archivos de texto).
//
// Se hace en el navegador del usuario:
//   1. El archivo se descarga de Supabase Storage con una URL firmada que solo puede
//      obtener su dueño (RLS del bucket privado "paco-files").
//   2. El texto se extrae aquí con pdf.js (libre, sin servicios externos). Al modelo
//      solo le llega el TEXTO del documento autorizado, nunca el archivo.
//   3. Se lee por tramos de páginas para no enviar documentos enormes de golpe.
// pdf.js se carga solo la primera vez que hace falta (no pesa en el resto de la app).

export const DOC_MAX_BYTES = 25 * 1024 * 1024
export const DOC_CHUNK_CHARS = 40000

const TEXT_EXT = /\.(txt|md|markdown|csv|tsv|json|log)$/i

// 'pdf' | 'text' | null (no se puede leer)
export function documentKind(file) {
  const mime = String(file?.mime_type || '').toLowerCase()
  const name = String(file?.name || '')
  if (mime === 'application/pdf' || /\.pdf$/i.test(name)) return 'pdf'
  if (mime.startsWith('text/') || mime === 'application/json' || TEXT_EXT.test(name)) return 'text'
  return null
}

let pdfjsPromise = null
async function loadPdfjs() {
  if (!pdfjsPromise) {
    pdfjsPromise = Promise.all([import('pdfjs-dist'), import('pdfjs-dist/build/pdf.worker.min.mjs?url')]).then(([lib, worker]) => {
      lib.GlobalWorkerOptions.workerSrc = worker.default
      return lib
    })
  }
  return pdfjsPromise
}

// Etiquetas que la app usa para dar contexto al modelo: un documento no puede imitarlas.
const RESERVED_TAGS = /<\/?\s*(contexto_app|documentos_adjuntos|documento|inicio_documento|fin_documento)[^>]*>/gi
export const cleanText = (s) => String(s || '').replace(RESERVED_TAGS, ' ').replace(/\u0000/g, '')

function clampPage(n, total, fallback) {
  const v = Number(n)
  return Number.isFinite(v) && v >= 1 ? Math.min(Math.floor(v), total) : fallback
}

/**
 * Extrae el texto de un PDF por páginas, hasta maxChars caracteres.
 * Devuelve { pages_total, from_page, to_page, text, next_from_page }.
 */
export async function extractPdfText(bytes, { from, to, maxChars = DOC_CHUNK_CHARS, pdfjs } = {}) {
  const lib = pdfjs || (await loadPdfjs())
  // isEvalSupported: false -> pdf.js nunca evalúa código del PDF. Tampoco se ejecuta JavaScript del documento.
  const task = lib.getDocument({ data: bytes, isEvalSupported: false, disableFontFace: true, enableXfa: false })
  try {
    const doc = await task.promise
    const total = doc.numPages
    const start = clampPage(from, total, 1)
    const end = Math.max(start, clampPage(to, total, total))
    let text = ''
    let last = start - 1
    for (let p = start; p <= end; p++) {
      const page = await doc.getPage(p)
      const content = await page.getTextContent()
      let pageText = ''
      for (const it of content.items) {
        if (typeof it.str !== 'string') continue
        pageText += it.str + (it.hasEOL ? '\n' : '')
      }
      page.cleanup()
      let chunk = `[Página ${p}]\n${cleanText(pageText).replace(/[ \t]+\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim()}\n\n`
      if (text.length + chunk.length > maxChars) {
        if (p > start) break
        chunk = chunk.slice(0, maxChars) + '… [página recortada]\n'
      }
      text += chunk
      last = p
    }
    return { pages_total: total, from_page: start, to_page: last, text: text.trim(), next_from_page: last < total ? last + 1 : null }
  } finally {
    await task.destroy()
  }
}

// Archivos de texto: se trocean en "partes" de maxChars caracteres (from/to = número de parte).
export function extractPlainText(bytes, { from, maxChars = DOC_CHUNK_CHARS } = {}) {
  const all = cleanText(new TextDecoder('utf-8').decode(bytes))
  const parts = Math.max(1, Math.ceil(all.length / maxChars))
  const part = clampPage(from, parts, 1)
  return {
    pages_total: parts,
    from_page: part,
    to_page: part,
    text: all.slice((part - 1) * maxChars, part * maxChars),
    next_from_page: part < parts ? part + 1 : null,
    unit: 'partes',
  }
}
