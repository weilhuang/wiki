import { validateReadiness, curriculum } from './curriculum.mjs'
const chapters = validateReadiness()
console.log(`Curriculum: ${curriculum.paths.length} complete paths, ${chapters.length} ready chapters, guides and source-bound execution evidence passed`)
