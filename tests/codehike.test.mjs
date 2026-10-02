import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { compileCode, tokenLines } from '../scripts/render-codehike.mjs'
import { createCodeCache } from '../scripts/code-cache.mjs'
import { wikiMarkdown } from '../scripts/markdown-extensions.mjs'
import MarkdownIt from 'markdown-it'

test('Code Hike escapes HTML, strips annotation comments, preserves marks and copy text', async () => {
  const { result, html } = await compileCode({ value: '// !focus(1:2) focus\nconst x = "<script>&";\n\n// !mark[/status/]\nconst status = true;\n', lang: 'js', meta: '' })
  assert.equal(tokenLines(result).map(line => line.map(t => t.value).join('')).join('\n'), result.code)
  assert.ok(html.includes('&lt;script&gt;&amp;'))
  assert.ok(!html.includes('<script>'))
  assert.ok(!result.code.includes('!focus'))
  assert.ok(html.includes('ch-inline-mark'))
  assert.ok(html.includes('<wbr>'))
})
test('Unsupported annotation handlers fail explicitly', async () => {
  await assert.rejects(() => compileCode({ value: '// !unknown(1) test\nconst x = 1;\n', lang: 'js', meta: '' }), /Unsupported/)
  await assert.rejects(() => compileCode({ value: '// !step(1:20) bad range\nconst x = 1;\n', lang: 'js', meta: '' }), /outside the cleaned source/)
})
test('Published Code Hike steps match verified clean snippets and exact ranges', async () => {
  const groups = [
    { fixture:'code-walkthroughs.json', source:'frameworks/spring-transactions/proxy-call-chain', lang:'java' },
    { fixture:'go-context-walkthroughs.json', source:'go/concurrency/context-cancellation', lang:'go' }
  ]
  for (const group of groups) {
    const cases = JSON.parse(readFileSync(`tests/fixtures/${group.fixture}`, 'utf8'))
    const markdown = readFileSync(`docs/knowledge/${group.source}.md`, 'utf8')
    const fences = new MarkdownIt().parse(markdown, {}).filter(t => t.type === 'fence' && t.info === `${group.lang} steps`)
    assert.equal(fences.length, cases.length)
    for (let i = 0; i < fences.length; i++) {
      const { result } = await compileCode({ value:fences[i].content, lang:group.lang, meta:'steps' })
      assert.equal(result.code, cases[i].code)
      assert.deepEqual(result.annotations.filter(a => a.name === 'step').map(a => [a.fromLineNumber, a.toLineNumber]), cases[i].steps.map(s => [s.startLine, s.endLine]))
    }
  }
})
test('Build cache handles real fences and rejects misses; Mermaid source rejects unsafe overrides', async () => {
  const cache = await createCodeCache()
  assert.throws(() => cache.get('new uncached code', 'js'), /cache miss/)
  const md = new MarkdownIt()
  wikiMarkdown(md, cache)
  assert.throws(() => md.render('```mermaid\n%%{init: {securityLevel: loose}}%%\nflowchart TB\n```'), /不允许/)
  assert.throws(() => md.render('```mermaid\nflowchart TB\nA-->B\n```'), /accTitle/)
})

test('Python source links remain base-aware downloads, not invented HTML routes',()=>{
  const md=new MarkdownIt();wikiMarkdown(md,{})
  const html=md.render('[完整模型](/examples/order-extraction-protocol-model.py)')
  assert.match(html,/href="\/wiki\/examples\/order-extraction-protocol-model\.py"/)
  assert.match(html,/download=""/);assert.ok(!html.includes('.py.html'))
})
