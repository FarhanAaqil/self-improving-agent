// Minimal server-sent events parser. We stream with fetch (not EventSource) so the
// API key can travel in a header instead of the URL.

export interface SseMessage {
  id: number | null
  event: string
  data: string
}

export function createSseParser(onMessage: (msg: SseMessage) => void) {
  let buffer = ''

  const dispatch = (block: string) => {
    let id: number | null = null
    let event = 'message'
    const data: string[] = []
    for (const rawLine of block.split('\n')) {
      const line = rawLine.endsWith('\r') ? rawLine.slice(0, -1) : rawLine
      if (!line || line.startsWith(':')) continue
      const colon = line.indexOf(':')
      const field = colon === -1 ? line : line.slice(0, colon)
      const value = colon === -1 ? '' : line.slice(colon + 1).replace(/^ /, '')
      if (field === 'id') id = Number.isFinite(Number(value)) ? Number(value) : null
      else if (field === 'event') event = value
      else if (field === 'data') data.push(value)
    }
    if (data.length || event !== 'message') onMessage({ id, event, data: data.join('\n') })
  }

  return {
    feed(chunk: string) {
      buffer += chunk.replace(/\r\n/g, '\n')
      let boundary = buffer.indexOf('\n\n')
      while (boundary !== -1) {
        dispatch(buffer.slice(0, boundary))
        buffer = buffer.slice(boundary + 2)
        boundary = buffer.indexOf('\n\n')
      }
    },
  }
}
