import pandas as pd

from src.sector import Sector
from src.storage import Storage


class Zone:
    def __init__(self, zone_name: str, historical_prices: pd.Series):
        self.name = zone_name
        self.historical_prices = historical_prices
        self.sectors: list[Sector] = list()
        self.storages: list[Storage] = list()
        self.power_demand = list()
        self.prices_out = list()

    def add_sector(self, sector_name: str, historical_powers: pd.Series):
        sector = Sector(sector_name,historical_powers)
        self.sectors.append(sector)

    def build_price_model(self, prices_init: tuple):
        for sector in self.sectors:
            sector.build_price_model(historical_prices=self.historical_prices, prices_init=prices_init)

    def compute_demand(self, net_imports: list[float]):
        # Opf
        pass

    def add_storage(self, sector_name: str, historical_powers: pd.Series):
        storage = Storage(sector_name, historical_powers)
        self.storages.append(storage)
        self.sectors.append(storage.load)
        self.sectors.append(storage.generator)

    def save_plots(self, path):
        for sector in self.sectors:
            if sector.is_load:
                sector.plot_result(zone_name=self.name, historical_prices=self.historical_prices,
                                   path=path / f"{self.name}-{sector.name}-load.png" )
            else:
                sector.plot_result(zone_name=self.name, historical_prices=self.historical_prices,
                                   path=path / f"{self.name}-{sector.name}-generator.png")

