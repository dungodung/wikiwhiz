/* Browser side of Web Push: feature detection, permission, and turning a
 * PushSubscription into the shape the API wants.
 *
 * Every function here is defensive about support, because push is the least
 * uniformly implemented thing the app touches: Firefox and Chrome are fine,
 * iOS Safari only exposes it once the site has been added to the home screen
 * (and reports no PushManager until then), and any browser can have
 * notifications blocked at the OS level. The UI uses isPushSupported() to
 * decide whether to offer the feature at all rather than letting a user turn
 * on something that silently can't work.
 */

const SW_URL = '/sw.js'

export function isPushSupported() {
  return (
    typeof window !== 'undefined' &&
    'serviceWorker' in navigator &&
    'PushManager' in window &&
    'Notification' in window
  )
}

export function notificationPermission() {
  if (!('Notification' in window)) return 'unsupported'
  return Notification.permission // 'default' | 'granted' | 'denied'
}

// The applicationServerKey has to be a Uint8Array of the raw VAPID public
// key; the server sends it as unpadded base64url, which is what the Web Push
// ecosystem uses everywhere else too.
function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')
  const raw = window.atob(base64)
  const output = new Uint8Array(raw.length)
  for (let i = 0; i < raw.length; i += 1) output[i] = raw.charCodeAt(i)
  return output
}

export async function registerServiceWorker() {
  if (!isPushSupported()) return null
  return navigator.serviceWorker.register(SW_URL)
}

/** The current subscription for this browser, or null. Does not prompt. */
export async function getExistingSubscription() {
  if (!isPushSupported()) return null
  try {
    const registration = await navigator.serviceWorker.getRegistration(SW_URL)
    if (!registration) return null
    return await registration.pushManager.getSubscription()
  } catch {
    return null
  }
}

/** Serializes a PushSubscription into the JSON the /api/push endpoints take. */
export function serializeSubscription(subscription) {
  if (!subscription) return null
  // toJSON() gives { endpoint, keys: { p256dh, auth } } in every browser that
  // supports push -- the manual key extraction dance isn't needed any more.
  const json = subscription.toJSON()
  return { endpoint: json.endpoint, keys: json.keys }
}

/**
 * Prompt if needed, then subscribe this browser. Throws an Error with a
 * `code` the UI can branch on rather than a raw DOMException, since the
 * failure modes need different messages ("you blocked this in browser
 * settings" vs "your browser can't do this at all").
 */
export async function subscribe(vapidPublicKey) {
  if (!isPushSupported()) {
    const err = new Error('Push notifications are not supported in this browser.')
    err.code = 'unsupported'
    throw err
  }
  if (!vapidPublicKey) {
    const err = new Error('Push notifications are not configured on the server.')
    err.code = 'not_configured'
    throw err
  }

  const permission = await Notification.requestPermission()
  if (permission !== 'granted') {
    const err = new Error(
      permission === 'denied'
        ? 'Notifications are blocked for this site. Re-enable them in your browser settings, then try again.'
        : 'Notification permission was dismissed.'
    )
    err.code = permission === 'denied' ? 'denied' : 'dismissed'
    throw err
  }

  const registration = await navigator.serviceWorker.register(SW_URL)
  // Without this, subscribing immediately after a first-ever registration can
  // reject: the worker isn't active yet and pushManager has nothing to attach
  // to.
  await navigator.serviceWorker.ready

  const existing = await registration.pushManager.getSubscription()
  if (existing) return existing

  return registration.pushManager.subscribe({
    // Required to be true by every current browser: a push that never shows
    // a notification isn't allowed for web apps.
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(vapidPublicKey),
  })
}

/**
 * Tear down this browser's subscription. Returns the endpoint that was
 * removed (or null), so the caller can tell the server which device to
 * forget. Unsubscribing locally even if the server call later fails is the
 * right order: the user asked for it to stop, and a stale server row will be
 * pruned on its next failed send anyway.
 */
export async function unsubscribe() {
  const subscription = await getExistingSubscription()
  if (!subscription) return null
  const { endpoint } = subscription
  try {
    await subscription.unsubscribe()
  } catch {
    // Already gone, or the push service rejected it -- either way the local
    // state is what we wanted.
  }
  return endpoint
}
