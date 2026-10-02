// VitePress manages frontmatter.head in both SSR and client-side navigation.
export function managedPageHead(relativePath, frontmatter, siteUrl) {
  const path = relativePath.replace(/index\.md$/, '').replace(/\.md$/, '.html')
  const head = (frontmatter.head || []).filter(([tag, attributes]) =>
    !(tag === 'link' && attributes?.rel === 'canonical') &&
    !(path === '404.html' && tag === 'meta' && attributes?.name === 'robots'))
  if (path === '404.html') return [...head, ['meta', { name: 'robots', content: 'noindex' }]]
  const target = frontmatter.canonical ? frontmatter.canonical.replace(/^\//, '') : path
  return [...head, ['link', { rel: 'canonical', href: new URL(target, siteUrl).href }]]
}
