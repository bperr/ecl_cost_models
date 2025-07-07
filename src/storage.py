import pandas as pd

from src.sector import Sector


class Storage:
    """
        Represents an energy storage system composed of two separate sectors having the same name:
        one acting as a load (charging) and the other as a generator (discharging).
    """

    def __init__(self, sector_name: str, historical_powers: pd.Series, is_controllable: bool):
        """
            Initializes the Storage instance by splitting historical power data into load (negative powers) and
            generator sectors (positive powers).

            :param sector_name: Name of the sectors associated with this storage
            :param historical_powers: Time series of historical power values (can be positive or negative)
            :param is_controllable : Indicates whether the storage system is controllable
        """
        powers_load = historical_powers[historical_powers <= 0]
        powers_generator = historical_powers[historical_powers >= 0]

        self._load = Sector(sector_name, powers_load, is_controllable=is_controllable, is_storage_load=True)
        self._generator = Sector(sector_name, powers_generator, is_controllable=is_controllable)

    @property
    def load(self):
        return self._load

    @property
    def generator(self):
        return self._generator
