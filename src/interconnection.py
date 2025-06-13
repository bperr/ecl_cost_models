class Interconnection:
    def __init__(self, country_from: str, country_to: str, power_rating: float):
        self.country_from = country_from
        self.country_to = country_to
        self.power_rating = power_rating
        self.powers_in = dict()
        self.powers_out = dict()
