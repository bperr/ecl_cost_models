from numpy import inf
import pandas as pd

from src.interconnection import ExteriorInterconnection, Interconnection, OUT_ZONE_NAME
from src.opf_utils import TOL, bounded_value
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
        # Reset export per zone and update available power per storage
        for zone in self._zones.values():
            zone.reset_powers()
            zone.update_storages_availability(timestep=timestep)

        feasible_export_per_zone = {zone: zone.feasible_export_range(timestep=timestep)
                                    for zone in self._zones.values()}
        historical_power_per_interco = {interco: interco.historical_power(timestep)
                                        for interco in self._interconnections}

        outside_interconnections = list()  # Interconnections between a network zone and outside the network
        inside_interconnections = list()  # Interconnections between network zones
        for interco in self._interconnections:
            if isinstance(interco, ExteriorInterconnection):
                outside_interconnections.append(interco)
            else:
                inside_interconnections.append(interco)

        # Export per zone due to initial export per interconnection
        requested_export_per_zone = {zone: 0 for zone in self._zones.values()}

        # Add the zone representing outside the network
        if len(outside_interconnections) > 0:
            outside_interco = outside_interconnections[0]
            if outside_interco.zone_to.name == OUT_ZONE_NAME:
                outside_zone = outside_interco.zone_to
            else:
                assert outside_interco.zone_from.name == OUT_ZONE_NAME
                outside_zone = outside_interco.zone_from
            feasible_export_per_zone[outside_zone] = (-inf, inf)
            requested_export_per_zone[outside_zone] = 0

        outside_export_warnings = dict()
        for interco in outside_interconnections + inside_interconnections:
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
            assert max_export >= min_export

            # Initialise the export in the interconnection
            historical_export = historical_power_per_interco[interco]
            initial_export = bounded_value(value=historical_export,
                                           min_value=min_export, max_value=max_export)
            interco.set_export(power=initial_export)
            requested_export_per_zone[zone_from] += initial_export
            requested_export_per_zone[zone_to] -= initial_export

            # Warning if export power in an outside interconnection is not feasible
            # (It can occur if a storage availability is inconsistent with its historical power)
            if interco in outside_interconnections and initial_export != historical_power_per_interco[interco]:
                interco_str = interco.__repr__()  # f"{interco.zone_from.name} -> {interco.zone_to.name}"
                outside_export_warnings[f"{interco_str} | historical_export"] = historical_export
                outside_export_warnings[f"{interco_str} | initial_export"] = initial_export

        return outside_export_warnings

    def run_opf(self, timestep: pd.Timestamp):
        """
        Runs the Optimal Power Flow (OPF) algorithm on the network
        """

        # Export in each interconnection are initialised close to historical.
        # Warnings are returned if outside interconnections do not export their historical power.
        outside_interco_warnings = self.initialise_opf(timestep=timestep)

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
            return False, outside_interco_warnings  # The OPF did not converge

        # Run market in each zone with the final exports
        for zone in self._zones.values():
            zone.market_optimisation(timestep)

        # Store results
        for zone in self.zones.values():
            zone.update_storages_energy()
            zone.store_simulated_power(timestep)
        for interconnection in self._interconnections:
            interconnection.store_simulated_power(timestep)

        return True, outside_interco_warnings
