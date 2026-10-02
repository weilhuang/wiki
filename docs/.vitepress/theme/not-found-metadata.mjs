// VitePress's built-in 404 bypasses transformPageData. Own its robots tag explicitly.
export const notFoundRobots = ['meta', { name:'robots', content:'noindex', 'data-wiki-not-found':'' }]

export function syncNotFoundMetadata(document, isNotFound) {
  const tags = [...document.head.querySelectorAll('meta[data-wiki-not-found]')]
  if (!isNotFound) { for (const tag of tags) tag.remove(); return }
  let tag = tags.shift()
  for (const duplicate of tags) duplicate.remove()
  if (!tag) { tag = document.createElement('meta'); document.head.appendChild(tag) }
  for (const [name, value] of Object.entries(notFoundRobots[1])) tag.setAttribute(name, value)
}
