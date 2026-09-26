"""Web Push delivery: sign with VAPID, post to the push service, and prune
subscriptions the service says are permanently gone.

Deliberately the only module that imports pywebpush, so the rest of the app
talks in terms of "send this to this user" and never handles VAPID material.

Config is passed in as a mapping rather than read off `current_app`, matching
lib/notifications.py -- scripts/send_push_reminders.py runs as a Toolforge
job with no Flask app context, and requiring one just to send a notification
would mean standing up the whole app inside the cron job.

With no keys configured, is_configured() is False and every send is a no-op
rather than an error: a fresh checkout has no keys, and push being
unavailable shouldn't break the app or the test suite.

Pruning matters more than it looks. Push endpoints die constantly (cleared
site data, uninstalled browsers, expired registrations) and a dead one
returns 404/410 forever. Without deleting on those codes, every reminder run
would retry a growing pile of corpses, and the per-user "do you have push set
up" answer would drift from reality.
"""

import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Push services use these to say "this endpoint is permanently gone" --
# distinct from a transient 5xx, which is worth retrying on the next run.
_GONE_STATUS_CODES = (404, 410)


def is_configured(config) -> bool:
    return bool(config.get("VAPID_PRIVATE_KEY") and config.get("VAPID_PUBLIC_KEY"))


def public_key(config) -> str:
    return config.get("VAPID_PUBLIC_KEY", "")


def send_to_subscription(session, subscription, payload: dict, config) -> bool:
    """Deliver one payload to one endpoint. Returns True if the push service
    accepted it. Deletes the subscription row (without committing -- the
    caller owns the transaction) when the service reports it permanently
    gone, and leaves it alone on any other failure so a transient outage
    doesn't discard working subscriptions.
    """
    if not is_configured(config):
        logger.info("push not configured; skipping send to subscription %s", subscription.id)
        return False

    # Imported lazily so this module stays importable (and the app boots)
    # even without pywebpush installed -- push is optional.
    from pywebpush import WebPushException, webpush

    try:
        webpush(
            subscription_info=subscription.to_webpush_info(),
            data=json.dumps(payload),
            vapid_private_key=config["VAPID_PRIVATE_KEY"],
            vapid_claims={"sub": config.get("VAPID_SUBJECT", "mailto:wikiwhiz@toolforge.org")},
            timeout=10,
        )
        return True
    except WebPushException as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status in _GONE_STATUS_CODES:
            logger.info("pruning dead push subscription %s (HTTP %s)", subscription.id, status)
            session.delete(subscription)
        else:
            logger.warning(
                "push send failed for subscription %s (HTTP %s): %s",
                subscription.id,
                status,
                exc,
            )
        return False
    except Exception:
        logger.exception("unexpected error sending push to subscription %s", subscription.id)
        return False


def send_to_user(session, user, payload: dict, config) -> int:
    """Fan a payload out to every device the user has registered. Returns the
    number of endpoints that accepted it -- 0 means nothing was delivered
    (all dead, or push unconfigured), which the reminder job uses to decide
    whether the attempt counts as notified.
    """
    delivered = 0
    for subscription in list(user.push_subscriptions):
        if send_to_subscription(session, subscription, payload, config):
            subscription.last_sent_at = datetime.now(timezone.utc)
            delivered += 1
    return delivered
