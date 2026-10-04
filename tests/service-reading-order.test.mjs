import test from 'node:test'
import assert from 'node:assert/strict'
import { JSDOM } from 'jsdom'
import { createMarkdownRenderer } from 'vitepress'
import { readTopics, paths } from '../scripts/knowledge.mjs'
import { topicContextMarkdown } from '../scripts/topic-context.mjs'

test('Reservation reading suggestions lead from HTTP to transactions to RPC in rendered context', async () => {
  const topics = readTopics()
  const ids = ['go.gin-service-contract', 'go.sql-gorm-boundaries', 'go.grpc-service-contract']
  const route = paths.find(path => path.source === 'paths/go-reliable-services.md')
  assert.deepEqual(route.stages.flatMap(stage => stage.readings.map(item => item.topic)).filter(id => ids.includes(id)), ids)
  const markdown = await createMarkdownRenderer(process.cwd())
  for (let index = 0; index < ids.length; index++) {
    const topic = topics.find(item => item.id === ids[index])
    const expected = index + 1 < ids.length ? [ids[index + 1]] : []
    assert.deepEqual((topic.recommendedBefore || []).map(edge => edge.id), expected)
    const document = new JSDOM(markdown.render(topicContextMarkdown(topic, topics).bottom)).window.document
    const heading = [...document.querySelectorAll('p')].find(element => element.textContent === '建议先读本文再读')
    const next = heading?.nextElementSibling
    const links = next ? [...next.querySelectorAll('a')].map(a => a.getAttribute('href')) : []
    assert.deepEqual(links, expected.map(id => topics.find(item => item.id === id).url))
    document.defaultView.close()
  }
})
