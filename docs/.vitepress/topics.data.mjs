import { readFileSync } from 'node:fs'
import { readTopics, taxonomy, kinds, registries } from '../../scripts/knowledge.mjs'
export default {
  watch: ['../knowledge/**/*.md','../cases/**/*.md','../troubleshooting/**/*.md','../../content/**/*'],
  load() {return { topics:readTopics(), domains:taxonomy.map(({id,title})=>({id,title})), kinds, terms:registries().terms, questions:JSON.parse(readFileSync('content/review-questions.json','utf8')) }}
}
