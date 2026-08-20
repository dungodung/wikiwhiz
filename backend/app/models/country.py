from ..extensions import db


class Country(db.Model):
    """Codebook of ISO 3166-1 alpha-2 country codes, seeded once by migration
    e5f8b3a9d1c7 (see backend/migrations). Includes a synthetic 'XX' =
    'Unknown' row for page views whose country couldn't be resolved (see
    lib/page_views.py), so PageViewStat.country_code never needs to be
    nullable.
    """

    __tablename__ = "countries"

    code = db.Column(db.String(2), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
