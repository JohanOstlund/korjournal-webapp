// Handskriven service worker.
//
// Sidorna är inloggningsskyddade och resorna ändras hela tiden, så ingenting
// som kommer från servern cachas som svar på en navigering — annars kan appen
// visa någon annans senaste vy, eller ett skal som tror att du är inloggad när
// sessionen gått ut. Cachen innehåller bara sådant som är oföränderligt:
// Next.js hashade byggartefakter, ikonerna och en offline-sida.

const CACHE = 'korjournal-v1';
const OFFLINE_URL = '/offline.html';

const PRECACHE = [
  OFFLINE_URL,
  '/manifest.webmanifest',
  '/icons/icon-192.png',
  '/icons/icon-512.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE)
      .then((cache) => cache.addAll(PRECACHE))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith('/api/')) return;   // aldrig cacha API-svar

  // Navigeringar går alltid till nätet, så att utgången session ger
  // inloggningssidan i stället för ett cachat skal. Offline-sidan är det enda
  // vi svarar med när nätet inte finns.
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request).catch(() => caches.match(OFFLINE_URL).then((hit) => hit || new Response(
        'Ingen anslutning.',
        { status: 503, headers: { 'Content-Type': 'text/plain; charset=utf-8' } },
      ))),
    );
    return;
  }

  // Hashade byggartefakter och ikoner: cache först — innehållet kan inte
  // ändras utan att URL:en gör det.
  const immutable = url.pathname.startsWith('/_next/static/')
    || url.pathname.startsWith('/icons/')
    || url.pathname === '/favicon.png'
    || url.pathname === '/apple-touch-icon.png';

  if (!immutable) return;

  event.respondWith(
    caches.match(request).then((hit) => hit || fetch(request).then((res) => {
      if (res.ok) {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(request, copy));
      }
      return res;
    })),
  );
});
