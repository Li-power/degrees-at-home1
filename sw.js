// 離線快取：第一次開啟後，沒有網路也能使用
// 網頁本身（HTML）先上網拿最新版，連不上或太慢（4 秒）才用快取，避免看到舊版
const CACHE='dah-v52';
const CORE=['./','./index.html','./manifest.webmanifest','./icon-192.png','./icon-512.png','./data/taipower.json'];
self.addEventListener('install',e=>{e.waitUntil(caches.open(CACHE).then(c=>Promise.all(CORE.map(u=>c.add(new Request(u,{cache:'reload'})).catch(()=>{})))).then(()=>self.skipWaiting()))});
self.addEventListener('activate',e=>{e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim()))});
function put(req,res){if(res&&(res.ok||res.type==='opaque')){const copy=res.clone();caches.open(CACHE).then(c=>c.put(req,copy)).catch(()=>{})}return res}
self.addEventListener('fetch',e=>{
  if(e.request.method!=='GET')return;
  const url=new URL(e.request.url);
  const isPage=e.request.mode==='navigate'||(url.origin===location.origin&&/\/(index\.html)?$/.test(url.pathname));
  // 網頁：網路優先，4 秒沒回應就先用快取
  if(isPage){
    e.respondWith(new Promise(resolve=>{
      let done=false;
      const fallback=()=>caches.match(e.request,{ignoreSearch:true}).then(h=>h||caches.match('./index.html')||caches.match('./'));
      const t=setTimeout(()=>{fallback().then(h=>{if(h&&!done){done=true;resolve(h)}})},4000);
      fetch(e.request).then(res=>{put(e.request,res.clone());if(!done){done=true;clearTimeout(t);resolve(res)}})
        .catch(()=>{clearTimeout(t);fallback().then(h=>{if(!done){done=true;resolve(h||Response.error())}})});
    }));
    return;
  }
  // 台電資料：先上網抓最新的，連不上才用快取
  if(url.origin===location.origin&&url.pathname.indexOf('/data/')>=0){
    e.respondWith(fetch(e.request).then(res=>{if(res&&res.ok){const copy=res.clone();caches.open(CACHE).then(c=>c.put(url.pathname,copy))}return res}).catch(()=>caches.match(url.pathname)));
    return;
  }
  // 其他（圖示等）：先用快取，背景更新
  e.respondWith(caches.match(e.request).then(hit=>{
    const net=fetch(e.request).then(res=>put(e.request,res)).catch(()=>hit);
    return hit||net;
  }));
});
