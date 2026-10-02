import DefaultTheme from 'vitepress/theme'
import MermaidDiagram from './components/MermaidDiagram.vue'
import CodeWalkthrough from './components/CodeWalkthrough.vue'
import './codehike.css'
import PostList from './components/PostList.vue'

export default {
  extends: DefaultTheme,
  enhanceApp({ app }) { app.component('PostList', PostList); app.component('MermaidDiagram', MermaidDiagram); app.component('CodeWalkthrough', CodeWalkthrough) }
}
