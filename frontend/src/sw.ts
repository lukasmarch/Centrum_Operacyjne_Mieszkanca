/// <reference lib="webworker" />
import { clientsClaim } from 'workbox-core';
import { cleanupOutdatedCaches, precacheAndRoute } from 'workbox-precaching';

declare const self: ServiceWorkerGlobalScope;

// Precache assets injected by vite-plugin-pwa
precacheAndRoute(self.__WB_MANIFEST);
cleanupOutdatedCaches();

// registerType: 'autoUpdate' w vite.config nie wystarcza przy strategies: 'injectManifest' —
// bez tych dwóch wywołań nowy SW czeka, aż użytkownik zamknie wszystkie karty serwisu,
// więc wdrożone poprawki nie docierają do osób, które już odwiedziły stronę.
self.skipWaiting();
clientsClaim();

// ==================== Push Events ====================

self.addEventListener('push', (event: PushEvent) => {
  if (!event.data) return;

  let data: {
    title: string;
    body: string;
    url?: string;
    icon?: string;
  };

  try {
    data = event.data.json();
  } catch {
    data = { title: 'Centrum Operacyjne', body: event.data.text() };
  }

  const options: NotificationOptions = {
    body: data.body,
    icon: data.icon || '/icon-192.png',
    badge: '/icon-72.png',
    data: { url: data.url || '/' },
  };

  event.waitUntil(
    self.registration.showNotification(data.title, options)
  );
});

// ==================== Notification Click ====================

self.addEventListener('notificationclick', (event: NotificationEvent) => {
  event.notification.close();

  const url = event.notification.data?.url || '/';

  event.waitUntil(
    self.clients
      .matchAll({ type: 'window', includeUncontrolled: true })
      .then((clientList) => {
        // Jeśli aplikacja jest już otwarta, skup okno i przejdź do URL
        for (const client of clientList) {
          if ('focus' in client) {
            client.focus();
            if ('navigate' in client) {
              (client as WindowClient).navigate(url);
            }
            return;
          }
        }
        // Otwórz nowe okno
        return self.clients.openWindow(url);
      })
  );
});
