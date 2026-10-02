export function wikiMarkdown(md, codeCache) {
  const fence = md.renderer.rules.fence
  md.renderer.rules.fence = (tokens, index, options, env, renderer) => {
    const token = tokens[index]
    const [lang, ...attrs] = token.info.trim().split(/\s+/)
    if (lang === 'mermaid') {
      if (/%%\{|^\s*---|^\s*click\s|<\/?(?:script|iframe|img)\b/im.test(token.content)) throw new Error('Mermaid 图不允许指令覆盖、点击动作或嵌入 HTML；使用站点统一的安全配置')
      if (!/^\s*accTitle\s*:/m.test(token.content) || !/^\s*accDescr\s*:/m.test(token.content)) throw new Error('每个 Mermaid 图需要 accTitle 和 accDescr 文字说明')
      return `<MermaidDiagram encoded="${encodeURIComponent(token.content)}" />\n`
    }
    if (attrs.includes('steps')) {
      const { result, html } = codeCache.get(token.content, lang)
      const steps = result.annotations.filter(a => a.name === 'step' && 'fromLineNumber' in a).map(a => ({ from: a.fromLineNumber, to: a.toLineNumber, text: a.query }))
      if (!steps.length || steps.some(s => !s.text)) throw new Error('steps 代码块需要带有解释文字的 Code Hike !step 注释')
      const payload = { html, steps, lang: result.lang, lines: result.code.replace(/\n$/, '').split('\n').length }
      return `<CodeWalkthrough encoded="${encodeURIComponent(JSON.stringify(payload))}" />\n`
    }
    return fence(tokens, index, options, env, renderer)
  }
}
