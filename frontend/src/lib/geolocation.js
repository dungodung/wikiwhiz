// Resolves the visitor's own country client-side and reports it to
// /api/info/page-view -- see backend/app/lib/page_views.py's module
// docstring for why this happens in the browser rather than server-side
// (Toolforge's edge network strips the real visitor IP before it ever
// reaches the backend, confirmed live; the browser is the only place that
// actually has it). Only the resolved country code is ever sent to our own
// backend -- the IP itself never leaves the browser except to geojs.io.
//
// geojs.io is a free, keyless, CORS-enabled geolocation service. Best
// effort throughout: an ad-blocker, an offline visitor, or geojs.io being
// down should never surface an error to the player -- this is a page-view
// counter, not something worth a console error over.

const GEOLOCATION_URL = 'https://get.geojs.io/v1/ip/country.json'

export async function reportPageView() {
  try {
    const geoResp = await fetch(GEOLOCATION_URL)
    if (!geoResp.ok) return
    const { country } = await geoResp.json()
    if (!country) return

    await fetch('/api/info/page-view', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ country_code: country }),
    })
  } catch {
    // Best effort -- see module comment above.
  }
}
