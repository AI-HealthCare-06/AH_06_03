// 웹 푸시 수신 전용 서비스 워커. 화면 캐시는 하지 않는다.
// 서버가 보내는 JSON: { title, body, url }  (url은 알림을 눌렀을 때 열 화면. 예: post.html?id=…#c-…)
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));

self.addEventListener('push', (e) => {
  let d = {};
  try { d = e.data ? e.data.json() : {}; } catch (err) { d = { body: e.data ? e.data.text() : '' }; }
  e.waitUntil(self.registration.showNotification(d.title || 'PAEON', {
    body: d.body || '',
    icon: 'assets/img/icon-192.png',
    badge: 'assets/img/icon-192.png',
    data: { url: d.url || 'dashboard.html' },
  }));
});

self.addEventListener('notificationclick', (e) => {
  e.notification.close();
  const url = new URL((e.notification.data && e.notification.data.url) || 'dashboard.html', self.location.href).href;
  e.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((list) => {
    for (const c of list) { if ('focus' in c) { c.navigate(url); return c.focus(); } }   // 이미 열려 있으면 그 창을 그 화면으로
    return self.clients.openWindow(url);
  }));
});
