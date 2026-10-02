import test from 'node:test'
import assert from 'node:assert/strict'
import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import matter from 'gray-matter'
import { JSDOM } from 'jsdom'
import { createMarkdownRenderer } from 'vitepress'
import { generateViews } from '../scripts/generate-views.mjs'
import { topicContextMarkdown } from '../scripts/topic-context.mjs'

test('Generated task and topic labels render as strong text beside Chinese prose', async () => {
  const topics = generateViews()
  const md = await createMarkdownRenderer(process.cwd())
  const labels = ['综合任务', '小目标', '阶段任务', '适用范围', '理解先修']
  const covered = new Set()
  const walk = dir => readdirSync(dir, { withFileTypes:true }).flatMap(entry => entry.isDirectory()
    ? (entry.name.startsWith('.') ? [] : walk(join(dir, entry.name)))
    : entry.name.endsWith('.md') ? [join(dir, entry.name)] : [])
  const sources = walk('docs').flatMap(file => {
    const { data, content } = matter(readFileSync(file, 'utf8'))
    return data.generated ? [{ file, content }] : []
  })
  sources.push(...topics.map(topic => ({ file:topic.source, content:topicContextMarkdown(topic, topics).scope })))
  for (const { file, content } of sources) {
    const document = new JSDOM(md.render(content)).window.document
    const strong = [...document.querySelectorAll('strong')].map(element => element.textContent)
    for (const label of labels) {
      const count = content.split(`**${label}`).length - 1
      if (!count) continue
      covered.add(label)
      assert.equal(strong.filter(text => text === label).length, count, `${file}: ${label} must render as strong text`)
    }
    document.querySelectorAll('pre, code').forEach(element => element.remove())
    assert.doesNotMatch(document.body.textContent, /\*\*[^*\n]+\*\*/, `${file}: unparsed bold delimiters in non-code text`)
    document.defaultView.close()
  }
  assert.deepEqual([...covered].sort(), [...labels].sort())
})
