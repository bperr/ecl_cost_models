import warnings

import pandas as pd

from src.interconnection import Interconnection
from src.sector import Sector
from src.storage import Storage


class Zone:
    """
    Represents a geographical or zone (composed of one or more countries, defined in the user inputs)
    in the energy network

    Each zone contains multiple sectors, along with historical SPOT price data and mechanisms for
    building price models, computing demand, and plotting results
    """

    def __init__(self, zone_name: str, historical_prices: pd.Series):
        """
        Initializes a new Zone instance

        :param zone_name: Name of the zone
        :param historical_prices: Time series of electricity prices for the zone
        """
        self._name = zone_name
        self._historical_prices = historical_prices.dropna()  # in €/MWh
        self._sectors: list[Sector] = list()
        self._storages: list[Storage] = list()

        self._interconnections: list[Interconnection] = list()
        self._power_demand = list()  # in MW
        self._prices_out = list()  # in €/MWh

    @property
    def name(self):
        return self._name

    @property
    def sectors(self):
        return self._sectors

    @property
    def interconnections(self):
        return self._interconnections

    def add_sector(self, sector_name: str, historical_powers: pd.Series, is_controllable: bool):
        """
        Adds a new sector (production or consumption) to the zone with its name, historical powers
        and controllability. Updates the list of sectors accordingly.

        :param sector_name: Name of the sector
        :param historical_powers: Power data for the sector in MW
        :param is_controllable: Indicates whether the sector is controllable
        """
        sector = Sector(sector_name, historical_powers, is_controllable)
        sector.build_availabilities()
        self.sectors.append(sector)

    def build_price_model(self, prices_init: tuple):
        """
        Builds price models for all sectors in the zone

        :param prices_init: Tuple of bounds and step size for price search
        """

        print(f"\n ==== Building price model for {self._name} ====")
        if self._historical_prices.replace(0, pd.NA).dropna().empty:
            warnings.warn(f"No prices available for {self._name}"
                          f"skipping plots.", RuntimeWarning)

        for sector in self.sectors:
            sector.build_price_model(historical_prices=self._historical_prices, prices_init=prices_init,
                                     zone_name=self._name)
        print("=" * 30)

    def set_price_model(self, price_models: dict[str, list[float]]):
        """
        Assign a price model to each sector in the zone.

        For each sector in the zone:
        - If the sector is a storage load (is_storage_load == True),
        use the price components in the order [cons_none, cons_full].
        - Otherwise, the price components are used in the order [prod_none, prod_full].

        :param price_models: Dictionary of price models by sector. Expected format:
            price_models[sector_name] = [cons_full, cons_none, prod_none, prod_full]
        """
        for sector in self.sectors:
            price_components = price_models[sector.name]
            if sector.is_storage_load:
                sector_price_model = (price_components[1], price_components[0])
            else:
                sector_price_model = (price_components[2], price_components[3])
            sector.set_price_model(sector_price_model)

    def compute_demand(self, net_imports: pd.Series):
        """
        Calculates the net historical demand for the zone, adjusted for imports and exports.

        If demand has not yet been calculated (_power_demand attribute empty), production for all sectors is summed
        and imports/exports are added to obtain net demand.

        :param net_imports: Time series of net power imports (positive = import, negative = export).
                            If net_imports is None or not supplied, the series is considered to be zero
                            (no exchanges).
        """
        if len(self._power_demand) == 0:
            # The production from all sectors is summed
            zone_production = sum(sector.historical_powers.fillna(0) for sector in self._sectors)

            if isinstance(net_imports, pd.Series):
                net_imports_clean = net_imports.fillna(0)
            else:  # if net_import is None or 0
                net_imports_clean = pd.Series(0, index=zone_production.index)

            self._power_demand = net_imports_clean + zone_production

    def add_storage(self, sector_name: str, historical_powers: pd.Series, is_controllable: bool):
        """
        Adds an energy storage unit to the zone. Updates the list of sectors accordingly.
        This includes both the charging (load) and discharging (generator) components that have the same sector name

        :param sector_name: Name of the storage unit
        :param historical_powers: Power time series of the storage (consumption and generation) in MW
        :param is_controllable: Indicates whether the storage behavior is controllable
        """
        storage = Storage(sector_name, historical_powers, is_controllable)
        storage.load.build_availabilities()
        storage.generator.build_availabilities()
        self._storages.append(storage)
        self.sectors.append(storage.load)
        self.sectors.append(storage.generator)

    def add_interconnection(self, interconnection: Interconnection):
        """
        Adds an interconnection to the zone. The already created instance of Interconnection is added in the
        interconnection list of the zone
        :param interconnection: connection between this zone and another zone with power rating and power in
        """
        self._interconnections.append(interconnection)

    def cost_function(self, timestep: pd.Timestamp) -> float:
        """
        Calculates the cost of the system within the zone at the given timestep
        Not implemented yet
        :return:
        """

    def store_simulated_power(self, timestep: pd.Timestamp):
        """
        Updates the simulated powers for all sectors and interconnections in the zone for a specific timestep.

        This method loops through all sectors and all interconnections associated with the zone,
        and calls their `store_simulated_power` method for the provided timestep to refresh their simulated power
        time series.

        Used during the power flow simulation to update results at each timestep.

        :param timestep: pd.Timestamp representing the current simulation timestep.
        """
        for sector in self._sectors:
            sector.store_simulated_power(timestep)

        for interconnection in self._interconnections:
            interconnection.store_simulated_power(timestep)

    def save_plots(self, path):
        """
        Saves the historical use ratios vs. price and the resulting piecewise linear model
        for each sector in the zone

        :param path: path where plots will be saved
        """
        for sector in self.sectors:
            if sector.is_storage_load:
                sector.plot_result(zone_name=self._name, historical_prices=self._historical_prices,
                                   path=path / f"{self._name}-{sector.name}-load.png")
            else:
                sector.plot_result(zone_name=self._name, historical_prices=self._historical_prices,
                                   path=path / f"{self._name}-{sector.name}-generator.png")
