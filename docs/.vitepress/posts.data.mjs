import { readPosts } from '../../scripts/content.mjs'
export default { watch: ['../learn/**/*.md', '../../curriculum.mjs'], load: () => readPosts() }
