<script setup>
import { withBase } from 'vitepress'
import { data as posts } from '../../posts.data.mjs'
const categories = [...new Set(posts.map(p => p.category))]
const layers = [
  ['01', '语言与运行时', '并发、内存与执行模型'],
  ['02', '框架与中间件', '调用链、事务与数据流'],
  ['03', '分布式与云', '失败、协调与系统边界'],
  ['04', '可观测性与安全', '证据、身份与信任边界'],
  ['05', '工程实践', '测试、交付与持续演进']
]
</script>
<template>
  <main class="wiki-home" id="main-content">
    <section class="home-hero" aria-labelledby="home-title">
      <div class="hero-copy">
        <p class="eyebrow"><span></span> BACKEND · SYSTEMS · ENGINEERING</p>
        <h1 id="home-title">把机制读懂，<br><span>把问题想透。</span></h1>
        <p class="hero-description">从一段代码走到系统边界。记录后端开发中的原理、验证与取舍，留下值得反复翻阅的笔记。</p>
        <div class="hero-actions"><a class="primary-link" :href="withBase('/guide/knowledge-map.html')">打开知识地图 <span aria-hidden="true">↗</span></a><a class="text-link" :href="withBase('/blog/')">阅读文章 <span aria-hidden="true">→</span></a></div>
        <div class="hero-footnote"><span>{{ posts.length }} 篇完整笔记</span><i aria-hidden="true">/</i><span>{{ categories.length }} 个已写主题</span><i aria-hidden="true">/</i><span>持续整理</span></div>
      </div>
      <aside class="reading-map" aria-label="知识组织方式">
        <div class="map-heading"><span>知识的层次</span><span class="map-symbol" aria-hidden="true">⌘</span></div>
        <ol><li v-for="layer in layers" :key="layer[0]"><span class="map-number">{{ layer[0] }}</span><div><strong>{{ layer[1] }}</strong><p>{{ layer[2] }}</p></div><span class="map-dot" aria-hidden="true"></span></li></ol>
        <a :href="withBase('/guide/knowledge-map.html')">查看阅读路径与收录范围 <span aria-hidden="true">→</span></a>
      </aside>
    </section>
    <section class="recent-section" aria-labelledby="recent-title">
      <div class="section-heading"><div><p class="eyebrow">RECENT NOTES</p><h2 id="recent-title">最近整理</h2></div><a class="text-link" :href="withBase('/blog/')">全部文章 <span aria-hidden="true">↗</span></a></div>
      <div class="recent-grid"><article v-for="(post, index) in posts.slice(0, 4)" :key="post.url" class="note-card">
        <div class="card-topline"><span class="category-mark">{{ post.category }}</span><span class="note-number">{{ String(index + 1).padStart(2, '0') }}</span></div>
        <h3><a :href="withBase(post.url)">{{ post.title }}</a></h3><p>{{ post.description }}</p>
        <div class="note-card-footer"><time :datetime="post.date">{{ post.date }}</time><span>约 {{ post.minutes }} 分钟</span><span class="card-arrow" aria-hidden="true">↗</span></div>
      </article></div>
    </section>
    <section class="reading-principle" aria-label="阅读建议"><span class="principle-label">HOW TO READ</span><p>先看一个具体问题，再追到它背后的机制。<br>代码、边界条件与参考资料，尽量放在一起。</p><a :href="withBase('/about.html')">关于这些笔记 <span aria-hidden="true">→</span></a></section>
  </main>
</template>
