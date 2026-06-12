// AJ Dril — Service Worker
// Verze cache — změň číslo když aktualizuješ aplikaci
const CACHE_NAME = 'aj-dril-v24';

const ASSETS = [
  './',
  './index.html',
  './style.css',
  './manifest.json',
  './icon-192.png',
  './icon-512.png'
];

// Instalace — uloží soubory do cache
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return cache.addAll(ASSETS.filter(a => !a.includes('icon'))); // ikony přeskočí pokud neexistují
    }).catch(() => {})
  );
  self.skipWaiting();
});

// Aktivace — smaže staré cache
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Fetch — cache first, pak síť
self.addEventListener('fetch', event => {
  // JSON databázi vždy ze sítě (nebo nech prohlížeči)
  if (event.request.url.includes('.json') && !event.request.url.includes('manifest')) {
    return;
  }
  // Firebase / Google requesty nikdy necachovat — přeskočit
  const url = event.request.url;
  if (url.includes('firestore.googleapis.com') ||
      url.includes('firebase') ||
      url.includes('googleapis.com') ||
      url.includes('gstatic.com') ||
      url.includes('accounts.google.com')) {
    return;
  }

  event.respondWith(
    caches.match(event.request).then(cached => {
      return cached || fetch(event.request).then(response => {
        // Ulož nové soubory do cache
        if (response.ok) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
        }
        return response;
      }).catch(() => cached);
    })
  );
});
