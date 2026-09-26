/* WikiWhiz service worker -- daily reminder notifications only.
 *
 * Deliberately does NOT cache anything or intercept fetches. The app is
 * served by Flask's catch-all (backend/app/__init__.py) with hashed asset
 * filenames, so an offline cache here would buy nothing and risk serving a
 * stale index.html that points at assets a redeploy has already removed.
 * This worker exists purely so the browser has somewhere to deliver push
 * events -- Web Push requires a service worker, there's no page-only API.
 *
 * Served from /sw.js (via frontend/public/) rather than a subdirectory
 * because a worker's scope can't be broader than its own path, and this one
 * needs to cover the whole origin.
 */

self.addEventListener('install', () => {
  // Take over immediately rather than waiting for every existing tab to
  // close -- a user who just switched notifications on expects the next
  // test push to work in the tab they're already looking at.
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim())
})

self.addEventListener('push', (event) => {
  // A push with no/undecodable payload still deserves a notification: most
  // browsers show a generic "site updated in the background" message if the
  // handler doesn't call showNotification, which looks broken.
  let payload = {}
  try {
    payload = event.data ? event.data.json() : {}
  } catch {
    payload = {}
  }

  const title = payload.title || 'WikiWhiz'
  const options = {
    body: payload.body || "Today's puzzle is still waiting.",
    icon: '/favicon.svg',
    badge: '/favicon.svg',
    // A stable tag collapses repeats instead of stacking them, so someone
    // whose device was offline doesn't wake to a column of identical nudges.
    tag: payload.tag || 'wikiwhiz',
    renotify: false,
    data: { url: payload.url || '/' },
  }

  event.waitUntil(self.registration.showNotification(title, options))
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const targetUrl = new URL(event.notification.data?.url || '/', self.location.origin).href

  // Focus an existing tab on this origin if there is one, rather than piling
  // up duplicate tabs each time a reminder is tapped.
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if (client.url.startsWith(self.location.origin) && 'focus' in client) {
          client.navigate(targetUrl)
          return client.focus()
        }
      }
      return self.clients.openWindow(targetUrl)
    })
  )
})
