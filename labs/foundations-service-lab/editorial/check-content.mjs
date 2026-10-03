import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
const root = path.resolve(process.argv[2] || '.');
const wiki = path.resolve(process.argv[3] || (() => { throw Error('Provide an existing wiki checkout with installed dependencies'); })());
const require = createRequire(path.join(wiki, 'package.json'));
const MarkdownIt = require('markdown-it');
const matter = require('gray-matter');
const { JSDOM } = require('jsdom');
const dom = new JSDOM('<!doctype html><html><body></body></html>');
globalThis.window = dom.window;
globalThis.document = dom.window.document;
const { default: mermaid } = await import(pathToFileURL(path.join(wiki, 'node_modules/mermaid/dist/mermaid.esm.mjs')));
mermaid.initialize({ startOnLoad: false, securityLevel: 'strict' });
const { compileCode } = await import(pathToFileURL(path.join(wiki, 'scripts/render-codehike.mjs')));
const { validateTopic } = await import(pathToFileURL(path.join(wiki, 'scripts/knowledge.mjs')));
const terms = JSON.parse(fs.readFileSync(path.join(wiki, 'content/terms.json'), 'utf8'));
const parser = new MarkdownIt();
const hash = value => crypto.createHash('sha256').update(value).digest('hex');
const snippets = JSON.parse(fs.readFileSync(path.join(root, 'snippets.json'), 'utf8'));
const mapping = { 'blocking-waiting.md': 'knowledge/foundations/operating-systems/blocking-waiting.md', 'assertion-counterexamples.md': 'knowledge/foundations/testing/assertion-counterexamples.md' };
const checks = [];
for (const [name, source] of Object.entries(mapping)) {
  const body = fs.readFileSync(path.join(root, 'articles', name), 'utf8');
  const { data, content } = matter(body);
  validateTopic({ ...data, source }, { terms });
  assert.equal(data.status, 'review');
  assert.equal(parser.parse(content, {}).filter(t => t.type === 'heading_open' && t.tag === 'h1').length, 1);
  assert(!body.includes('/workspace/') && !body.includes('/root/'));
  let diagrams = 0, steps = 0;
  for (const token of parser.parse(content, {})) {
    if (token.type !== 'fence') continue;
    const [lang, ...meta] = token.info.trim().split(/\s+/);
    if (lang === 'mermaid') {
      assert.match(token.content, /accTitle:/);
      assert.match(token.content, /accDescr:/);
      assert(!/classDef|%%\{init|<br|click /.test(token.content));
      await mermaid.parse(token.content);
      diagrams++;
    } else {
      const { result, html } = await compileCode({ value: token.content, lang, meta: meta.join(' ') });
      assert(html.includes('data-codehike-version="1.1.0"'));
      if (meta.includes('steps')) {
        assert(result.annotations.some(a => a.name === 'step'));
        assert(!result.code.includes('!step'));
        steps++;
      }
    }
  }
  checks.push({ path: 'articles/' + name, sha256: hash(body), mermaidParsed: diagrams, codeHikeSteps: steps });
}
for (const entry of snippets) {
  const doc = fs.readFileSync(path.join(root, entry.article), 'utf8');
  const marker = `<!-- snippet: ${entry.id} -->`;
  assert(doc.includes(marker));
  const block = doc.slice(doc.indexOf(marker) + marker.length).match(/```python steps\n([\s\S]*?)\n```/);
  assert(block);
  const { result } = await compileCode({ value: block[1] + '\n', lang: 'python', meta: 'steps' });
  let original = fs.readFileSync(path.join(root, entry.source), 'utf8');
  if (entry.lines) original = original.split('\n').slice(entry.lines[0] - 1, entry.lines[1]).join('\n') + '\n';
  assert.equal(result.code, original, 'clean source mismatch: ' + entry.id);
  checks.push({ snippet: entry.id, cleanSourceSha256: hash(result.code), lines: entry.lines || null, source: entry.source, annotations: result.annotations.length });
}
console.log(JSON.stringify({ status: 'pass', checks, limitations: ['Mermaid syntax parsing only, no browser rendering', 'Code Hike compilation and source equality only, no browser step interaction', 'Integration/independent review/deployment are separate'] }, null, 2));
