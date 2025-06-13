from pathlib import Path

import pandas as pd

from src.input_reader import InputReader
from src.network import Network


class Controller:
    def __init__(self, work_dir: Path, db_dir: Path):
        self.input_reader = InputReader(work_dir, db_dir)
        self.work_dir = work_dir
        self.network = None

        self.prices = self.input_reader.read_db_prices()
        self.powers = self.input_reader.read_db_powers()
        self.years, self.zones, self.sectors, self.storages, self.prices_init = self.input_reader.read_user_inputs()

    def build_price_models(self):
        create_file = True

        for start_year, end_year in self.years:
            self.network = Network()
            prices = self.prices[(self.prices.index.year >= start_year) & (self.prices.index.year <= end_year)]
            powers = {
                zone: df[(df.index.year >= start_year) & (df.index.year <= end_year)]
                for zone, df in self.powers.items()
            }

            for zone in self.zones:
                self.network.add_zone(zone_name=zone, sectors_historical_powers=powers[zone],
                                      storages=self.storages, historical_prices=prices[zone])
            self.network.build_price_models(self.prices_init[f"{start_year}-{end_year}"])
            self.export_price_models(start_year, end_year, create_file)

            create_file = False

    def export_price_models(self, start_year: int, end_year: int, create_file: bool):
        data = []
        sectors = []
        loop = 1

        for zone in self.network.zones:
            row_cons_max = [zone.name, "Cons_max"]
            row_cons_min = [zone.name, "Cons_min"]
            row_prod_min = [zone.name, "Prod_min"]
            row_prod_max = [zone.name, "Prod_max"]

            follows_load = False

            for sector in zone.sectors:
                prices = sector.price_model

                if sector.is_load:
                    row_cons_max.append(prices[0])
                    row_cons_min.append(prices[1])
                    # zone.sectors list is created such as for a storage,
                    # the generator sector is always following the load sector
                    follows_load = True

                else:
                    if loop == 1:
                        sectors.append(sector.name)
                    row_prod_min.append(prices[0])
                    row_prod_max.append(prices[1])
                    follows_load = False

            # if storage, both prices from generator and load have to be added to complete the row
            if not follows_load:
                data += [row_cons_max, row_cons_min, row_prod_min, row_prod_max]

            plot_folder_path = self.work_dir / "results" / f"Plots for years {start_year}-{end_year}"
            plot_folder_path.mkdir(parents=True, exist_ok=True)
            zone.save_plots(plot_folder_path)
            loop += 1

        df = pd.DataFrame(data, columns=["Zone", "Price Type"] + sectors)

        with pd.ExcelWriter(self.input_reader.work_dir / "results" / "Output_prices.xlsx",
                            mode='w' if create_file else 'a') as writer:
            df.to_excel(writer, index=False, sheet_name=f"{start_year}-{end_year}")
