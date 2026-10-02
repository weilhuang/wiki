import DefaultTheme from 'vitepress/theme'
import { h } from 'vue'
import Home from './components/Home.vue'
import PostList from './components/PostList.vue'
import ArticleMeta from './components/ArticleMeta.vue'
import './style.css'
export default {
  extends: DefaultTheme,
  Layout: () => h(DefaultTheme.Layout, null, { 'doc-before': () => h(ArticleMeta) }),
  enhanceApp({ app }) { app.component('WikiHome', Home); app.component('PostList', PostList) }
}
