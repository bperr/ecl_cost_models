import pandas as pd

from src.interconnection import Interconnection
from src.zone import Zone


class Network:
    """
        Represents an energy network composed of zones (themselves composed of sectors) and interconnections.

        This class manages the structure of the network by adding all the required zones and sectors
        (including storages) and interconnections, and includes tools to build and validate price and power models.
    """

    def __init__(self):
        self._zones: list[Zone] = list()
        self._interconnections: list[Interconnection] = list()

    @property
    def zones(self):
        return self._zones

    def add_zone(self, zone_name: str, sectors_historical_powers: pd.DataFrame, storages: list[str],
                 controllable_sectors: list[str], historical_prices: pd.Series):
        """
        Adds a new zone to the network with its sectors and storages, it includes all the powers data for the sectors
        and all the prices data for the zone

        :param zone_name: The name of the zone
        :param sectors_historical_powers: Historical power data for each sector (columns = sector names)
        :param storages: List of sector names that are storages
        :param controllable_sectors: List of sector names that are controllable
        :param historical_prices: Historical prices for the zone
        """
        zone = Zone(zone_name, historical_prices)
        self._zones.append(zone)

        for sector_name in sectors_historical_powers.columns:
            is_controllable = sector_name in controllable_sectors
            if sector_name in storages:
                zone.add_storage(sector_name, sectors_historical_powers[sector_name], is_controllable)
            else:
                zone.add_sector(sector_name, sectors_historical_powers[sector_name], is_controllable)

    def add_interconnection(self):
        """
            Adds an interconnection between two zones

            Note:
                Method currently not implemented (will be for OPF).
        """
        pass

    def build_price_models(self, prices_init: tuple):
        """
            Builds price models for all sectors of all the zones in the network.

            :param prices_init: Prices boundaries to make the initialisation of prices

            :raise:
                ValueError: If no zones have been added to the network.
        """

        if len(self._zones) == 0:
            raise ValueError("No zones available to build price models.")
        for zone in self._zones:
            zone.build_price_model(prices_init)

    def check_price_models(self):
        # FIXME : could be changed depending on the input reader read_price_model method - will be done for OPF
        """
            Validates the integrity of the price models for each sector in all zones

            :raise:
                ValueError: If prices are missing or incorrectly defined
        """
        # To add : c_price_no_power <= p_price_no_power --> "Consumption price c0 must be lower than"
        # f"production price p0 for {sector.name} in '{zone.name}'"
        for zone in self._zones:
            for sector in zone.sectors:
                prices = sector.price_model

                if len(prices) == 0:
                    raise ValueError(f"Prices values are missing for {sector.name} in '{zone._name}'")

                if sector.is_load:
                    c_price_no_power, c_price_full_power = prices
                    if c_price_full_power > c_price_no_power:
                        raise ValueError(
                            f"Consumption price c100 must be lower than c0 for {sector.name} in '{zone._name}'")
                else:
                    p_price_no_power, p_price_full_power = prices
                    if p_price_no_power > p_price_full_power:
                        raise ValueError(
                            f"Production price p0 must be lower than p100 for {sector.name} in '{zone._name}'")

    def check_power_models(self):
        """
            Validates power models for each sector or interconnection

            Note:
                Method currently not implemented (will be for OPF).
        """
        pass

    def run_OPF(self):
        """
            Runs the Optimal Power Flow (OPF) algorithm on the network

            Note:
                Method currently not implemented.
        """
        pass
