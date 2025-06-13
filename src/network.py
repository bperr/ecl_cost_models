import pandas as pd

from src.interconnection import Interconnection
from src.zone import Zone


class Network:
    def __init__(self):
        self.zones: list[Zone] = list()
        self.interconnection: list[Interconnection] = list()

    def add_zone(self, zone_name: str, sectors_historical_powers: pd.DataFrame, storages: list[str],
                 historical_prices: pd.Series):

        zone = Zone(zone_name, historical_prices)
        self.zones.append(zone)

        for sector_name in sectors_historical_powers.columns:
            if sector_name in storages:
                zone.add_storage(sector_name, sectors_historical_powers[sector_name])
            else:
                zone.add_sector(sector_name, sectors_historical_powers[sector_name])

    def add_interconnection(self):
        # opf
        pass

    def build_price_models(self, prices_init: tuple):
        if not self.zones:
            raise ValueError("No zones available to build price models.")
        for zone in self.zones:
            zone.build_price_model(prices_init)

    def check_price_models(self):
        # A ajouter : c_price_no_power <= p_price_no_power --> "Consumption price c0 must be lower than"
        # f"production price p0 for {sector.name} in '{zone.name}'"
        for zone in self.zones:
            for sector in zone.sectors:
                prices = sector.price_model

                if len(prices) == 0:
                    raise ValueError(f"Prices values are missing for {sector.name} in '{zone.name}'")

                if sector.is_load:
                    c_price_no_power, c_price_full_power = prices
                    if not (c_price_full_power <= c_price_no_power):
                        raise ValueError(
                            f"Consumption price c100 must be lower than c0 for {sector.name} in '{zone.name}'")
                else:
                    p_price_no_power, p_price_full_power = prices
                    if not (p_price_no_power <= p_price_full_power):
                        raise ValueError(
                            f"Production price p0 must be lower than p100 for {sector.name} in '{zone.name}'")

    def check_power_models(self):
        # opf
        pass

    def run_OPF(self):
        # opf
        pass
