// Build-time only. Never import this module from the browser theme.
import { readdirSync, readFileSync } from 'node:fs'
import { join, relative } from 'node:path'
import MarkdownIt from 'markdown-it'
import { compileCode } from './render-codehike.mjs'

const parser = new MarkdownIt()
const normalizeLanguage = lang => (lang || 'text').replace(/\{.*?\}/g, '').split(':')[0]
const keyFor = (value, lang) => `${normalizeLanguage(lang)}\0${value}`
const walk = dir => readdirSync(dir, { withFileTypes: true }).flatMap(e => e.isDirectory() ? (e.name.startsWith('.') ? [] : walk(join(dir, e.name))) : e.name.endsWith('.md') ? [join(dir, e.name)] : [])

export async function createCodeCache(root = process.cwd()) {
  const entries = new Map()
  async function refresh() {
    for (const file of walk(join(root, 'docs'))) {
      const source = readFileSync(file, 'utf8')
      if (/^\s*<<<\s/m.test(source)) throw new Error(`${relative(root, file)}: Code Hike 不支持隐式代码导入，请将完整代码放在 fenced block 中`)
      for (const token of parser.parse(source, {})) {
        if (token.type !== 'fence') continue
        const [rawLang = 'text', ...attrs] = token.info.trim().split(/\s+/)
        const lang = normalizeLanguage(rawLang)
        if (lang === 'mermaid') continue
        const key = keyFor(token.content, lang)
        if (!entries.has(key)) entries.set(key, await compileCode({ value: token.content, lang, meta: attrs.join(' ') }))
      }
    }
  }
  await refresh()
  return {
    refresh,
    get(value, lang) {
      const entry = entries.get(keyFor(value, lang))
      if (!entry) throw new Error(`Code Hike cache miss (${lang}). 重新运行 npm run docs:dev 或 docs:build；不会静默切换到其他高亮器。`)
      return entry
    }
  }
}
