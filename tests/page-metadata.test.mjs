import test from 'node:test'
import assert from 'node:assert/strict'
import { managedPageHead } from '../scripts/page-metadata.mjs'
import { syncNotFoundMetadata } from '../docs/.vitepress/theme/not-found-metadata.mjs'
import { JSDOM } from 'jsdom'

test('Canonical metadata belongs to each client-managed page, including directory routes', () => {
  const url = 'https://example.com/notes/'
  assert.deepEqual(managedPageHead('index.md', {}, url), [['link', { rel:'canonical', href:url }]])
  assert.deepEqual(managedPageHead('learn/go/index.md', {}, url), [['link', { rel:'canonical', href:url+'learn/go/' }]])
  const head = managedPageHead('learn/go/ownership.md', { head:[['link', {rel:'canonical', href:'https://old.example/'}], ['meta', {name:'theme-color',content:'#fff'}]] }, url)
  assert.equal(head.filter(([tag,attrs])=>tag==='link'&&attrs.rel==='canonical').length,1)
  assert.equal(head.at(-1)[1].href,url+'learn/go/ownership.html')
  assert.equal(head[0][1].name,'theme-color')
  assert.equal(managedPageHead('compat.md', {canonical:'/learn/go/ownership.html'}, url).at(-1)[1].href,url+'learn/go/ownership.html')
})

test('404 noindex is client-managed and is not carried to a normal page', () => {
  const url = 'https://example.com/notes/'
  assert.deepEqual(managedPageHead('404.md', {}, url), [['meta', {name:'robots', content:'noindex'}]])
  assert.ok(!managedPageHead('learn/go/ownership.md', {}, url).some(([tag,attrs])=>tag==='meta'&&attrs.name==='robots'))
})

test('The route hook owns only the default-404 robots tag across repeated visits', () => {
  const dom = new JSDOM('<!doctype html><head><meta name="robots" content="max-snippet:50"></head>')
  const document = dom.window.document
  syncNotFoundMetadata(document, true)
  syncNotFoundMetadata(document, true)
  assert.equal(document.querySelectorAll('meta[data-wiki-not-found]').length, 1)
  assert.equal(document.querySelector('meta[data-wiki-not-found]').content, 'noindex')
  syncNotFoundMetadata(document, false)
  assert.equal(document.querySelectorAll('meta[data-wiki-not-found]').length, 0)
  assert.equal(document.querySelector('meta[name=robots]').content, 'max-snippet:50')
  dom.window.close()
})
