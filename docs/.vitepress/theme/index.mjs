import DefaultTheme from 'vitepress/theme'
import MermaidDiagram from './components/MermaidDiagram.vue'
import CodeWalkthrough from './components/CodeWalkthrough.vue'
import './codehike.css'
import PostList from './components/PostList.vue'
import { syncNotFoundMetadata } from './not-found-metadata.mjs'

export default {
  extends: DefaultTheme,
  enhanceApp({ app, router }) {
    app.component('PostList', PostList); app.component('MermaidDiagram', MermaidDiagram); app.component('CodeWalkthrough', CodeWalkthrough)
    if (typeof document !== 'undefined') {
      const previous = router.onAfterRouteChange ?? router.onAfterRouteChanged
      router.onAfterRouteChange = async to => {
        await previous?.(to)
        syncNotFoundMetadata(document, Boolean(router.route.data.isNotFound))
      }
    }
  }
}
