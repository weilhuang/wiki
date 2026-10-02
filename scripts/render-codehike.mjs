/** Build-side only. Public API: codehike@1.1.0; requires react@18.3.1 at build time. */
import { highlight } from 'codehike/code';

export const escapeHtml = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const cssProperties = new Set(['color','background','backgroundColor','fontStyle','fontWeight','textDecoration','opacity','colorScheme']);
const styleAttr = style => escapeHtml(Object.entries(style).filter(([key,value])=>cssProperties.has(key)&&value!=null).map(([key,value])=>`${key.replace(/[A-Z]/g,c=>'-'+c.toLowerCase())}:${String(value)}`).join(';'));
const blockAt = (annotation,line) => 'fromLineNumber' in annotation && annotation.fromLineNumber <= line && line <= annotation.toLineNumber;

/** Grammar annotation offsets use cleaned code, one-based lines/columns, inclusive ends. */
export function tokenLines(code) {
  const lines = [[]];
  let column = 1;
  for(const token of code.tokens) {
    const [value,color,rest={}] = typeof token === 'string' ? [token] : token;
    const pieces = value.split('\n');
    pieces.forEach((part,index)=>{
      if(index) { lines.push([]); column=1; }
      if(part) { lines.at(-1).push({value:part,style:{color,...rest},from:column,toExclusive:column+part.length}); column+=part.length; }
    });
  }
  return lines;
}

/** Returns <pre> only so VitePress 1.6.4 retains its code wrapper/copy/line numbers. */
export function renderHighlightedCode(code) {
  const lines=tokenLines(code);
  // Keep a single final line break out of rendered block, so it doesn't add an empty numbered line.
  // Do not trim content within the final line. This is a documented choice versus VitePress trimEnd().
  if(code.code.endsWith('\n') && lines.length>1) lines.pop();
  const focus=code.annotations.filter(a=>a.name==='focus');
  const body=lines.map((line,index)=>{
    const n=index+1;
    const block=code.annotations.filter(a=>blockAt(a,n));
    const inline=code.annotations.filter(a=>'lineNumber' in a && a.lineNumber===n);
    const focused=block.some(a=>a.name==='focus') || inline.some(a=>a.name==='focus');
    const marked=block.some(a=>a.name==='mark');
    const className=['line',focused?'has-focus':'',marked?'highlighted':''].filter(Boolean).join(' ');
    // Step keys are annotation queries, not token offsets. The host may progressively enhance these.
    const stepIds=block.filter(a=>a.name==='step').map(a=>a.query);
    const segments=line.map(t=>{
      const cuts=new Set([t.from,t.toExclusive]);
      for(const a of inline) { if(t.from<a.fromColumn && a.fromColumn<t.toExclusive) cuts.add(a.fromColumn); const end=a.toColumn+1; if(t.from<end && end<t.toExclusive) cuts.add(end); }
      const offsets=[...cuts].sort((a,b)=>a-b);
      return offsets.slice(0,-1).map((from,i)=>{
        const end=offsets[i+1];
        const active=inline.filter(a=>a.fromColumn<=from && end<=a.toColumn+1);
        const mark=active.some(a=>a.name==='mark');
        const text=t.value.slice(from-t.from,end-t.from);
        return `<span${mark?' class="ch-inline-mark"':''} style="${styleAttr(t.style)}">${escapeHtml(text)}</span>`;
      }).join('');
    }).join('') || '<wbr>';
    return `<span class="${className}" data-line="${n}"${stepIds.length?` data-ch-steps="${escapeHtml(JSON.stringify(stepIds))}"`:''}>${segments}</span>`;
  }).join('\n');
  return `<pre class="vp-code codehike${focus.length?' has-focused-lines':''}" v-pre tabindex="0" data-codehike-version="1.1.0"><code>${body}</code></pre>`;
}

/** Use in async preprocessing. Do not place async highlight directly in markdown.highlight. */
export async function compileCode(raw) {
  const result=await highlight(raw,'github-from-css');
  const cleanLines = result.code.replace(/\n$/, '').split('\n');
  for (const annotation of result.annotations) {
    if (!['focus', 'mark', 'step'].includes(annotation.name)) throw new Error(`Unsupported Code Hike annotation: ${annotation.name}`);
    if (annotation.name === 'step' && !('fromLineNumber' in annotation)) throw new Error('Code Hike step must select full lines');
    if ('fromLineNumber' in annotation && (!Number.isInteger(annotation.fromLineNumber) || !Number.isInteger(annotation.toLineNumber) || annotation.fromLineNumber < 1 || annotation.toLineNumber < annotation.fromLineNumber || annotation.toLineNumber > cleanLines.length)) throw new Error('Code Hike annotation line range is outside the cleaned source');
    if ('lineNumber' in annotation && (annotation.lineNumber < 1 || annotation.lineNumber > cleanLines.length || annotation.fromColumn < 1 || annotation.toColumn < annotation.fromColumn || annotation.toColumn > cleanLines[annotation.lineNumber-1].length)) throw new Error('Code Hike annotation column range is outside the cleaned source');
  }
  return {result,html:renderHighlightedCode(result)};
}
