import { useCallback, useEffect, useState } from 'react'
import { api } from '../../api/client'
import {
  getExistingSubscription,
  isPushSupported,
  notificationPermission,
  serializeSubscription,
  subscribe as subscribePush,
  unsubscribe as unsubscribePush,
} from '../../lib/push'

// The server sends UTC instants, never formatted strings -- it has no idea
// what zone the player is in. Everything the user reads here is rendered
// from those instants by the browser, so "the puzzle changes at 02:00" is
// always their 02:00.
function formatLocalTime(isoString) {
  if (!isoString) return ''
  return new Date(isoString).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

// Whether the send lands on a different calendar day than "now" matters for
// comprehension: with a 1-hour lead time in a UTC+3 zone the reminder is at
// 03:00 *tomorrow*, and showing a bare "03:00" would read as this morning.
function formatLocalDayHint(isoString) {
  if (!isoString) return ''
  const target = new Date(isoString)
  const today = new Date()
  const sameDay = target.toDateString() === today.toDateString()
  if (sameDay) return 'today'
  const tomorrow = new Date(today)
  tomorrow.setDate(tomorrow.getDate() + 1)
  return target.toDateString() === tomorrow.toDateString() ? 'tomorrow' : ''
}

export default function NotificationSettings({ onClose }) {
  const [settings, setSettings] = useState(null)
  const [endpoint, setEndpoint] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)

  const supported = isPushSupported()
  const permission = supported ? notificationPermission() : 'unsupported'

  const load = useCallback(async () => {
    try {
      const existing = await getExistingSubscription()
      const currentEndpoint = existing?.endpoint || null
      setEndpoint(currentEndpoint)
      setSettings(await api.push.getSettings(currentEndpoint))
    } catch (err) {
      setError(err.message)
    }
  }, [])

  useEffect(() => {
    // Genuinely an external-system sync: it reads the browser's existing
    // PushSubscription and the server's settings. The lint rule can't see
    // that every setState inside load() happens after an await, not
    // synchronously during the effect, so it flags a cascading render that
    // can't actually occur here.
    // eslint-disable-next-line react/set-state-in-effect
    load()
  }, [load])

  // Escape-to-close, matching how the rest of the app's overlays behave.
  useEffect(() => {
    const onKeyDown = (e) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [onClose])

  const patch = async (body) => {
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      setSettings(await api.push.updateSettings({ ...body, endpoint }))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const handleEnable = async () => {
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      const subscription = await subscribePush(settings?.vapid_public_key)
      const serialized = serializeSubscription(subscription)
      setEndpoint(serialized.endpoint)
      setSettings(
        await api.push.subscribe({
          ...serialized,
          hours_before_reset: settings?.hours_before_reset,
          trigger: settings?.trigger,
        })
      )
      setNotice('Reminders are on for this device.')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  // Turning it off tears down the browser subscription *and* the server row,
  // so a user who changes their mind isn't left with a dormant registration
  // that starts firing again if the flag is ever flipped back on elsewhere.
  const handleDisable = async () => {
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      const removed = await unsubscribePush()
      setSettings(await api.push.unsubscribe(removed || endpoint))
      setEndpoint(null)
      setNotice('Reminders are off. You can turn them back on any time.')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const handleTest = async () => {
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      await api.push.sendTest()
      setNotice('Test notification sent — it should appear in a moment.')
    } catch (err) {
      setError(
        err.data?.error === 'delivery_failed'
          ? "The push service wouldn't accept it. Try turning reminders off and on again."
          : err.message
      )
    } finally {
      setBusy(false)
    }
  }

  const enabledHere = Boolean(settings?.subscribed_on_this_device)
  const otherDevices = (settings?.device_count || 0) - (enabledHere ? 1 : 0)

  return (
    <div
      className="notif-modal__backdrop"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div className="notif-modal" role="dialog" aria-modal="true" aria-label="Daily reminder settings">
        <div className="notif-modal__header">
          <h2 className="notif-modal__title">Daily reminder</h2>
          <button type="button" className="notif-modal__close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>

        {!supported && (
          <p className="notif-modal__unsupported">
            This browser can&apos;t do push notifications. On iPhone or iPad, add WikiWhiz to your
            Home Screen first — Safari only allows notifications for installed sites.
          </p>
        )}

        {supported && settings && !settings.supported && (
          <p className="notif-modal__unsupported">
            Push notifications aren&apos;t configured on this server yet.
          </p>
        )}

        {supported && settings?.supported && (
          <>
            <p className="notif-modal__reset">
              The puzzle changes at <strong>{formatLocalTime(settings.next_reset_utc)}</strong> your
              time, every day.
            </p>

            <label className="notif-modal__field">
              <span className="notif-modal__label">Remind me this long before it changes</span>
              <span className="notif-modal__hours-row">
                <input
                  className="notif-modal__hours"
                  type="number"
                  min={settings.min_hours}
                  max={settings.max_hours}
                  value={settings.hours_before_reset}
                  disabled={busy}
                  onChange={(e) => {
                    const hours = Number(e.target.value)
                    // Reflect the typed value straight away so the field
                    // stays editable, but only persist a value the server
                    // will actually accept.
                    setSettings((s) => ({ ...s, hours_before_reset: e.target.value }))
                    if (hours >= settings.min_hours && hours <= settings.max_hours) {
                      patch({ hours_before_reset: hours })
                    }
                  }}
                />
                <span className="notif-modal__hours-unit">
                  hour{Number(settings.hours_before_reset) === 1 ? '' : 's'}
                </span>
              </span>
            </label>

            <p className="notif-modal__sendtime">
              You&apos;ll be nudged at{' '}
              <strong>{formatLocalTime(settings.next_send_utc)}</strong>
              {formatLocalDayHint(settings.next_send_utc)
                ? ` ${formatLocalDayHint(settings.next_send_utc)}`
                : ''}
              .
            </p>

            <fieldset className="notif-modal__field notif-modal__triggers">
              <legend className="notif-modal__label">Only remind me if</legend>
              <label className="notif-modal__radio">
                <input
                  type="radio"
                  name="notif-trigger"
                  checked={settings.trigger === 'incomplete'}
                  disabled={busy}
                  onChange={() => patch({ trigger: 'incomplete' })}
                />
                <span>
                  <strong>I haven&apos;t finished</strong> — includes puzzles I started but
                  didn&apos;t solve.
                </span>
              </label>
              <label className="notif-modal__radio">
                <input
                  type="radio"
                  name="notif-trigger"
                  checked={settings.trigger === 'untouched'}
                  disabled={busy}
                  onChange={() => patch({ trigger: 'untouched' })}
                />
                <span>
                  <strong>I haven&apos;t started</strong> — stay quiet once I&apos;ve made a guess.
                </span>
              </label>
            </fieldset>

            {otherDevices > 0 && (
              <p className="notif-modal__devices">
                Also on {otherDevices} other device{otherDevices === 1 ? '' : 's'}.
              </p>
            )}

            <div className="notif-modal__actions">
              {enabledHere ? (
                <>
                  <button
                    type="button"
                    className="notif-modal__button notif-modal__button--off"
                    onClick={handleDisable}
                    disabled={busy}
                  >
                    Turn off reminders
                  </button>
                  <button
                    type="button"
                    className="notif-modal__button"
                    onClick={handleTest}
                    disabled={busy}
                  >
                    Send test
                  </button>
                </>
              ) : (
                <button
                  type="button"
                  className="notif-modal__button notif-modal__button--primary"
                  onClick={handleEnable}
                  disabled={busy || permission === 'denied'}
                >
                  Turn on reminders
                </button>
              )}
            </div>

            {permission === 'denied' && !enabledHere && (
              <p className="notif-modal__error">
                Notifications are blocked for this site in your browser settings. Allow them there,
                then reload this page.
              </p>
            )}
          </>
        )}

        {error && <p className="notif-modal__error">{error}</p>}
        {notice && <p className="notif-modal__notice">{notice}</p>}
      </div>
    </div>
  )
}
