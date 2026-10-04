import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import { createHash } from 'node:crypto'
import MarkdownIt from 'markdown-it'
import { compileCode } from '../scripts/render-codehike.mjs'

const hash = text => createHash('sha256').update(text).digest('hex')
const markdown = new MarkdownIt()

test('Declared plain Code Hike excerpts retain exact source without unsupported step annotations', async () => {
  for (const file of readdirSync('content/plain-snippets').filter(name => name.endsWith('.json'))) {
    for (const entry of JSON.parse(readFileSync('content/plain-snippets/' + file, 'utf8'))) {
      assert.equal(entry.presentation, 'plain')
      const source = readFileSync(entry.source, 'utf8')
      assert.equal(hash(source), entry.sourceSha256, entry.id + ' source changed')
      const doc = readFileSync(entry.doc, 'utf8')
      const marker = `<!-- snippet: ${entry.id} -->`
      assert.equal(doc.split(marker).length, 2, entry.id + ' needs one source marker')
      const block = markdown.parse(doc.slice(doc.indexOf(marker) + marker.length), {})[0]
      assert.equal(block?.type, 'fence')
      const [language, ...attributes] = block.info.trim().split(/\s+/)
      assert.equal(language, entry.language)
      assert.equal(attributes.includes('steps'), false, entry.id + ' has no supported step renderer')
      const result = (await compileCode({ value: block.content, lang: language, meta: '' })).result
      assert.equal(result.annotations.length, 0)
      assert.equal(hash(result.code), entry.cleanCodeSha256)
      const selected = entry.lines ? source.split('\n').slice(entry.lines[0] - 1, entry.lines[1]).join('\n') + '\n' : source
      assert.equal(result.code, selected, entry.id + ' source bytes differ')
    }
  }
})
