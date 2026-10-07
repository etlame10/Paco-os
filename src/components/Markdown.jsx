// Markdown mínimo y seguro para las respuestas de PACO AI: párrafos, listas,
// títulos, **negrita**, *cursiva* y `código`. Crea elementos de React (nunca HTML
// sin escapar), así que un texto malicioso no puede inyectar nada en la página.
import { Fragment } from 'react'

function inline(text, keyBase) {
  const out = []
  const re = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*\s][^*]*\*)/g
  let last = 0
  let m
  let i = 0
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index))
    const tok = m[0]
    const key = `${keyBase}-${i++}`
    if (tok.startsWith('**')) out.push(<strong key={key}>{tok.slice(2, -2)}</strong>)
    else if (tok.startsWith('`')) out.push(<code key={key}>{tok.slice(1, -1)}</code>)
    else out.push(<em key={key}>{tok.slice(1, -1)}</em>)
    last = m.index + tok.length
  }
  if (last < text.length) out.push(text.slice(last))
  return out
}

export default function Markdown({ text }) {
  const lines = String(text || '').replace(/\r/g, '').split('\n')
  const blocks = []
  let list = null
  let para = []

  const flushPara = () => {
    if (para.length) blocks.push({ type: 'p', lines: para })
    para = []
  }
  const flushList = () => {
    if (list) blocks.push(list)
    list = null
  }

  for (const line of lines) {
    const bullet = line.match(/^\s*[-*•]\s+(.*)$/)
    const numbered = line.match(/^\s*(\d+)[.)]\s+(.*)$/)
    const heading = line.match(/^\s*#{1,6}\s+(.*)$/)
    if (bullet || numbered) {
      flushPara()
      const type = bullet ? 'ul' : 'ol'
      if (!list || list.type !== type) {
        flushList()
        list = { type, items: [] }
      }
      list.items.push(bullet ? bullet[1] : numbered[2])
    } else if (heading) {
      flushPara()
      flushList()
      blocks.push({ type: 'h', text: heading[1] })
    } else if (!line.trim()) {
      flushPara()
      flushList()
    } else {
      flushList()
      para.push(line)
    }
  }
  flushPara()
  flushList()

  return (
    <div className="md">
      {blocks.map((b, i) => {
        if (b.type === 'h') return <p key={i} className="md-h">{inline(b.text, i)}</p>
        if (b.type === 'p')
          return (
            <p key={i}>
              {b.lines.map((l, j) => (
                <Fragment key={j}>
                  {j > 0 && <br />}
                  {inline(l, `${i}-${j}`)}
                </Fragment>
              ))}
            </p>
          )
        const Tag = b.type
        return (
          <Tag key={i}>
            {b.items.map((it, j) => (
              <li key={j}>{inline(it, `${i}-${j}`)}</li>
            ))}
          </Tag>
        )
      })}
    </div>
  )
}
