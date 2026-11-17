// 離線快取：第一次開啟後，沒有網路也能使用
const CACHE='dah-v37';
const CORE=['./','./index.html','./manifest.webmanifest','./icon-192.png','./icon-512.png','./data/taipower.json'];
self.addEventListener('install',e=>{e.waitUntil(caches.open(CACHE).then(c=>Promise.all(CORE.map(u=>c.add(u).catch(()=>{})))).then(()=>self.skipWaiting()))});
self.addEventListener('activate',e=>{e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim()))});
self.addEventListener('fetch',e=>{
  if(e.request.method!=='GET')return;
  const url=new URL(e.request.url);
  // 台電資料：先上網抓最新的，連不上才用快取
  if(url.origin===location.origin&&url.pathname.indexOf('/data/')>=0){
    e.respondWith(fetch(e.request).then(res=>{if(res&&res.ok){const copy=res.clone();caches.open(CACHE).then(c=>c.put(url.pathname,copy))}return res}).catch(()=>caches.match(url.pathname)));
    return;
  }
  e.respondWith(caches.match(e.request).then(hit=>{
    const net=fetch(e.request).then(res=>{if(res&&(res.ok||res.type==='opaque')){const copy=res.clone();caches.open(CACHE).then(c=>c.put(e.request,copy))}return res}).catch(()=>hit);
    return hit||net;
  }));
});
