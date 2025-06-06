class Sector:
    def __init__(self, sector_name: str, historical_powers: list[float]):
        self.sector_name = sector_name
        self.historical_power = historical_powers

        # consumption_price_full_power,consumption_price_no_power,production_price_no_power,production_price_full_power :
        self._price_model = tuple()
        self.is_controllable = False

        self.powers_out = list()
        self.availabilities = list()

    def build_price_model(self, historical_prices: list[float]):
        # Potentiellement groupe d'années en param
        # Error function + Optimisation
        # Load factor : self.historical_power / self.availabilities (check si self.availabilities non vide)
        # self._price_model = (Cons_max, Cons_min, Prod_min, Prod_max)
        pass

    def build_availabilities(self, availabilities: list[float]):
        # Si liste vide : availabilities = power rating pour chaque heure
        # Sinon : nucléaire availabilities = param availabilities
        # self.availabilities = modelled_availabilities
        pass

    @property
    def price_model(self):
        return self._price_model
