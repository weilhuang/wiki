import test from 'node:test'
import assert from 'node:assert/strict'
import { escapeXml, rss, readPosts } from '../scripts/content.mjs'
import { tokenizeChinese } from '../scripts/search.mjs'
test('RSS escapes all XML metacharacters', () => {
  assert.equal(escapeXml('<&>"\''), '&lt;&amp;&gt;&quot;&apos;')
  const xml = rss([{ title: '<script>&', description: 'A & B', date: '2026-10-02', url: '/blog/test.html', tags: ['<tag>'] }])
  assert.ok(!xml.includes('<script>')); assert.ok(xml.includes('https://weilhuang.github.io/wiki/blog/test.html'))
})
test('Chinese search supports substrings and English identifiers', () => {
  const terms = tokenizeChinese('事务失效 Context cancellation')
  assert.ok(terms.includes('事务')); assert.ok(terms.includes('失效')); assert.ok(terms.includes('context'))
  assert.deepEqual(tokenizeChinese(''), [])
})
test('Published metadata is complete and deterministic', () => {
  const posts = readPosts(); assert.ok(posts.length > 0)
  assert.deepEqual(readPosts(), posts)
  assert.equal(new Set(posts.map(p => p.url)).size, posts.length)
})
