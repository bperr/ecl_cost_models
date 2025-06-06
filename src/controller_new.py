from pathlib import Path

import pandas as pd

from src.input_reader import InputReader
from src.network import Network


class Controller:
    def __init__(self, work_dir: Path, db_dir: Path):
        self.input_reader = InputReader(work_dir, db_dir)
        self.network = Network()

        self.years, self.zones, self.sectors, self.storages = None, None, None, None

    def read_inputs(self):
        prices = self.input_reader.read_db_prices()
        powers = self.input_reader.read_db_powers()
        self.years, self.zones, self.sectors, self.storages = self.input_reader.read_user_inputs()
        user_inputs = {"prices": prices, "powers": powers}
        return user_inputs

    def build_price_models(self):
        self.network.build_price_models()

        data = []

        for zone in self.network.zones:
            row_cons_max = [zone.name, "Cons_max"]
            row_cons_min = [zone.name, "Cons_min"]
            row_prod_min = [zone.name, "Prod_min"]
            row_prod_max = [zone.name, "Prod_max"]

            for sector in zone.sectors:
                prices = sector.price_model
                row_cons_max.append(prices[0])
                row_cons_min.append(prices[1])
                row_prod_min.append(prices[2])
                row_prod_max.append(prices[3])
            data += [row_cons_max, row_cons_min, row_prod_min, row_prod_max]

        df = pd.DataFrame(data, columns=["Zone", "Price Type"] + self.sectors)

        with pd.ExcelWriter(self.input_reader.work_dir / "results" / "Output_prices.xlsx") as writer:
            df.to_excel(writer, index=False)
