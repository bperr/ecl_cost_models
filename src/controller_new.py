from datetime import datetime
from pathlib import Path

import pandas as pd

from src.input_reader import InputReader
from src.network import Network


class Controller:
    def __init__(self, work_dir: Path, db_dir: Path):
        self.input_reader = InputReader(work_dir, db_dir)
        self.work_dir = work_dir
        self.network = None

        (self.years, self.zones, self.sectors,
         self.storages, self.controllable, self.prices_init) = self.input_reader.read_user_inputs()
        self.prices = self.input_reader.read_db_prices()
        self.powers = self.input_reader.read_db_powers()

    def build_price_models(self):
        create_file = True
        current_date = datetime.now().strftime("%Y%m%d_%Hh%M")

        for start_year, end_year in self.years:
            print("=" * 60)
            print("=" * 30)
            print(f"\n ====== Building price models for year {start_year}-{end_year} ======")
            self.network = Network()
            prices = self.prices[(self.prices.index.year >= start_year) & (self.prices.index.year <= end_year)]
            powers = {
                zone: df[(df.index.year >= start_year) & (df.index.year <= end_year)]
                for zone, df in self.powers.items()
            }

            for zone in self.zones:
                saving_data = {"start_year": start_year, "end_year": end_year, "work_dir": self.work_dir}
                self.network.add_zone(zone_name=zone, sectors_historical_powers=powers[zone],
                                      storages=self.storages, controllable=self.controllable,
                                      historical_prices=prices[zone], saving_data=saving_data)
            self.network.build_price_models(self.prices_init[f"{start_year}-{end_year}"])
            self.export_price_models(start_year, end_year, create_file, current_date)

            create_file = False

    def export_price_models(self, start_year: int, end_year: int, create_file: bool, current_date: str):
        data = []
        loop = 1

        sectors = []
        sector_to_index = {}

        for zone in self.network.zones:
            # Column mapping only for the first sector (identical for the others)
            if loop == 1:
                follows_load = False
                last_load_name = None

                for sector in zone.sectors:
                    if sector.is_load:  # New storage sector
                        sector_name = sector.name
                        sectors.append(sector_name)
                        sector_to_index[sector_name] = len(sectors) - 1
                        follows_load = True  # storage - load, next sector will be the associated generator sector
                        last_load_name = sector_name
                    else:
                        if follows_load:
                            # Storage - generator : same sector as the previous load
                            sector_to_index[sector.name] = sector_to_index[last_load_name]
                            follows_load = False
                        else:
                            # New production sector
                            sector_name = sector.name
                            sectors.append(sector_name)
                            sector_to_index[sector_name] = len(sectors) - 1

            # Row initialisation
            row_cons_max = [zone.name, "Cons_max"] + [""] * len(sectors)
            row_cons_min = [zone.name, "Cons_min"] + [""] * len(sectors)
            row_prod_min = [zone.name, "Prod_min"] + [""] * len(sectors)
            row_prod_max = [zone.name, "Prod_max"] + [""] * len(sectors)

            follows_load = False
            last_load_index = None

            for sector in zone.sectors:
                prices = sector.price_model

                if sector.is_load:
                    idx = sector_to_index[sector.name]
                    row_cons_min[idx + 2] = prices[0]
                    row_cons_max[idx + 2] = prices[1]
                    follows_load = True
                    last_load_index = idx
                else:
                    if follows_load:
                        idx = last_load_index
                        follows_load = False
                    else:
                        idx = sector_to_index[sector.name]
                    row_prod_min[idx + 2] = prices[0]
                    row_prod_max[idx + 2] = prices[1]

            data += [row_cons_max, row_cons_min, row_prod_min, row_prod_max]

            plot_folder_path = self.work_dir / f"results {current_date}" / f"Plots for years {start_year}-{end_year}"
            plot_folder_path.mkdir(parents=True, exist_ok=True)
            zone.save_plots(plot_folder_path)
            loop += 1

        df = pd.DataFrame(data, columns=["Zone", "Price Type"] + sectors)

        with pd.ExcelWriter(self.input_reader.work_dir / f"results {current_date}" / "Output_prices.xlsx",
                            mode='w' if create_file else 'a') as writer:
            df.to_excel(writer, index=False, sheet_name=f"{start_year}-{end_year}")
