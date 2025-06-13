import pandas as pd

from src.sector import Sector


class Storage:
    def __init__(self, sector_name: str, historical_powers: pd.Series):
        powers_load = historical_powers[historical_powers <= 0]
        powers_generator = historical_powers[historical_powers >= 0]

        self.load = Sector(sector_name, powers_load, is_load=True)
        self.generator = Sector(sector_name, powers_generator)
