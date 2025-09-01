import warnings

import pandas as pd

from src.interconnection import ExteriorInterconnection, Interconnection
from pathlib import Path
from src.interconnection import Interconnection
from src.opf_utils import TOL, bounded_value
from src.zone import Zone
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import PatternFill

POWERS_ERRORS_EXCEL_FILE = "simulated_powers_errors.xlsx"
SECTORS_SIMULATION_ERRORS_DIR = 'errors_simulated_powers_by_sector'
LINES_SIMULATION_ERRORS_DIR = 'errors_simulated_powers_by_interconnection'

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

    def remove_invalid_datetime(self, invalid_datetime: set[pd.Timestamp]):
        """
        Remove from self._datetime_index a list of timestamp that cannot be simulated.

        Parameters
        ----------
        invalid_datetime: Timestamp that cannot be simulated.
        """
        self._datetime_index = self._datetime_index.drop(invalid_datetime)

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

    def add_exterior_interconnection(self, zone_from: Zone, zone_to: Zone, historical_power_flows: pd.Series):
        """
        Add an interconnection with the 'Exterior' zone.

        Parameters
        ----------
        zone_from: A zone in the network.
        zone_to: A the 'Exterior' zone, not stored inside the network
        historical_power_flows: pd.Series containing the historical net power flow from 'zone from' to 'zone to'.
        """
        interconnection = ExteriorInterconnection(zone_from, zone_to, historical_power_flows)
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

    def build_storage_constraints(self, energy_ratings: dict, mean_inflows: dict):
        """
        Build min/max energy constraint time series for each storage.

        Parameters
        ----------
        energy_ratings: Energy rating per storage. Used to run OPF but not to build price models
        mean_inflows: Constant natural charging per storage
        """
        for zone_name, zone in self._zones.items():
            zone.build_storage_constraints(datetime_index=self._datetime_index,
                                           energy_ratings=energy_ratings[zone_name],
                                           mean_inflows=mean_inflows[zone_name])

    def initialise_opf(self, timestep):
        """
        Initialise export in each interconnection with values close to historical powers, by respecting feasible export
        per zone.
        """

        def get_exterior_interconnection(inside_zone: Zone) -> ExteriorInterconnection | None:
            # By construction, outside connection should be the last
            for interconnection in reversed(inside_zone.interconnections):
                if isinstance(interconnection, ExteriorInterconnection):
                    return interconnection
            return None  # This should not happen as each zone is connected to the exterior zone

        # Reset export per zone and update available power per storage
        for zone in self._zones.values():
            zone.reset_powers()
            zone.update_storages_availability(timestep=timestep)

        # Reset export with the outside zone and list inner network interconnection
        inside_interconnections = list()  # Interconnections between network zones
        for interco in self._interconnections:
            if isinstance(interco, ExteriorInterconnection):
                interco.set_export(power=interco.historical_powers[timestep])
            else:
                inside_interconnections.append(interco)

        # Compute minimum and maximum export per zone, considering storage constraints and exchange with outside
        feasible_export_per_zone = {}
        for zone in self._zones.values():
            min_net_export, max_net_export = zone.feasible_export_range(timestep)
            exterior_interco = get_exterior_interconnection(zone)
            if exterior_interco is not None:
                external_net_export = exterior_interco.get_export(zone)  # Is equal to historical power
                min_net_export -= external_net_export
                max_net_export -= external_net_export

            feasible_export_per_zone[zone] = min_net_export, max_net_export

        historical_power_per_interco = {interco: interco.historical_power(timestep)
                                        for interco in self._interconnections}

        # Export per zone due to initial export per interconnection
        requested_export_per_zone = {zone: 0 for zone in self._zones.values()}

        # Set initial power in interconnections allowing to respect export constraints
        for interco in inside_interconnections:
            # Feasible export per zone
            zone_from = interco.zone_from
            zone_to = interco.zone_to
            min_from, max_from = feasible_export_per_zone[zone_from]
            min_to, max_to = feasible_export_per_zone[zone_to]

            # Feasible export in the interconnection
            min_from -= requested_export_per_zone[zone_from]
            max_from -= requested_export_per_zone[zone_from]
            min_to -= requested_export_per_zone[zone_to]
            max_to -= requested_export_per_zone[zone_to]
            min_export = max(min_from, - max_to)
            max_export = min(max_from, - min_to)
            if min_export > max_export:
                min_export = max_export

            # Initialise the export in the interconnection
            historical_export = historical_power_per_interco[interco]
            initial_export = bounded_value(
                value=bounded_value(value=historical_export, min_value=min_export, max_value=max_export),
                min_value=-interco.power_rating, max_value=interco.power_rating
            )
            interco.set_export(power=initial_export)
            requested_export_per_zone[zone_from] += initial_export
            requested_export_per_zone[zone_to] -= initial_export

        # Check requested export per zone is within allowed limits
        for zone, requested_export in requested_export_per_zone.items():
            min_net_export, max_net_export = feasible_export_per_zone[zone]
            if not (min_net_export <= requested_export <= max_net_export):
                # For the OPF to initialise, we modify the interconnection with the exterior, thus artificially
                # falsifying the simulation inputs.
                exterior_interconnection = get_exterior_interconnection(zone)
                assert exterior_interconnection is not None

                if requested_export > max_net_export:
                    delta_power = max_net_export - requested_export  # <0, power to remove in exterior interconnection
                else:
                    delta_power = min_net_export - requested_export  # >0, power to add in exterior interconnection
                exterior_interconnection.set_export(exterior_interconnection.get_export(zone) + delta_power)
                warnings.warn(f"At timestep {timestep}, zone {zone.name} export constraints could not be satisfied. "
                              f"Interconnection with the outside zone is modified by {delta_power}, therefore "
                              "simulation results cannot be compared with historical data", stacklevel=2)

    def run_opf(self, timestep: pd.Timestamp):
        """
        Runs the Optimal Power Flow (OPF) algorithm on the network
        """

        # Export in each interconnection are initialised close to historical.
        # Warnings are returned if outside interconnections do not export their historical power.
        self.initialise_opf(timestep=timestep)

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
            zone.update_storages_energy()
            zone.store_simulated_power(timestep)
        for interconnection in self._interconnections:
            interconnection.store_simulated_power(timestep)

        return True

    def compare_power_series(self, simulation_dir_path: Path):
        """
        Compute and save errors between simulated and historical powers for all zones and interconnections. It generates
        comparison plots for each one. It also generates an Excel file containing a "sectors_errors" sheet with error
        metrics per sector and a "lines_errors" sheet with error metrics per interconnection

        For each zone and interconnection in the network :
        - Calls `compare_power_series` to compute error metrics and generate plots comparing simulated vs historical
            powers.
        - Aggregates the results into two separate lists: one for sectors (zones), one for interconnections.
        - Saves both sets of results into an Excel file with two sheets: "sectors_errors" and "lines_errors".

        Parameters
        ----------
        simulation_dir_path:Path: Root directory where plots and the Excel summary file will be saved
        """
        zone_errors_data = []
        lines_errors_data = []

        for zone in self.zones.values():
            zone_errors_data += zone.compare_power_series(simulation_dir_path / SECTORS_SIMULATION_ERRORS_DIR)

        for interconnection in self._interconnections:
            lines_errors_data.append(
                interconnection.compare_power_series(simulation_dir_path / LINES_SIMULATION_ERRORS_DIR))

        df_sectors_errors = pd.DataFrame(zone_errors_data)
        df_lines_errors = pd.DataFrame(lines_errors_data)

        excel_path = simulation_dir_path / POWERS_ERRORS_EXCEL_FILE

        # Définition des couleurs
        green_fill = PatternFill(start_color="90EE90", end_color="90EE90", fill_type="solid")  # vert clair
        orange_fill = PatternFill(start_color="FFD580", end_color="FFD580", fill_type="solid")  # orange clair
        red_fill = PatternFill(start_color="FF7F7F", end_color="FF7F7F", fill_type="solid")  # rouge clair

        with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
            df_sectors_errors.to_excel(writer, sheet_name="sectors_errors", index=False)
            df_lines_errors.to_excel(writer, sheet_name="lines_errors", index=False)

            workbook = writer.book

            # Parcourir toutes les feuilles écrites
            for sheet_name, df in {
                "sectors_errors": df_sectors_errors,
                "lines_errors": df_lines_errors,
            }.items():
                worksheet = workbook[sheet_name]

                # Chercher les colonnes contenant "relative"
                for idx, col_name in enumerate(df.columns, start=1):
                    if "relative" in col_name.lower():
                        # Appliquer format pourcentage
                        for cells in worksheet.iter_cols(min_col=idx, max_col=idx, min_row=2):
                            for cell in cells:
                                cell.number_format = "0.0%"

                        # Définir la plage de données (sans l'entête)
                        col_letter = worksheet.cell(row=1, column=idx).column_letter
                        data_range = f"{col_letter}2:{col_letter}{worksheet.max_row}"

                        # Formules Excel avec ABS()
                        worksheet.conditional_formatting.add(
                            data_range,
                            FormulaRule(formula=[f"=ABS({col_letter}2)<0.1"], fill=green_fill)
                        )
                        worksheet.conditional_formatting.add(
                            data_range,
                            FormulaRule(formula=[f"=AND(ABS({col_letter}2)>=0.1,ABS({col_letter}2)<=0.25)"],
                                        fill=orange_fill)
                        )
                        worksheet.conditional_formatting.add(
                            data_range,
                            FormulaRule(formula=[f"=ABS({col_letter}2)>0.25"], fill=red_fill)
                        )
