const state = { source:"both", lang:"en", history:[], streaming:false, ctrl:null };

document.addEventListener("DOMContentLoaded", ()=>{
  applyI18n(); fetchMeta(); wire();
});
function sourcesOnlyText(){
  return "I couldn't find this in the collected data. Try asking about DarGlobal projects (Trump Tower Jeddah, AIDA, Aston Martin) or Wasalt listings by city. Figures are indicative and subject to change.";
}
async function fetchMeta(){
  try{
    const m = await (await fetch("/api/meta")).json();
    document.getElementById("st-pages").textContent = m.pages_indexed ?? "—";
    document.getElementById("st-wa").textContent = m.wasalt_listings ?? "—";
    document.getElementById("st-date").textContent = m.data_date ?? "—";
    document.getElementById("footMeta").textContent = `Model: ${m.model||"—"} · Data: ${m.data_date||"—"}`;
  }catch(e){ console.warn("meta failed", e); }
}

function wire(){
  document.querySelectorAll(".seg-btn").forEach(b=>b.addEventListener("click",()=>{
    state.source=b.dataset.src;
    document.querySelectorAll(".seg-btn").forEach(x=>{x.classList.toggle("active",x===b);x.setAttribute("aria-checked",x===b);});
  }));
  document.querySelectorAll(".lang-btn").forEach(b=>b.addEventListener("click",()=>{
    state.lang=b.dataset.lang;
    document.querySelectorAll(".lang-btn").forEach(x=>x.classList.toggle("active",x===b));
    applyI18n();
  }));
  document.getElementById("starters").addEventListener("click",e=>{
    const card=e.target.closest(".starter"); if(!card) return;
    document.getElementById("input").value=card.dataset.q; send();
  });
  const inp=document.getElementById("input");
  inp.addEventListener("input",()=>{inp.style.height="auto";inp.style.height=Math.min(inp.scrollHeight,160)+"px";});
  inp.addEventListener("keydown",e=>{ if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();send();} });
  document.getElementById("composer").addEventListener("submit",e=>{e.preventDefault();send();});
  document.getElementById("dwClose").addEventListener("click",closeDrawer);
  document.getElementById("scrim").addEventListener("click",closeDrawer);
  document.addEventListener("keydown",e=>{ if(e.key==="Escape") closeDrawer(); });
}

function esc(s){return (s||"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}
function md(s){
  return esc(s)
    .replace(/\*\*(.+?)\*\*/g,"<strong>$1</strong>")
    .replace(/\[(\d+)\]/g,'<sup><a href="#" data-cite="$1">[$1]</a></sup>')
    .replace(/((?:SAR|AED|USD|GBP)\s[\d,\.]+)/g,'<span class="num">$1</span>')
    .replace(/\n/g,"<br>");
}

function addMsg(text,role){
  document.getElementById("hero").style.display="none";
  const tr=document.getElementById("transcript"); tr.hidden=false;
  const d=document.createElement("div");
  if(role==="user"){ d.className="msg msg-user"; d.dir="auto"; d.textContent=text; }
  else{ d.className="msg msg-asst"; d.dir="auto";
    d.innerHTML=`<span class="as-label">${I18N[state.lang].assistant}</span><div class="as-text"><span class="dots"><i></i><i></i><i></i></span></div>`; }
  tr.appendChild(d); tr.scrollTop=tr.scrollHeight;
  return d;
}

async function send(){
  const inp=document.getElementById("input");
  const msg=inp.value.trim(); if(!msg||state.streaming) return;
  inp.value=""; inp.style.height="auto";
  addMsg(msg,"user");
  state.history.push({role:"user",content:msg});
  state.history=state.history.slice(-8);
  await runChat(msg);
}

async function runChat(msg){
  state.streaming=true;
  const sendBtn=document.getElementById("sendBtn");
  sendBtn.innerHTML='<svg width="16" height="16"><use href="#i-stop"/></svg>';
  sendBtn.onclick=stop;
  document.getElementById("loadbar").hidden=false;
  const host=addMsg("","assistant");
  const textEl=host.querySelector(".as-text");
  let full="", cits=[], warned=null, gotFirst=false, wakeTimer=null;

  state.ctrl=new AbortController();
  wakeTimer=setTimeout(()=>{ if(!gotFirst) showWaking(textEl); },3000);

  try{
    const res=await fetch("/api/chat",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({message:msg,source:state.source,lang:state.lang,history:state.history.slice(0,-1)}),
      signal:state.ctrl.signal});
    if(!res.ok) throw new Error("HTTP "+res.status);
    const reader=res.body.getReader(), dec=new TextDecoder();
    let buf="";
    while(true){
      const {done,value}=await reader.read(); if(done) break;
      buf+=dec.decode(value,{stream:true});
      const events=buf.split("\n\n"); buf=events.pop();
      for(const ev of events){
        if(!ev.startsWith("data: ")) continue;
        let d; try{ d=JSON.parse(ev.slice(6)); }catch(e){ continue; }
        if(d.type==="meta"){ gotFirst=true; clearTimeout(wakeTimer); hideWaking(textEl);
          if(d.cached) addBadge(host,"cached");
          if(d.model) document.getElementById("footMeta").textContent=`Model: ${d.model} · Data: ${I18N[state.lang].st_date}`;
        }
        else if(d.type==="token"){ gotFirst=true; clearTimeout(wakeTimer); hideWaking(textEl);
          full+=d.content; textEl.innerHTML=md(full)+'<span class="caret"></span>'; autoScroll(); }
        else if(d.type==="citations"){ cits=d.data||[]; renderCits(host,cits); }
        else if(d.type==="warning"){ warned=d.content; addBadge(host,"warn",d.content); }
        else if(d.type==="error"){ throw new Error(d.content||"stream error"); }
        else if(d.type==="done"){ /* handled below */ }
      }
    }
    if(!full && !cits.length) textEl.innerHTML=md(sourcesOnlyText());    else textEl.innerHTML=md(full);
    state.history.push({role:"assistant",content:full});
    document.getElementById("announce").textContent=`Answer ready, ${cits.length} sources`;
  }catch(err){
    if(err.name==="AbortError"){ textEl.innerHTML=md(full)||"<em>stopped</em>"; }
    else{ textEl.innerHTML=`<div class="notice error"><div class="n-title">${I18N[state.lang].err_title}</div>${esc(I18N[state.lang].err_txt)}<div><button class="retry" data-retry="${esc(msg)}">${I18N[state.lang].retry}</button></div></div>`; }
  }finally{
    clearTimeout(wakeTimer);
    state.streaming=false; state.ctrl=null;
    sendBtn.innerHTML='<svg width="16" height="16"><use href="#i-arrow"/></svg>';
    sendBtn.onclick=null;
    document.getElementById("loadbar").hidden=true;
    host.querySelector(".retry")?.addEventListener("click",e=>{ document.getElementById("input").value=e.target.dataset.retry; send(); });
  }
}

function stop(){ state.ctrl?.abort(); }
function autoScroll(){ const t=document.getElementById("transcript"); t.scrollTop=t.scrollHeight; }

function showWaking(el){ el.innerHTML=`<div class="notice"><div class="n-title">${I18N[state.lang].waking}</div>${I18N[state.lang].waking_txt}</div>`; }
function hideWaking(el){ if(el.querySelector(".notice")) el.innerHTML='<span class="dots"><i></i><i></i><i></i></span>'; }

function addBadge(host,kind,text){
  const row=host.querySelector(".cit-row")||makeCitRow(host);
  const b=document.createElement("span");
  b.className="badge"+(kind==="warn"?" warn":kind==="cached"?" cached":"");
  b.textContent=text||I18N[state.lang][kind==="warn"?"sources_only":kind];
  row.appendChild(b);
}
function makeCitRow(host){
  const r=document.createElement("div"); r.className="cit-row";
  r.innerHTML=`<span class="label">${I18N[state.lang].sources}</span>`;
  host.appendChild(r); return r;
}
function renderCits(host,cits){
  let row=host.querySelector(".cit-row")||makeCitRow(host);
  row.querySelectorAll(".chip").forEach(c=>c.remove());
  cits.forEach(c=>{
    const dot=c.company==="Wasalt"?"dot-wa":c.company==="computed"?"dot-silver":"dot-dar";
    const el=document.createElement("button");
    el.className="chip"; el.dataset.chunk=c.chunk_id; el.dataset.url=c.url;
    el.setAttribute("aria-label",`Source ${c.n}: ${c.title}, ${c.company}`);
    el.innerHTML=`<span class="n">[${c.n}]</span><i class="dot ${dot}"></i><span class="t">${esc((c.title||"").slice(0,28))}</span><span class="ext"><svg width="12" height="12"><use href="#i-ext"/></svg></span>`;
    el.addEventListener("click",e=>{
      if(e.target.closest(".ext")){ window.open(c.url,"_blank","noopener"); return; }
      openDrawer(c);
    });
    row.appendChild(el);
  });
}

async function openDrawer(c){
  const dw=document.getElementById("drawer"), scrim=document.getElementById("scrim");
  dw.hidden=false; scrim.hidden=false; requestAnimationFrame(()=>dw.classList.add("open"));
  const body=document.getElementById("dwBody");
  body.innerHTML=`<div class="dw-meta"><i class="dot ${c.company==="Wasalt"?"dot-wa":"dot-dar"}"></i>${esc(c.company)} · ${esc(c.page_type||"")}</div><div class="dw-title">${esc(c.title)}</div><div class="dw-date">Scraped ${esc((c.scraped_at||"").slice(0,10))}</div><div class="dw-excerpt">${esc(c.excerpt||"")}…</div><div class="dw-rows"><span><b>URL:</b> ${esc(c.url)}</span></div><a class="dw-open" href="${esc(c.url)}" target="_blank" rel="noopener noreferrer">${I18N[state.lang].open}<svg width="12" height="12"><use href="#i-ext"/></svg></a>`;
  try{ const full=await (await fetch("/api/source/"+c.chunk_id)).json();
    if(full&&full.text_display) body.querySelector(".dw-excerpt").textContent=full.text_display.slice(0,600)+"…";
  }catch(e){}
  document.getElementById("dwClose").focus();
}
function closeDrawer(){
  const dw=document.getElementById("drawer");
  dw.classList.remove("open");
  setTimeout(()=>{ dw.hidden=true; document.getElementById("scrim").hidden=true; },300);
}