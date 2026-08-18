from ..extensions import db


class PoolAlertState(db.Model):
    """Single-row table tracking whether a low-content-pool alert is currently
    'open', so scripts/check_pool_level.py emails once per dip below the
    threshold rather than every day it stays low.
    """

    __tablename__ = "pool_alert_state"

    id = db.Column(db.SmallInteger, primary_key=True, default=1)
    low_pool_alert_active = db.Column(db.Boolean, nullable=False, default=False)
    last_remaining_count = db.Column(db.Integer, nullable=True)
    last_checked_at = db.Column(db.DateTime, nullable=True)
    last_alert_sent_at = db.Column(db.DateTime, nullable=True)
