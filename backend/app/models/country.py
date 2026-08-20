from ..extensions import db


class Country(db.Model):
    """Codebook of ISO 3166-1 alpha-2 country codes, seeded once by migration
    d... (see backend/migrations). Includes a synthetic 'XX' = 'Unknown' row
    for page views whose IP couldn't be geolocated, so PageViewStat.country_code
    never needs to be nullable.
    """

    __tablename__ = "countries"

    code = db.Column(db.String(2), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
