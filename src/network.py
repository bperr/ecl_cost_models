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
        self._zones: dict[str, Zone] = dict()
        self._interconnections: list[Interconnection] = list()
        self._datetime_index = None  # Updated in add_zone

    @property
    def zones(self):
        return self._zones

    @property
    def interconnections(self):
        return self._interconnections

    @property
    def datetime_index(self):
        return self._datetime_index

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
        self._zones[zone_name] = zone

        if self._datetime_index is None:
            self._datetime_index = sectors_historical_powers.index
        else:
            idx1 = self._datetime_index
            idx2 = sectors_historical_powers.index

            if not idx1.equals(idx2):
                diff_1 = idx1.difference(idx2)
                diff_2 = idx2.difference(idx1)

                print(f"Timestep issue for {zone_name}")
                if not diff_1.empty:
                    print(f"Timestamps in self._datetime_index but not in sectors_historical_powers: {diff_1}")
                if not diff_2.empty:
                    print(f"Timestamps in sectors_historical_powers but not in self._datetime_index: {diff_2}")

        for sector_name in sectors_historical_powers.columns:
            is_controllable = sector_name in controllable_sectors
            if sector_name in storages:
                zone.add_storage(sector_name, sectors_historical_powers[sector_name], is_controllable)
            else:
                zone.add_sector(sector_name, sectors_historical_powers[sector_name], is_controllable)

    def add_interconnection(self, zone_from: Zone, zone_to: Zone, interco_power_rating: float,
                            historical_power_flows: pd.Series):
        """
            Adds an interconnection between two zones

            :param zone_from: The name of the zone "from"
            :param zone_to: The name of the zone "to"
            :param interco_power_rating: The interconnection power rating between the two zones
            :param historical_power_flows: pd.Series containing historical power flows between the two zones per hour
            (positive when power is transferred from zone "from" to zone "to" and negative if power is transferred in
            the opposite direction)

            Note:
                Method currently not implemented (will be for OPF).
        """
        interconnection = Interconnection(zone_from, zone_to, interco_power_rating, historical_power_flows)
        self._interconnections.append(interconnection)

        # interconnection is added to both concerned zones interconnections list
        zone_to.add_interconnection(interconnection)
        zone_from.add_interconnection(interconnection)

    def build_price_models(self, prices_init: tuple):
        """
            Builds price models for all sectors of all the zones in the network.

            :param prices_init: Prices boundaries to make the initialisation of prices

            :raise:
                ValueError: If no zones have been added to the network.
        """

        if len(self._zones) == 0:
            raise ValueError("No zones available to build price models.")
        for zone in self._zones.values():
            zone.build_price_model(prices_init)

    def set_price_model(self, price_models: dict):
        """
        Set price models for all sectors of all the zones in the network.

        :param price_models: embedded dictionary with the following format
            price_models[zone][sector] = [cons_full, cons_none, prod_none, prod_full]
        """
        for zone_name, zone in self.zones.items():
            zone_price_models = price_models[zone_name]
            zone.set_price_model(zone_price_models)

    @staticmethod
    def check_price_models(price_models: dict, storages: list[str]):
        """
            Validates the integrity and logical consistency of the price models for each sector in all zones.

            The price_models dictionary should have the following structure:
            price_models[zone][sector] = [cons_full, cons_none, prod_none, prod_full]

            Validation rules:
            - Sectors that are not storage units must not have consumption prices.
            - For all sectors: prod_none must be less than or equal to prod_full
            - For all sectors: cons_full must be less than or equal to cons_none
            - For all sectors: cons_none must be less than or equal to prod_none

            :param price_models: Dictionary containing the price models per zone and sector
            :param storages: List of sector names that are storages

            :raises ValueError: If any of the logical consistency checks fail
    """

        for zone, sectors in price_models.items():
            for sector, prices in sectors.items():
                cons_full, cons_none, prod_none, prod_full = prices

                # If sector is not storage, it should not have consumption prices
                if sector not in storages:
                    if any(p is not None for p in [cons_full, cons_none]):
                        raise ValueError(
                            f"Sector '{sector}' in zone '{zone}' is not storage but has consumption prices."
                        )

                # Check prod_none <= prod_full
                if prod_none is not None and prod_full is not None:
                    if prod_none > prod_full:
                        raise ValueError(
                            f"Logical error: Prod_none > Prod_full for '{sector}' in zone '{zone}' "
                            f"({prod_none} > {prod_full})"
                        )

                # Check cons_full <= cons_none
                if cons_full is not None and cons_none is not None:
                    if cons_full > cons_none:
                        raise ValueError(
                            f"Logical error: Cons_full > Cons_none for '{sector}' in zone '{zone}' "
                            f"({cons_full} > {cons_none})"
                        )

                # Check cons_none <= prod_none
                if cons_none is not None and prod_none is not None:
                    if cons_none > prod_none:
                        raise ValueError(
                            f"Consumption price no power (c0 = {cons_none}) must be lower than "
                            f"production price no power (p0 = {prod_none}) for '{sector}' in zone '{zone}'."
                        )

    def check_power_models(self):
        """
            Validates power models for each sector or interconnection

            Note:
                Method currently not implemented (will be for OPF).
        """
        pass

    def run_opf(self, timestep: pd.Timestamp):
        """
            Runs the Optimal Power Flow (OPF) algorithm on the network

            Note:
                Method currently not implemented
        """
        # converged = False
        n_full_iter = 100
        for i in range(n_full_iter):
            # converged = True
            for line in self._interconnections:
                cost_change = line.optimize_export(timestep)
                if cost_change < 0:
                    pass
                    # converged = False

        for zone in self.zones.values():
            zone.update_simulated_powers(timestep)

        # Update each sector._simulated_powers
        # Update each interconnection._simulated_powers
        raise NotImplementedError
