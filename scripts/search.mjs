// Self-contained: VitePress serializes this function for the browser search client.
export function tokenizeChinese(text) {
  const tokens = []
  for (const part of text.toLowerCase().match(/[a-z0-9_]+|[\u3400-\u9fff]+/g) || []) {
    if (/^[a-z0-9_]+$/.test(part)) { tokens.push(part); continue }
    for (let i = 0; i < part.length; i++) {
      tokens.push(part[i])
      if (i + 1 < part.length) tokens.push(part.slice(i, i + 2))
      if (i + 2 < part.length) tokens.push(part.slice(i, i + 3))
    }
  }
  return [...new Set(tokens)]
}
