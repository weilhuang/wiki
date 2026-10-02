import { readPosts } from '../../scripts/content.mjs'
export default { watch: ['../blog/*.md'], load: () => readPosts() }
