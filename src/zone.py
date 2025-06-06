
from src.sector import Sector


class Zone:
    def __init__(self, zone_name, historical_prices):
        self.name = zone_name
        self.historical_prices = historical_prices
        self.sectors: list[Sector] = list()
        self.power_demand = list()
        self.prices_out = list()

    def add_sector(self, sector_name: str, historical_powers: list[float]):
        sector = Sector(sector_name,historical_powers)
        self.sectors.append(sector)

    def build_price_model(self):
        for sector in self.sectors:
            sector.build_price_model(historical_prices=self.historical_prices)

    def compute_demand(self, net_imports: list[float]):
        # Opf
        pass

    def add_storage(self, sector_name: str, historical_powers: list[float]):
        # Idem que add sector mais séparer conso et prod
        # Si besoin des Timestamp utiliser pd.Series plutôt que list[float]
        # crée objet storage qui a deux objets sectors (à rajouter au self)
        pass
