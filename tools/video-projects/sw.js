/* 影片製作進度 — Service Worker（Web Push 收信 + 點擊開啟）
   註：不做離線快取，只負責推播；避免快取住 HTML 造成看到舊版。 */
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));

self.addEventListener('push', (event) => {
  let d = {};
  try { d = event.data ? event.data.json() : {}; } catch (_) { d = { title: '影片製作提醒', body: event.data ? event.data.text() : '' }; }
  const title = d.title || '🎬 影片製作提醒';
  const options = {
    body: d.body || '',
    icon: d.icon || 'icons/icon-192.png',
    badge: 'icons/icon-192.png',
    tag: d.tag || 'vproj-reminder',
    renotify: true,
    data: { url: d.url || './' },
    vibrate: [80, 40, 80]
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || './';
  event.waitUntil((async () => {
    const all = await clients.matchAll({ type: 'window', includeUncontrolled: true });
    for (const c of all) { if ('focus' in c) { c.navigate(url).catch(() => {}); return c.focus(); } }
    if (clients.openWindow) return clients.openWindow(url);
  })());
});
