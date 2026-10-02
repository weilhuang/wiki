import { readPosts } from './content.mjs'
const posts = readPosts()
if (posts.length < 1) throw new Error('至少需要一篇完整文章才可发布')
console.log(`Content metadata: ${posts.length} articles passed`)
