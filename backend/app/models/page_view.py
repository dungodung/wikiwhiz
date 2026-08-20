from ..extensions import db


class PageViewStat(db.Model):
    """Aggregated daily page-view counts by country -- deliberately not a
    per-visit event log: no IP address is ever stored or even seen by this
    backend (country resolution happens client-side, see lib/page_views.py's
    module docstring for why), and no per-visit timestamp either, just a
    running total per (country, date). Incremented via POST
    /api/info/page-view once per real frontend page load, for non-bot
    requests.
    """

    __tablename__ = "page_view_stats"

    id = db.Column(db.Integer, primary_key=True)
    country_code = db.Column(db.String(2), db.ForeignKey("countries.code"), nullable=False)
    view_date = db.Column(db.Date, nullable=False)
    view_count = db.Column(db.Integer, nullable=False, default=0)

    __table_args__ = (
        db.UniqueConstraint("country_code", "view_date", name="uq_page_view_country_date"),
        db.Index("ix_page_view_stats_date", "view_date"),
    )
