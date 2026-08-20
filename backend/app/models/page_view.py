from ..extensions import db


class PageViewStat(db.Model):
    """Aggregated daily page-view counts by country -- deliberately not a
    per-visit event log: no IP is ever stored (see lib/geolocation.py), and
    no per-visit timestamp either, just a running total per (country, date).
    Incremented by lib/page_views.py whenever the frontend's index.html is
    served to a non-bot request.
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
