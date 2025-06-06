import pandas as pd

from src.zone import Zone
from src.interconnection import Interconnection

class Network:
    def __init__(self):
        self.zones: list[Zone] = list()
        self.interconnection: list[Interconnection] = list()

    def add_zone(self, zone_name: str, all_historical_powers: pd.DataFrame, storages:list[str],historical_prices:list[float]):
        zone = Zone(zone_name, historical_prices)
        self.zones.append(zone)

        for sector_name in all_historical_powers.columns:
            if sector_name in storages :
                zone.add_storage(sector_name, all_historical_powers[sector_name].tolist())
            else:
                zone.add_sector(sector_name, all_historical_powers[sector_name].tolist())


    def add_interconnection(self):
        #opf
        pass

    def build_price_models(self):
        for zone in self.zones:
            zone.build_price_model()

    def check_price_models(self):
        # Si sector est un stockage ou non on peut aussi check les valeurs de cons
        for zone in self.zones:
            for sector in zone.sectors:
                prices = sector.price_model
                # raise error si tuple vide ou prix mauvais ordre


    def check_power_models(self):
        # opf
        pass

    def run_OPF(self):
        # opf
        pass

