import pandas as pd

from src.sector import Sector
from src.storage import Storage


class Zone:
    def __init__(self, zone_name: str, historical_prices: pd.Series):
        self.name = zone_name
        self.historical_prices = historical_prices.dropna()
        self.sectors: list[Sector] = list()
        self.storages: list[Storage] = list()
        self.power_demand = list()
        self.prices_out = list()

    def add_sector(self, sector_name: str, historical_powers: pd.Series, is_controllable: bool, saving_data: dict):
        sector = Sector(sector_name, historical_powers, is_controllable)
        availabilities = sector.build_availabilities()
        self.sectors.append(sector)

        if self.name == "FR" and sector_name == "nuclear":
            work_dir = saving_data["work_dir"]
            start_date = saving_data["start_year"]
            end_date = saving_data["end_year"]
            output_path = work_dir / "availabilities" / f"French_nuclear_availabilities_{start_date}-{end_date}.xlsx"
            availabilities.to_frame(name="Availabilities (MW)").to_excel(output_path)

    def build_price_model(self, prices_init: tuple):
        print(f"\n ==== Building price model for {self.name} ====")
        for sector in self.sectors:
            # TODO : si les prix sont tous nuls ou vides alors warning
            sector.build_price_model(historical_prices=self.historical_prices, prices_init=prices_init,
                                     zone_name=self.name)
        print("=" * 30)

    def compute_demand(self, net_imports: list[float]):
        # Opf
        pass

    def add_storage(self, sector_name: str, historical_powers: pd.Series, is_controllable: bool):
        storage = Storage(sector_name, historical_powers, is_controllable)
        storage.load.build_availabilities()
        storage.generator.build_availabilities()
        self.storages.append(storage)
        self.sectors.append(storage.load)
        self.sectors.append(storage.generator)

    def save_plots(self, path):
        for sector in self.sectors:
            if sector.is_load:
                sector.plot_result(zone_name=self.name, historical_prices=self.historical_prices,
                                   path=path / f"{self.name}-{sector.name}-load.png")
            else:
                sector.plot_result(zone_name=self.name, historical_prices=self.historical_prices,
                                   path=path / f"{self.name}-{sector.name}-generator.png")
