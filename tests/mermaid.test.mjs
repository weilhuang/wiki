import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import MarkdownIt from 'markdown-it'
import { join } from 'node:path'
import { JSDOM } from 'jsdom'

test('All authored Mermaid diagrams parse with the pinned strict renderer', async () => {
  const dom = new JSDOM('<!doctype html><html><body></body></html>')
  globalThis.window = dom.window
  globalThis.document = dom.window.document
  const { default: mermaid } = await import('mermaid')
  mermaid.initialize({ startOnLoad: false, securityLevel: 'strict', htmlLabels: false })
  const walk = dir => readdirSync(dir, { withFileTypes: true }).flatMap(e => e.isDirectory() ? (e.name.startsWith('.') ? [] : walk(join(dir, e.name))) : e.name.endsWith('.md') ? [join(dir, e.name)] : [])
  const parser = new MarkdownIt()
  const diagrams = walk('docs').flatMap(file => parser.parse(readFileSync(file, 'utf8'), {}).filter(t => t.type === 'fence' && t.info === 'mermaid'))
  assert.ok(diagrams.length >= 7)
  const types = new Set()
  for (const token of diagrams) {
    assert.match(token.content, /accTitle:/)
    assert.match(token.content, /accDescr:/)
    const parsed = await mermaid.parse(token.content)
    assert.ok(parsed)
    types.add(parsed.diagramType)
  }
  assert.ok(types.size >= 2, 'Flow and sequence coverage required')
  dom.window.close()
})
