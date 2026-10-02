// Change these values together when moving to a different repository or host.
export const site = {
  title: '工程札记',
  repository: 'weilhuang/wiki',
  origin: 'https://weilhuang.github.io',
  base: '/wiki/'
}
site.url = new URL(site.base, site.origin).href
site.repoUrl = `https://github.com/${site.repository}`
