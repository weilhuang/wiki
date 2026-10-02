// Self-contained: VitePress serializes this function for the browser search client.
export function tokenizeChinese(text) {
  const tokens = []
  for (const part of text.toLowerCase().match(/[a-z0-9_]+|[\u3400-\u9fff]+/g) || []) {
    if (/^[a-z0-9_]+$/.test(part)) { tokens.push(part); continue }
    for (let i = 0; i < part.length; i++) {
      tokens.push(part[i])
      if (i + 1 < part.length) tokens.push(part.slice(i, i + 2))
      if (i + 2 < part.length) tokens.push(part.slice(i, i + 3))
    }
  }
  return [...new Set(tokens)]
}

// VitePress 1.6.4's supported local-search _render hook runs only during indexing.
// Keep narrative sections; verification history and generated relationship lists do not compete with them.
export async function renderSearch(source, env, md) {
  const { readTopics } = await import('./knowledge.mjs')
  const { readFileSync } = await import('node:fs')
  const topics=readTopics(), topic=topics.find(t=>t.source===env.relativePath)
  env.wikiSearch=true
  const clean=source.replace(/<details class="verification-appendix">[\s\S]*?<\/details>/g,'')
  let html=md.render(clean,env)
  if(env.frontmatter?.search===false || (env.frontmatter?.status && env.frontmatter.status!=='published'))return ''
  if(!topic)return html
  const escape=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))
  const intents=JSON.parse(readFileSync('content/search-intents.json','utf8')).filter(q=>q.topic===topic.id)
  const {JSDOM}=await import('jsdom'),dom=new JSDOM(html)
  for(const intent of intents){const heading=dom.window.document.getElementById(intent.anchor);if(!heading)throw Error(`Search intent anchor missing: ${topic.id}#${intent.anchor}`);const p=dom.window.document.createElement('p');p.textContent='检索问法：'+intent.query;heading.after(p)}
  if(topic.searchTerms?.length){const h1=dom.window.document.querySelector('h1');h1?.insertAdjacentHTML('afterend',`<p>术语与别名：${topic.searchTerms.map(escape).join('、')}</p>`)}
  html=dom.window.document.body.innerHTML;dom.window.close();return html
}
