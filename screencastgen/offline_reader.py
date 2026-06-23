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
main{display:grid;grid-template-columns:minmax(260px,360px) minmax(0,720px);gap:28px;max-width:1140px;margin:auto;padding:26px 24px 120px}
#page-panel{position:sticky;top:82px;align-self:start;background:var(--surface);border:1px solid var(--border);border-radius:18px;overflow:hidden}
#page-label{padding:9px 14px;color:var(--muted);font:12px system-ui,sans-serif;text-transform:uppercase;letter-spacing:.12em;border-bottom:1px solid var(--border)}
#page-image{display:block;width:100%;height:auto}#page-empty{padding:30px;color:var(--muted);text-align:center}
#text{background:var(--surface);border:1px solid var(--border);border-radius:18px;padding:28px 34px;min-height:50vh}
.page h2{font:600 12px system-ui,sans-serif;text-transform:uppercase;letter-spacing:.12em;color:var(--muted);margin:24px 0 8px}.page:first-child h2{margin-top:0}
p{margin:.7em 0}.word{border-radius:3px;padding:1px 2px}.word.active{background:var(--active);color:#1f1b14}.word:hover{background:var(--hover);cursor:pointer}
#pip{position:fixed;z-index:30;left:24px;top:76px;width:280px;min-width:180px;max-width:70vw;background:#000;border:1px solid var(--border);border-radius:12px;overflow:hidden;box-shadow:0 12px 34px #0007;resize:both}
#pip.hidden{display:none}#pipbar{display:flex;justify-content:space-between;align-items:center;padding:5px 8px;background:#202020;color:#fff;font:12px system-ui,sans-serif;cursor:move;user-select:none}#pipbar button{padding:0 5px;background:transparent;color:#fff;border:0}video{display:block;width:100%;height:calc(100% - 28px);object-fit:contain;background:#000}
footer{position:fixed;z-index:20;left:0;right:0;bottom:0;background:var(--surface);border-top:1px solid var(--border);box-shadow:0 -8px 24px #0002;padding:12px 18px;font:13px system-ui,sans-serif}
.controls{display:flex;gap:12px;align-items:center;max-width:900px;margin:auto}.controls input[type=range]{flex:1}.time{font-variant-numeric:tabular-nums;color:var(--muted);min-width:42px}.play{width:45px;height:45px;border-radius:50%;font-size:18px;padding:0}.check{display:flex;gap:6px;align-items:center;color:var(--muted);white-space:nowrap}
#show-presenter{display:none}
@media(max-width:760px){main{display:block;padding:16px 14px 120px}#page-panel{position:relative;top:auto;margin-bottom:18px;max-height:45vh}#page-image{max-height:45vh;object-fit:contain}#text{padding:22px 20px}#pip{width:220px}.check{display:none}}
</style>
</head>
<body>
<header><h1 id="title"></h1><div><button id="show-presenter">Show presenter</button> <button id="theme">Night</button></div></header>
<main><aside id="page-panel"><div id="page-label">Document</div><img id="page-image" alt="Current document page"><div id="page-empty">No page image available</div></aside><article id="text"></article></main>
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
let wi=0; for(const [page,chunks] of [...pages].sort((a,b)=>a[0]-b[0])){const section=document.createElement('section');section.className='page';section.innerHTML='<h2>Page '+(page||'')+'</h2>';for(const chunk of chunks){const p=document.createElement('p');if(chunk.words.length){for(const word of chunk.words){const span=document.createElement('span');span.className='word';span.dataset.i=wi++;span.dataset.start=word.start;span.textContent=word.word+' ';p.appendChild(span);}}else p.textContent=chunk.text;section.appendChild(p);}$('text').appendChild(section);}
const spans=[...document.querySelectorAll('.word')]; let active=-1,lastPage=-1;
function fmt(s){s=Math.max(0,Math.floor(s||0));return Math.floor(s/60)+':'+String(s%60).padStart(2,'0')}
function showPage(page){if(page===lastPage)return;lastPage=page;const file=data.pages&&data.pages.files[String(page)];$('page-label').textContent=page?'Page '+page:'Document';$('page-image').style.display=file?'block':'none';$('page-empty').style.display=file?'none':'block';if(file)$('page-image').src=data.pages.dir+'/'+file;}
function find(t){let lo=0,hi=words.length-1,best=-1;while(lo<=hi){const mid=(lo+hi)>>1;if(words[mid].start<=t){best=mid;lo=mid+1}else hi=mid-1}return best>=0&&t<words[best].end?best:best;}
function update(){const t=media.currentTime||0,idx=find(t);$('now').textContent=fmt(t);$('seek').value=String(t);if(idx!==active){if(active>=0)spans[active]?.classList.remove('active');active=idx;if(active>=0){const el=spans[active];el?.classList.add('active');showPage(words[active].page);if($('scroll').checked)el?.scrollIntoView({behavior:'smooth',block:'center'});}}}
media.addEventListener('timeupdate',update);media.addEventListener('play',()=>{$('play').innerHTML='&#10074;&#10074;'});media.addEventListener('pause',()=>{$('play').innerHTML='&#9654;'});media.addEventListener('loadedmetadata',()=>{$('seek').max=String(media.duration||data.duration);$('total').textContent=fmt(media.duration||data.duration)});
$('play').onclick=()=>media.paused?media.play():media.pause();$('seek').oninput=e=>{media.currentTime=Number(e.target.value);update()};$('rate').onchange=e=>media.playbackRate=parseFloat(e.target.value);spans.forEach(s=>s.onclick=()=>{media.currentTime=Number(s.dataset.start);update()});
const saved=(()=>{try{return localStorage.getItem('reader-theme')}catch{return null}})();if(saved==='night')document.documentElement.classList.add('night');function themeLabel(){$('theme').textContent=document.documentElement.classList.contains('night')?'Day':'Night'}themeLabel();$('theme').onclick=()=>{document.documentElement.classList.toggle('night');themeLabel();try{localStorage.setItem('reader-theme',document.documentElement.classList.contains('night')?'night':'day')}catch{}};
$('hide-presenter').onclick=()=>{$('pip').classList.add('hidden');$('show-presenter').style.display='inline-block'};$('show-presenter').onclick=()=>{$('pip').classList.remove('hidden');$('show-presenter').style.display='none'};
let drag=null;$('pipbar').onpointerdown=e=>{if(e.target.tagName==='BUTTON')return;const r=$('pip').getBoundingClientRect();drag={dx:e.clientX-r.left,dy:e.clientY-r.top};$('pipbar').setPointerCapture(e.pointerId)};$('pipbar').onpointermove=e=>{if(!drag)return;$('pip').style.left=Math.max(0,Math.min(innerWidth-$('pip').offsetWidth,e.clientX-drag.dx))+'px';$('pip').style.top=Math.max(0,Math.min(innerHeight-$('pip').offsetHeight-70,e.clientY-drag.dy))+'px'};$('pipbar').onpointerup=()=>drag=null;
showPage(([...pages.keys()].sort((a,b)=>a-b)[0])||0);
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
