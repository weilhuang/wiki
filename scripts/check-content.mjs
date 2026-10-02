import { validateReadiness, paths, taxonomy } from './knowledge.mjs'
import { generateViews } from './generate-views.mjs'
generateViews()
const topics=validateReadiness()
console.log(`Knowledge: ${taxonomy.length} domains, ${topics.length} canonical topics, ${paths.length} reference-based routes; applicable evidence and publication gates passed`)
