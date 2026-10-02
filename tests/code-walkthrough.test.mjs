import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { JSDOM } from 'jsdom'
import { parse, compileScript } from 'vue/compiler-sfc'
import { compileCode } from '../scripts/render-codehike.mjs'

test('Walkthrough step → full reset preserves authored focus and fully readable code', async () => {
  const themeCss = readFileSync('node_modules/vitepress/dist/client/theme-default/styles/components/vp-doc.css', 'utf8')
  const codeCss = readFileSync('docs/.vitepress/theme/codehike.css', 'utf8')
  const dom = new JSDOM(`<!doctype html><style>${themeCss}\n${codeCss}</style><div class="vp-doc" id="app"></div>`)
  const saved = new Map(['window', 'document', 'Element', 'SVGElement'].map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]))
  for (const key of saved.keys()) Object.defineProperty(globalThis, key, { value:dom.window[key], configurable:true, writable:true })
  let app
  try {
    // Load the real SFC after installing the DOM. Only the VitePress button leaf
    // is replaced; the component's template, handlers and computed HTML run unchanged.
    const { createApp, h, nextTick, ref } = await import('vue')
    const { descriptor } = parse(readFileSync('docs/.vitepress/theme/components/CodeWalkthrough.vue', 'utf8'))
    const source = compileScript(descriptor, { id:'walkthrough-readability', inlineTemplate:true }).content
      .replace(/import \{ VPButton \} from 'vitepress\/theme'/, `import { h } from 'vue'\nconst VPButton = { props:['text', 'theme'], render() { return h('button', this.$attrs, this.text) } }`)
      .replace(/from (['"])vue\1/g, `from ${JSON.stringify(import.meta.resolve('vue'))}`)
    const { default:CodeWalkthrough } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`)
    const { html } = await compileCode({ value:'// !focus(1) authored focus\nconst first = 1;\nconst second = 2;\nconst third = 3;\n', lang:'js', meta:'' })
    const payload = { html, lang:'js', lines:3, steps:[{ from:2, to:3, text:'Inspect the following lines' }] }
    const encoded = ref(encodeURIComponent(JSON.stringify(payload)))
    app = createApp({ render:() => h(CodeWalkthrough, { encoded:encoded.value }) })
    app.mount(dom.window.document.querySelector('#app'))
    const document = dom.window.document
    const assertReadable = () => {
      for (const line of document.querySelectorAll('.codehike .line:not(.has-focus)')) {
        const style = dom.window.getComputedStyle(line)
        assert.equal(style.opacity, '1', 'VitePress focus styling must not dim other code lines')
        assert.equal(style.filter, 'none', 'VitePress focus styling must not blur other code lines')
      }
      assert.equal(document.querySelectorAll('.has-focus').length, 1, 'authored focus must survive step changes')
      assert.equal(document.querySelectorAll('.codehike .line').length, 3)
    }
    const buttons = () => [...document.querySelectorAll('.step-controls button')]
    assertReadable()
    for (let iteration = 0; iteration < 2; iteration++) {
      buttons()[1].click()
      await nextTick()
      assert.deepEqual([...document.querySelectorAll('.ch-step-active')].map(line => line.dataset.line), ['2', '3'])
      assert.equal(buttons()[1].getAttribute('aria-pressed'), 'true')
      assertReadable()
      buttons()[0].click()
      await nextTick()
      assert.equal(document.querySelectorAll('.ch-step-active').length, 0)
      assert.equal(buttons()[0].getAttribute('aria-pressed'), 'true')
      assertReadable()
    }
    buttons()[1].click()
    await nextTick()
    encoded.value = encodeURIComponent(JSON.stringify({ ...payload, steps:[{ from:1, to:1, text:'A different walkthrough' }] }))
    await nextTick()
    assert.equal(document.querySelectorAll('.ch-step-active').length, 0, 'changing the payload resets the selected step')
    assert.equal(buttons()[0].getAttribute('aria-pressed'), 'true')
    assertReadable()
  } finally {
    app?.unmount()
    dom.window.close()
    for (const [key, descriptor] of saved) {
      if (descriptor) Object.defineProperty(globalThis, key, descriptor)
      else delete globalThis[key]
    }
  }
})
