"""Package browser-reader assets as a self-contained offline ZIP."""

from __future__ import annotations

import json
import os
import tempfile
import zipfile
from pathlib import Path


OFFLINE_INDEX_NAME = "index.html"


_HTML = r'''<!doctype html>
<html lang="__LANG__">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>
:root{--bg:#f6f1e7;--fg:#29251f;--surface:#fffdf7;--border:#d8d0c3;--muted:#746d63;--active:#fde047;--hover:#eee7da}
:root.night{--bg:#171717;--fg:#eee9df;--surface:#242424;--border:#404040;--muted:#aaa39a;--active:#a16207;--hover:#333}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.65 Georgia,serif}
header{position:sticky;top:0;z-index:10;display:flex;justify-content:space-between;align-items:center;padding:12px 18px;background:var(--surface);border-bottom:1px solid var(--border)}
h1{font:600 18px/1.2 system-ui,sans-serif;margin:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
button,select,input{font:inherit}button,select{color:var(--fg);background:var(--surface);border:1px solid var(--border);border-radius:7px;padding:6px 10px;cursor:pointer}
main{display:block;max-width:860px;margin:auto;padding:26px 24px 120px}
main.has-pages{display:grid;grid-template-columns:minmax(260px,360px) minmax(0,720px);gap:28px;max-width:1140px}
#page-panel{display:none;position:sticky;top:82px;align-self:start;background:var(--surface);border:1px solid var(--border);border-radius:18px;overflow:hidden}
main.has-pages #page-panel{display:block}
#page-label{padding:9px 14px;color:var(--muted);font:12px system-ui,sans-serif;text-transform:uppercase;letter-spacing:.12em;border-bottom:1px solid var(--border)}
#page-image{display:block;width:100%;height:auto}
#text{background:var(--surface);border:1px solid var(--border);border-radius:18px;padding:28px 34px;min-height:50vh}
.page h2{font:600 12px system-ui,sans-serif;text-transform:uppercase;letter-spacing:.12em;color:var(--muted);margin:24px 0 8px}.page:first-child h2{margin-top:0}
p{margin:.7em 0}h1,h2,h3,h4{line-height:1.25}article h1{font-size:2rem}article h2{font-size:1.55rem}article h3{font-size:1.25rem}article pre{overflow:auto;background:var(--bg);border:1px solid var(--border);border-radius:10px;padding:14px}article code{background:var(--hover);border-radius:4px;padding:1px 4px;font-size:.9em}article pre code{background:transparent;padding:0}blockquote{border-left:4px solid var(--border);margin:1em 0;padding-left:1em;color:var(--muted)}table{width:100%;border-collapse:collapse;margin:1em 0}th,td{border:1px solid var(--border);padding:6px 10px;text-align:left}hr{border:0;border-top:1px solid var(--border);margin:2em 0}.word{border-radius:3px;padding:1px 2px}.word.active{background:var(--active);color:#1f1b14}.word:hover{background:var(--hover);cursor:pointer}
#pip{position:fixed;z-index:30;left:24px;top:76px;width:280px;min-width:180px;max-width:70vw;background:#000;border:1px solid var(--border);border-radius:12px;overflow:hidden;box-shadow:0 12px 34px #0007;resize:both}
#pip.hidden{display:none}#pipbar{display:flex;justify-content:space-between;align-items:center;padding:5px 8px;background:#202020;color:#fff;font:12px system-ui,sans-serif;cursor:move;user-select:none}#pipbar button{padding:0 5px;background:transparent;color:#fff;border:0}video{display:block;width:100%;height:calc(100% - 28px);object-fit:contain;background:#000}
footer{position:fixed;z-index:20;left:0;right:0;bottom:0;background:var(--surface);border-top:1px solid var(--border);box-shadow:0 -8px 24px #0002;padding:12px 18px;font:13px system-ui,sans-serif}
.controls{display:flex;gap:12px;align-items:center;max-width:900px;margin:auto}.controls input[type=range]{flex:1}.time{font-variant-numeric:tabular-nums;color:var(--muted);min-width:42px}.play{width:45px;height:45px;border-radius:50%;font-size:18px;padding:0}.check{display:flex;gap:6px;align-items:center;color:var(--muted);white-space:nowrap}
#show-presenter{display:none}
@media(max-width:760px){main,main.has-pages{display:block;padding:16px 14px 120px}main.has-pages #page-panel{position:relative;top:auto;margin-bottom:18px;max-height:45vh}#page-image{max-height:45vh;object-fit:contain}#text{padding:22px 20px}#pip{width:220px}.check{display:none}}
</style>
</head>
<body>
<header><h1 id="title"></h1><div><button id="show-presenter">Show presenter</button> <button id="theme">Night</button></div></header>
<main id="reader-main"><aside id="page-panel"><div id="page-label">Document</div><img id="page-image" alt="Current document page"></aside><article id="text"></article></main>
<div id="pip"><div id="pipbar"><span>Presenter</span><button id="hide-presenter" aria-label="Hide presenter">x</button></div><video id="presenter" playsinline preload="auto"></video></div>
<audio id="narration" preload="auto"></audio>
<footer><div class="controls"><button class="play" id="play" aria-label="Play">&#9654;</button><span class="time" id="now">0:00</span><input id="seek" type="range" min="0" step="0.1" value="0"><span class="time" id="total">0:00</span><select id="rate" aria-label="Playback speed"><option>.75x</option><option selected>1x</option><option>1.25x</option><option>1.5x</option><option>2x</option></select><label class="check"><input id="scroll" type="checkbox" checked> Auto-scroll</label></div></footer>
<script id="reader-data" type="application/json">__MANIFEST__</script>
<script>
(()=>{
const data=JSON.parse(document.getElementById('reader-data').textContent), $=id=>document.getElementById(id);
document.title=data.title; $('title').textContent=data.title;
const presenter=$('presenter'), narration=$('narration'), hasPresenter=!!data.presenter;
presenter.src=hasPresenter?data.presenter:''; narration.src=data.audio; const media=hasPresenter?presenter:narration;
if(!hasPresenter)$('pip').style.display='none';
const words=[], pages=new Map();
for(const chunk of data.chunks){const page=chunk.pages[0]||0;if(!pages.has(page))pages.set(page,[]);pages.get(page).push(chunk);for(const word of chunk.words)words.push({...word,page});}
const sourceTypes=new Set(['md','markdown','mdown']), hasMarkdown=data.source_markdown&&sourceTypes.has(String(data.source_type||'').toLowerCase());
const hasPages=!!(data.pages&&data.pages.files&&Object.keys(data.pages.files).length);
if(hasPages)$('reader-main').classList.add('has-pages');
function textSpan(token){const span=document.createElement('span');const idx=wordIndex++;span.className='word';span.dataset.i=idx;span.dataset.start=words[idx]?.start||0;span.textContent=token;return span}
function appendTimedText(parent,text){for(const token of text.match(/\s+|[^\s]+/g)||[]){if(/^\s+$/.test(token)||!/[A-Za-z0-9]/.test(token)){parent.append(token);continue}parent.appendChild(textSpan(token));}}
function renderInline(parent,text){const re=/(`[^`]+`|\*\*[^*]+\*\*|__[^_]+__|~~[^~]+~~|\[[^\]]+\]\([^)]+\)|\*[^*\s][^*]*[^*\s]\*)/g;let last=0;for(const match of text.matchAll(re)){const token=match[0],idx=match.index||0;if(idx>last)appendTimedText(parent,text.slice(last,idx));let el;if(token.startsWith('`')){el=document.createElement('code');appendTimedText(el,token.slice(1,-1));}else if(token.startsWith('**')||token.startsWith('__')){el=document.createElement('strong');renderInline(el,token.slice(2,-2));}else if(token.startsWith('~~')){el=document.createElement('del');renderInline(el,token.slice(2,-2));}else if(token.startsWith('[')){const link=token.match(/^\[([^\]]+)\]\(([^)]+)\)$/),href=link&&/^(https?:|mailto:|#)/i.test(link[2].trim())?link[2].trim():'';el=document.createElement(href?'a':'span');if(href){el.href=href;if(!href.startsWith('#')){el.target='_blank';el.rel='noreferrer';}}renderInline(el,link?link[1]:token);}else{el=document.createElement('em');renderInline(el,token.slice(1,-1));}parent.appendChild(el);last=idx+token.length;}if(last<text.length)appendTimedText(parent,text.slice(last));}
function blockStart(line,next){return /^#{1,6}\s+/.test(line)||/^>\s?/.test(line)||/^(\s*)([-+*]|\d+[.)])\s+/.test(line)||/^\s*(```+|~~~+)/.test(line)||/^\s{0,3}[-*_]{3,}\s*$/.test(line)||(line.includes('|')&&!!next&&/^\s*\|?[\s:|-]{3,}\|[\s:|.-]*$/.test(next));}
function renderMarkdown(markdown){const lines=markdown.replace(/\r\n?/g,'\n').replace(/^---\s*\n[\s\S]*?\n---\s*(?:\n|$)/,'').replace(/<!--[\s\S]*?-->/g,'').split('\n');let i=0;while(i<lines.length){const line=lines[i];if(!line.trim()){i++;continue}const fence=line.match(/^\s*(```+|~~~+)/);if(fence){i++;const code=[];while(i<lines.length&&!lines[i].trim().startsWith(fence[1]))code.push(lines[i++]);if(i<lines.length)i++;const pre=document.createElement('pre'),codeEl=document.createElement('code');appendTimedText(codeEl,code.join('\n'));pre.appendChild(codeEl);$('text').appendChild(pre);continue}const heading=line.match(/^(#{1,6})\s+(.+)$/);if(heading){const el=document.createElement('h'+Math.min(heading[1].length,4));renderInline(el,heading[2]);$('text').appendChild(el);i++;continue}if(/^\s{0,3}[-*_]{3,}\s*$/.test(line)){$('text').appendChild(document.createElement('hr'));i++;continue}if(line.includes('|')&&i+1<lines.length&&/^\s*\|?[\s:|-]{3,}\|[\s:|.-]*$/.test(lines[i+1])){const tableLines=[line];i+=2;while(i<lines.length&&lines[i].includes('|')&&lines[i].trim())tableLines.push(lines[i++]);const rows=tableLines.map(row=>row.trim().replace(/^\|/,'').replace(/\|$/,'').split('|').map(cell=>cell.trim())),table=document.createElement('table'),thead=document.createElement('thead'),tbody=document.createElement('tbody'),headRow=document.createElement('tr');for(const cell of rows.shift()||[]){const th=document.createElement('th');renderInline(th,cell);headRow.appendChild(th)}thead.appendChild(headRow);for(const row of rows){const tr=document.createElement('tr');for(const cell of row){const td=document.createElement('td');renderInline(td,cell);tr.appendChild(td)}tbody.appendChild(tr)}table.append(thead,tbody);$('text').appendChild(table);continue}const list=line.match(/^(\s*)([-+*]|\d+[.)])\s+(.+)$/);if(list){const ordered=/\d/.test(list[2]),el=document.createElement(ordered?'ol':'ul');while(i<lines.length){const item=lines[i].match(/^(\s*)([-+*]|\d+[.)])\s+(.+)$/);if(!item||/\d/.test(item[2])!==ordered)break;const li=document.createElement('li');renderInline(li,item[3].replace(/^\[[ xX]\]\s+/,''));el.appendChild(li);i++;}$('text').appendChild(el);continue}if(/^>\s?/.test(line)){const quote=[];while(i<lines.length&&/^>\s?/.test(lines[i]))quote.push(lines[i++].replace(/^>\s?/,''));const el=document.createElement('blockquote');renderInline(el,quote.join(' '));$('text').appendChild(el);continue}const para=[line.trim()];i++;while(i<lines.length&&lines[i].trim()&&!blockStart(lines[i],lines[i+1]))para.push(lines[i++].trim());const p=document.createElement('p');renderInline(p,para.join(' '));$('text').appendChild(p);}}
let wordIndex=0;
if(hasMarkdown){renderMarkdown(data.source_markdown)}else{for(const [page,chunks] of [...pages].sort((a,b)=>a[0]-b[0])){const section=document.createElement('section');section.className='page';const h=document.createElement('h2');h.textContent='Page '+(page||'');section.appendChild(h);for(const chunk of chunks){const p=document.createElement('p');if(chunk.words.length){for(const word of chunk.words){const span=textSpan(word.word+' ');span.dataset.start=word.start;p.appendChild(span);}}else p.textContent=chunk.text;section.appendChild(p);}$('text').appendChild(section);}}
const spans=[...document.querySelectorAll('.word')]; let active=-1,lastPage=-1;
function fmt(s){s=Math.max(0,Math.floor(s||0));return Math.floor(s/60)+':'+String(s%60).padStart(2,'0')}
function showPage(page){if(!hasPages||page===lastPage)return;lastPage=page;const file=data.pages.files[String(page)];if(!file)return;$('page-label').textContent=page?'Page '+page:'Document';$('page-image').src=data.pages.dir+'/'+file;}
function find(t){let lo=0,hi=words.length-1,best=-1;while(lo<=hi){const mid=(lo+hi)>>1;if(words[mid].start<=t){best=mid;lo=mid+1}else hi=mid-1}return best>=0&&t<words[best].end?best:best;}
function update(){const t=media.currentTime||0,idx=find(t);$('now').textContent=fmt(t);$('seek').value=String(t);if(idx!==active){if(active>=0)spans[active]?.classList.remove('active');active=idx;if(active>=0){const el=spans[active];el?.classList.add('active');showPage(words[active].page);if($('scroll').checked)el?.scrollIntoView({behavior:'smooth',block:'center'});}}}
media.addEventListener('timeupdate',update);media.addEventListener('play',()=>{$('play').innerHTML='&#10074;&#10074;'});media.addEventListener('pause',()=>{$('play').innerHTML='&#9654;'});media.addEventListener('loadedmetadata',()=>{$('seek').max=String(media.duration||data.duration);$('total').textContent=fmt(media.duration||data.duration)});
$('play').onclick=()=>media.paused?media.play():media.pause();$('seek').oninput=e=>{media.currentTime=Number(e.target.value);update()};$('rate').onchange=e=>media.playbackRate=parseFloat(e.target.value);spans.forEach(s=>s.onclick=()=>{media.currentTime=Number(s.dataset.start);update()});
const saved=(()=>{try{return localStorage.getItem('reader-theme')}catch{return null}})();if(saved==='night')document.documentElement.classList.add('night');function themeLabel(){$('theme').textContent=document.documentElement.classList.contains('night')?'Day':'Night'}themeLabel();$('theme').onclick=()=>{document.documentElement.classList.toggle('night');themeLabel();try{localStorage.setItem('reader-theme',document.documentElement.classList.contains('night')?'night':'day')}catch{}};
$('hide-presenter').onclick=()=>{$('pip').classList.add('hidden');$('show-presenter').style.display='inline-block'};$('show-presenter').onclick=()=>{$('pip').classList.remove('hidden');$('show-presenter').style.display='none'};
let drag=null;$('pipbar').onpointerdown=e=>{if(e.target.tagName==='BUTTON')return;const r=$('pip').getBoundingClientRect();drag={dx:e.clientX-r.left,dy:e.clientY-r.top};$('pipbar').setPointerCapture(e.pointerId)};$('pipbar').onpointermove=e=>{if(!drag)return;$('pip').style.left=Math.max(0,Math.min(innerWidth-$('pip').offsetWidth,e.clientX-drag.dx))+'px';$('pip').style.top=Math.max(0,Math.min(innerHeight-$('pip').offsetHeight-70,e.clientY-drag.dy))+'px'};$('pipbar').onpointerup=()=>drag=null;
if(hasPages)showPage(([...pages.keys()].sort((a,b)=>a-b)[0])||0);
})();
</script>
</body></html>'''


def _html_for_manifest(manifest: dict) -> str:
    """Render an offline reader page with manifest data embedded safely."""
    manifest_json = json.dumps(manifest, ensure_ascii=False).replace("<", "\\u003c")
    title = str(manifest.get("title") or "Screencastgen Reader")
    # Text substitutions use JSON encoding for the title element separately below;
    # the HTML title is escaped conservatively.
    import html

    return (
        _HTML.replace("__LANG__", html.escape(str(manifest.get("language") or "en"), quote=True))
        .replace("__TITLE__", html.escape(title))
        .replace("__MANIFEST__", manifest_json)
    )


def build_offline_reader_archive(manifest_path: str, output_path: str) -> str:
    """Create a ZIP that opens locally without an HTTP server."""
    manifest_file = Path(manifest_path).resolve()
    output_dir = manifest_file.parent
    with manifest_file.open("r", encoding="utf-8") as fh:
        manifest = json.load(fh)

    assets = [manifest_file]
    for key in ("audio", "presenter"):
        name = manifest.get(key)
        if name:
            assets.append((output_dir / name).resolve())
    pages = manifest.get("pages") or {}
    pages_dir = pages.get("dir")
    for name in (pages.get("files") or {}).values():
        if pages_dir and name:
            assets.append((output_dir / pages_dir / name).resolve())

    root = str(output_dir.resolve())
    for asset in assets:
        if os.path.commonpath([root, str(asset)]) != root:
            raise ValueError(f"Reader asset escapes output directory: {asset}")
        if not asset.is_file():
            raise FileNotFoundError(f"Reader asset not found: {asset}")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(suffix=".zip", dir=str(output.parent))
    os.close(fd)
    try:
        with zipfile.ZipFile(tmp_name, "w") as archive:
            archive.writestr(
                OFFLINE_INDEX_NAME,
                _html_for_manifest(manifest),
                compress_type=zipfile.ZIP_DEFLATED,
            )
            for asset in assets:
                archive.write(
                    asset,
                    asset.relative_to(output_dir).as_posix(),
                    compress_type=zipfile.ZIP_STORED,
                )
        os.replace(tmp_name, output)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
    return str(output)
