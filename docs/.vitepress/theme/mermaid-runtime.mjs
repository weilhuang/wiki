let renderer
export async function renderMermaid(id, source) {
  if (!renderer) renderer = import('mermaid').then(({ default: mermaid }) => {
    mermaid.initialize({
      startOnLoad: false, securityLevel: 'strict', theme: 'base', look: 'classic',
      htmlLabels: false, maxTextSize: 50000, suppressErrorRendering: true,
      secure: ['securityLevel', 'startOnLoad', 'maxTextSize', 'htmlLabels', 'theme', 'themeVariables'],
      fontFamily: 'system-ui, -apple-system, "Noto Sans CJK SC", "Microsoft YaHei", sans-serif',
      themeVariables: {
        fontSize: '15px', background: '#ffffff', primaryColor: '#e5f3ff', primaryTextColor: '#004f99',
        primaryBorderColor: '#d9e7f2', secondaryColor: '#f5faff', tertiaryColor: '#ffffff',
        lineColor: '#7e8790', textColor: '#004f99', mainBkg: '#e5f3ff', nodeBorder: '#d9e7f2',
        edgeLabelBackground: '#f5faff', clusterBkg: '#ffffff', clusterBorder: '#d4dfe8',
        actorBkg: '#e5f3ff', actorBorder: '#d9e7f2', actorTextColor: '#004f99', actorLineColor: '#a6adb3',
        signalColor: '#7e8790', signalTextColor: '#004f99', labelBoxBkgColor: '#f5faff', labelBoxBorderColor: '#d9e7f2',
        labelTextColor: '#004f99', noteBkgColor: '#f5faff', noteBorderColor: '#d9e7f2', noteTextColor: '#004f99'
      },
      flowchart: { htmlLabels: false, curve: 'rounded', nodeSpacing: 34, rankSpacing: 46, padding: 18, useMaxWidth: false },
      sequence: { useMaxWidth: false, actorMargin: 32, messageMargin: 30, diagramMarginX: 16, diagramMarginY: 16, wrap: true }
    })
    return mermaid
  })
  const mermaid = await renderer
  const isFlow = /^\s*(flowchart|graph)\b/m.test(source)
  const style = '\nclassDef default fill:#e5f3ff,stroke:#d9e7f2,color:#004f99,stroke-width:1px,rx:16,ry:16;\nclassDef decision fill:#f5faff,stroke:#d9e7f2,color:#004f99,stroke-width:1px,stroke-dasharray:3 3,rx:16,ry:16;\nlinkStyle default stroke:#7e8790,stroke-width:1px;'
  const rendered = (await mermaid.render(id, source + (isFlow ? style : ''))).svg
  const document = new DOMParser().parseFromString(rendered, 'image/svg+xml')
  for (const rect of document.querySelectorAll('.edgeLabel rect.background')) {
    for (const [name, amount] of [['x', -8], ['y', -3], ['width', 16], ['height', 6]]) {
      const value = Number(rect.getAttribute(name))
      if (Number.isFinite(value)) rect.setAttribute(name, String(value + amount))
    }
    rect.setAttribute('rx', '12'); rect.setAttribute('ry', '12')
    rect.setAttribute('style', 'fill:#f5faff;stroke:#d9e7f2;stroke-width:1px')
  }
  return document.documentElement.outerHTML
}
