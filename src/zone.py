import warnings

import pandas as pd

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

        self._power_demand = list()  # in MW
        self._prices_out = list()  # in €/MWh

    @property
    def name(self):
        return self._name

    @property
    def sectors(self):
        return self._sectors

    def add_sector(self, sector_name: str, historical_powers: pd.Series, is_controllable: bool):
        """
            Adds a new sector (production or consumption) to the zone with its name, historical powers
            and controllability. Updates the list of sectors accordingly.

            :param sector_name: Name of the sector
            :param historical_powers: Power data for the sector in MW
            :param is_controllable: Indicates whether the sector is controllable

            :return: None
        """
        sector = Sector(sector_name, historical_powers, is_controllable)
        sector.build_availabilities()
        self.sectors.append(sector)

    def build_price_model(self, prices_init: tuple):
        """
            Builds price models for all sectors in the zone

            :param prices_init: Tuple of bounds and step size for price search

            :raise: warning if there are no prices available for this zone
            :return: None
        """

        print(f"\n ==== Building price model for {self._name} ====")
        if self._historical_prices.replace(0, pd.NA).dropna().empty:
            warnings.warn(f"No prices available for {self._name}"
                          f"skipping plots.", RuntimeWarning)

        for sector in self.sectors:
            sector.build_price_model(historical_prices=self._historical_prices, prices_init=prices_init,
                                     zone_name=self._name)
        print("=" * 30)

    def compute_demand(self, net_imports: list[float]):
        """
            Computes net demand in the zone, adjusted for imports and exports

            :param net_imports: List of net imported powers (positive = import, negative = export)

            Note:
                Method not yet implemented (will be for OPF)
        """
        # Opf
        pass

    def add_storage(self, sector_name: str, historical_powers: pd.Series, is_controllable: bool):
        """
            Adds an energy storage unit to the zone. Updates the list of sectors accordingly.
            This includes both the charging (load) and discharging (generator) components that have the same sector name

            :param sector_name: Name of the storage unit
            :param historical_powers: Power time series of the storage (consumption and generation) in MW
            :param is_controllable: Indicates whether the storage behavior is controllable

            :return: None
        """
        storage = Storage(sector_name, historical_powers, is_controllable)
        storage.load.build_availabilities()
        storage.generator.build_availabilities()
        self._storages.append(storage)
        self.sectors.append(storage.load)
        self.sectors.append(storage.generator)

    def save_plots(self, path):
        """
            Saves the historical use ratios vs. price and the resulting piecewise linear model
            for each sector in the zone

            :param path: path where plots will be saved

            :return: None
        """
        for sector in self.sectors:
            if sector.is_load:
                sector.plot_result(zone_name=self._name, historical_prices=self._historical_prices,
                                   path=path / f"{self._name}-{sector.name}-load.png")
            else:
                sector.plot_result(zone_name=self._name, historical_prices=self._historical_prices,
                                   path=path / f"{self._name}-{sector.name}-generator.png")
