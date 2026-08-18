"""Maintainer email alerts.

Sends through Toolforge's documented outgoing relay (mail.tools.wmcloud.org
in production -- see https://wikitech.wikimedia.org/wiki/Help:Toolforge/Email:
Kubernetes tool containers have no local mailer and must relay through this
host, using a tool-controlled From address). This is a single low-volume
transactional email, not bulk mail.
"""

import logging
import smtplib
from email.message import EmailMessage

logger = logging.getLogger(__name__)


def send_low_pool_alert(remaining_count: int, threshold: int, config: dict) -> None:
    maintainer_email = config.get("MAINTAINER_EMAIL")
    if not maintainer_email:
        logger.warning(
            "MAINTAINER_EMAIL not configured; skipping low-pool alert "
            "(remaining=%s, threshold=%s)",
            remaining_count,
            threshold,
        )
        return

    subject = f"WikiWhiz: only {remaining_count} day(s) of content left"
    body = (
        f"The WikiWhiz daily-challenge pool has {remaining_count} scheduled day(s) "
        f"remaining (threshold: {threshold}).\n\n"
        "Invoke the wikiwhiz-content-author Claude Code skill soon to add more "
        "articles and clue sets before the pool runs dry."
    )

    if config.get("SMTP_DEBUG_LOG_ONLY"):
        logger.info("[low-pool alert, log-only] to=%s subject=%r\n%s", maintainer_email, subject, body)
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = config.get("MAIL_FROM", "wikiwhiz@toolforge.org")
    msg["To"] = maintainer_email
    msg.set_content(body)

    with smtplib.SMTP(config.get("SMTP_HOST", "localhost"), config.get("SMTP_PORT", 25), timeout=10) as smtp:
        smtp.send_message(msg)
