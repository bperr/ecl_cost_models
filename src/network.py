import pandas as pd

from src.interconnection import Interconnection
from src.opf_utils import TOL
from src.zone import Zone


class Network:
    """
    Represents an energy network composed of zones (themselves composed of sectors) and interconnections.

    This class manages the structure of the network by adding all the required zones and sectors
    (including storages) and interconnections, and includes tools to build and validate price and power models.
    """

    def __init__(self, opf_mode: bool):
        self._zones: dict[str, Zone] = dict()
        self._interconnections: list[Interconnection] = list()
        self._datetime_index: list[pd.Timestamp] | None = None  # Updated in add_zone
        self._is_opf_mode = opf_mode

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

        # update the attribute datetime_index with the timesteps (indexes) of the first zone's historical power data
        # these timesteps are then used as timesteps for the opfs
        if self._datetime_index is None:
            valid_prices = historical_prices.dropna()
            self._datetime_index = valid_prices.index

        else:
            idx1 = self._datetime_index
            idx2 = historical_prices.dropna().index

            common_idx = idx1.intersection(idx2)

            self._datetime_index = common_idx

        for sector_name in sectors_historical_powers.columns:
            is_controllable = sector_name in controllable_sectors
            if sector_name in storages:
                zone.add_storage(sector_name, sectors_historical_powers[sector_name], is_controllable,
                                 opf_mode=self._is_opf_mode)
            else:
                zone.add_sector(sector_name, sectors_historical_powers[sector_name], is_controllable)

    def add_interconnection(self, zone_from: Zone, zone_to: Zone, interco_power_rating: float,
                            historical_power_flows: pd.Series):
        """
        Adds an interconnection between two zones

        :param zone_from: Zone object representing the "exporting" zone
        :param zone_to: Zone object representing the "importing" zone
        :param interco_power_rating: The interconnection power rating between the two zones
        :param historical_power_flows: pd.Series containing historical power flows between the two zones per hour
        (positive when power is transferred from zone "from" to zone "to" and negative if power is transferred in
        the opposite direction)
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

    def run_opf(self, timestep: pd.Timestamp):
        """
        Runs the Optimal Power Flow (OPF) algorithm on the network

        Note:
            Method currently not implemented
        """

        # Initialise the network (no export)
        for zone in self._zones.values():
            zone.reset_powers()
        for interco in self._interconnections:
            interco.reset_power()

        # Run market in each zone
        for zone in self._zones.values():
            zone.market_optimisation(timestep)

        # Start optimisation loop
        converged = False
        iter_max = 100
        i = 0
        while not converged and i < iter_max:
            cost_change = 0
            for line in self._interconnections:
                cost_change += line.optimise_export(timestep)

            assert cost_change < TOL  # <= 0
            if abs(cost_change) < TOL:
                converged = True
            i += 1

        if not converged:
            return False  # The OPF did not converge

        # Run market in each zone with the final exports
        for zone in self._zones.values():
            zone.market_optimisation(timestep)

        # Store results
        for zone in self.zones.values():
            zone.store_simulated_power(timestep)
        for interconnection in self._interconnections:
            interconnection.store_simulated_power(timestep)

        return True

    def check_power_models(self):
        """
        Validates power models for each sector or interconnection

        Note:
            Method currently not implemented (will be for OPF).
        """
        pass
