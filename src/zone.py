import warnings

import pandas as pd

from src.interconnection import Interconnection
from src.opf_utils import NodeCostFunction, TOL, assert_approx, DEMAND_PRICE, FAKE_PROD_PRICE, FAKE_CONS_PRICE
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
        self._name: str = zone_name
        self._historical_prices: pd.Series = historical_prices.dropna()  # in €/MWh
        self._sectors: list[Sector] = list()
        self._storages: list[Storage] = list()

        self._interconnections: list[Interconnection] = list()
        self._power_demand = pd.Series()  # in MW
        self._simulated_prices = pd.Series()  # in €/MWh

        # -- "Variable" attributes for OPF computation
        self._current_cost_function: NodeCostFunction | None = None
        self._current_export: float = 0

    def __repr__(self):
        return f"Zone {self._name} has {len(self._sectors)} sectors including {len(self._storages)} storages"

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
            if sector.name not in price_models.keys():
                # There is no provided price model for this sector
                assert sector.historical_powers.sum() == 0  # Because the sector does not really exist in this zone
                sector_price_model = (FAKE_PROD_PRICE, FAKE_PROD_PRICE)  # Default value
            else:
                price_components = price_models[sector.name]
                if sector.is_load:
                    sector_price_model = (price_components[1], price_components[0])
                else:
                    sector_price_model = (price_components[2], price_components[3])
            if None in sector_price_model:
                if sector.is_load:
                    sector_price_model = (FAKE_CONS_PRICE, FAKE_CONS_PRICE)
                    print(f"!!! Missing consumption prices for '{sector.name}' in zone '{self._name}'. "
                          f"Prohibitive prices are used: {sector_price_model} !!!")
                else:
                    sector_price_model = (FAKE_PROD_PRICE, FAKE_PROD_PRICE)
                    print(f"!!! Missing production prices for '{sector.name}' in zone '{self._name}'. "
                          f"Prohibitive prices are used: {sector_price_model} !!!")
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

            demand_sector = Sector("Demand", historical_powers=self._power_demand, is_controllable=False, is_load=True)
            demand_sector.set_price_model((DEMAND_PRICE, DEMAND_PRICE))
            demand_sector.build_availabilities()
            self._sectors.append(demand_sector)

    def add_storage(self, sector_name: str, historical_powers: pd.Series, is_controllable: bool, opf_mode: bool):
        """
        Adds an energy storage unit to the zone. Updates the list of sectors accordingly.
        This includes both the charging (load) and discharging (generator) components that have the same sector name

        :param sector_name: Name of the storage unit
        :param historical_powers: Power time series of the storage (consumption and generation) in MW
        :param is_controllable: Indicates whether the storage behavior is controllable
        """
        storage = Storage(sector_name, historical_powers, is_controllable, opf_mode=opf_mode)
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

        assert self._current_cost_function is not None
        self._simulated_prices[timestep] = self._current_cost_function.compute_price(self._current_export)

    def save_plots(self, path):
        """
        Saves the historical use ratios vs. price and the resulting piecewise linear model
        for each sector in the zone

        :param path: path where plots will be saved
        """
        for sector in self.sectors:
            if sector.is_load:
                sector.plot_result(zone_name=self._name, historical_prices=self._historical_prices,
                                   path=path / f"{self._name}-{sector.name}-load.png")
            else:
                sector.plot_result(zone_name=self._name, historical_prices=self._historical_prices,
                                   path=path / f"{self._name}-{sector.name}-generator.png")

    # ---- OPF solving methods ---- #

    def get_current_export(self) -> float:
        """
        Returns net power exported by the node (power import if < 0)
        """
        self.update_current_export()
        return self._current_export

    def update_current_export(self):
        """
        Compute the net exported power by the node by considering all its lines.
        """
        self._current_export = sum([line.get_export(zone=self) for line in self._interconnections])

    def get_cost_function(self, timestep: pd.Timestamp) -> NodeCostFunction:
        """
        Returns the :class:`.NodeCostFunction` of the node.
        """
        if self._current_cost_function is None:
            self.update_cost_function(timestep)
        return self._current_cost_function

    def update_cost_function(self, timestep: pd.Timestamp):
        threshold_prices_list = list()
        for sector in self._sectors:  # + list(self._loads.values()):
            threshold_prices_list.extend(list(sector.price_model))
        threshold_prices_list = sorted(set(threshold_prices_list))

        # To compute the node cost function, we build in the first place its price/power curve by considering the
        # price_start and price_full of the loads and generators in the node. This is a piecewise linear function whose
        # "rupture" points are the threshold prices.
        # Integrating the reciprocal curve (power/price) allows to obtain the power/cost curve. This function is a
        # piecewise polynomial function whose "rupture" points are the powers corresponding to the threshold prices.
        #
        # To build the cost function of the node, we only need to compute the cost associated to these threshold powers
        # and the corresponding prices intervals.
        #
        # To satisfy all loads without producing anything in the node (leading to a cost of 0 in the node), the
        # following power is the opposite of what must be imported from the neighbour nodes.
        # This is the first point of the power/cost curve.
        min_net_export = - sum(sector.available_powers[timestep] for sector in self._sectors if sector.is_load)
        last_power = min_net_export
        last_cost = 0  # Cost = 0 if full consumption and no production
        last_price = None

        power_cost_points = [(last_power, last_cost)]  # List of threshold power and cost of the power/cost curve
        price_intervals = list()

        for price in threshold_prices_list:
            # For the given market price, compute the production and shedding inside the node to update the
            # net_export of the node.
            # As the price model of the sectors can be a step, a given price may correspond to a range of power.
            # Therefore, we are computing both the minimum and maximum power.
            power_min = min_net_export
            power_max = min_net_export
            for sector in self._sectors:
                if sector.is_load:
                    price_full, price_start = sector.price_model  # (price_no_power, price_full_power)
                    # Full shedding <-> No consumption | Start shedding <-> Full consumption
                else:
                    price_start, price_full = sector.price_model
                if price_start == price == price_full:
                    # power_min += 0 because possible to have no production at this price
                    power_max += sector.available_powers[timestep]
                elif price_start < price:
                    if price >= price_full:
                        factor = 1
                    else:  # price_start < price < price_full
                        factor = (price - price_start) / (price_full - price_start)
                    power = sector.available_powers[timestep] * factor
                    power_min += power
                    power_max += power

            # If increasing the market price led to a higher min_net_export, we add the new threshold point in the list.
            # Else there was no power increase between the previous price and this one, and there is no new threshold
            # point in the cost function
            if power_min > last_power:
                last_cost += (power_min - last_power) * (price + last_price) / 2
                last_power = power_min
                power_cost_points.append((last_power, last_cost))
                price_intervals.append((last_price, price))

            # If the market price correspond to a threshold price of a step model, we have power_max!=power_min and
            # therefore another point to add in the cost function.
            if power_max > power_min:
                assert last_power == power_min
                last_cost += (power_max - power_min) * price
                last_power = power_max
                power_cost_points.append((last_power, last_cost))
                price_intervals.append((price, price))

            last_price = price

        # Using the threshold points of the power/cost curve and the prices interval, computes the cost function on each
        # power interval.
        self._current_cost_function = NodeCostFunction(points_node_scope=power_cost_points, prices=price_intervals)

    def market_optimisation(self, timestep: pd.Timestamp):
        """
        Computes the actual power of generators and loads based on a fixed market price.

        Steps:
        - A/ Identify market price
        - B/ Compute min/max power per sector
        - C/ Compute power per sector to ensure production/consumption adequacy.
        If several solutions with the same cost:
        1/ minimise real loads shedding (maximise consumption for the same system cost)
        2/ minimise storage generators production (avoid emptying reservoir if no associated gain)
        (storage generators considered before storage loads to avoid a storage both producing & consuming)
        3/ minimise storage loads shedding (fill reservoir if no associated cost)
        4/ use real generators production to match the remaining inadequacy
        """
        export = sum([line.get_export(zone=self) for line in self._interconnections])
        self._current_export = export

        # A/ Identify market price
        if self._current_cost_function is None:
            self.update_cost_function(timestep)
        price = self._current_cost_function.compute_price(power=export)

        power_range_per_sector = dict()

        # B/ Compute min/max feasible generation and load shedding at this price
        for sector in self._sectors:
            min_power = 0
            max_power = 0
            if sector.is_load:
                sector_price_full, sector_price_start = sector.price_model  # (price_no_power, price_full_power)
                # Full shedding <-> No consumption | Start shedding <-> Full consumption
            else:
                sector_price_start, sector_price_full = sector.price_model
            sector_name = f"{sector.name}-load" if sector.is_load else sector.name

            if price > sector_price_start:
                if price >= sector_price_full:
                    factor = 1
                else:  # price_start < price < price_full
                    factor = (price - sector_price_start) / (sector_price_full - sector_price_start)
                power = sector.available_powers[timestep] * factor
                min_power = max_power = power
            elif price == sector_price_start == sector_price_full:
                max_power = sector.available_powers[timestep]
            assert sector_name not in power_range_per_sector.keys()
            power_range_per_sector[sector_name] = (min_power, max_power)

        # min/max (production + load_shedding)
        min_offer = sum([power_range[0] for power_range in power_range_per_sector.values()])
        max_offer = sum([power_range[1] for power_range in power_range_per_sector.values()])

        # Objective: production = consumption + export
        # => production + load_shedding = export + total_demand
        # => offer = export + total_demand
        min_net_export = self._current_cost_function.points[0][0]  # - total_demand
        target_power = export - min_net_export
        # => offer = export - min_net_export = target_power
        assert min_offer - TOL <= target_power <= max_offer + TOL
        min_offer = min(min_offer, target_power)
        max_offer = max(max_offer, target_power)

        # C/ Set actual power per sector
        sectors_with_power = list()

        for sector in self._sectors:
            sector_name = f"{sector.name}-load" if sector.is_load else sector.name

            offer_range = power_range_per_sector[sector_name]
            if offer_range[0] == offer_range[1]:
                if not sector.is_load:
                    sector.set_current_power(offer_range[0])
                else:  # load shedding = demand - consumption
                    sector.set_current_power(sector.available_powers[timestep] - offer_range[0])
                sectors_with_power.append(sector_name)

        # Share loads & generators between real ones & storage ones
        real_load_names = list()
        real_gen_names = list()
        storage_load_names = list()
        storage_gen_names = list()
        for storage in self._storages:
            storage_gen_names.append(storage.generator.name)
            storage_load_names.append(f"{storage.load.name}-load")
        for sector in self._sectors:
            if sector.is_load:
                sector_name = f"{sector.name}-load"
                if sector_name not in storage_load_names:
                    real_load_names.append(sector_name)
            else:
                if sector.name not in storage_gen_names:
                    real_gen_names.append(sector.name)

        for sector_list in (real_load_names, storage_gen_names, storage_load_names, real_gen_names):
            for sector_name in sector_list:
                if sector_name not in sectors_with_power:
                    sector = next(iter(sector for sector in self.sectors
                                       if (f"{sector.name}-load" if sector.is_load else sector.name) == sector_name))
                    offer_range = power_range_per_sector[sector_name]
                    assert max_offer >= target_power
                    margin = max_offer - target_power  # >= 0
                    offer = max(offer_range[0], offer_range[1] - margin)  # as close as possible to offer_range[0]
                    if sector.is_load:  # offer is shedding
                        actual_power = sector.available_powers[timestep] - offer  # consumption
                    else:
                        actual_power = offer  # production
                    sector.set_current_power(power=actual_power)
                    min_offer += offer - offer_range[0]  # increase
                    max_offer += offer - offer_range[1]  # decrease
                    sectors_with_power.append(sector_name)
        assert_approx(min_offer, target_power)
        assert_approx(max_offer, target_power)

    def reset_powers(self):
        """
        Reset the available powers of the :class:`.Sector` in the node and its current export.
        """
        self._current_export = 0
        self._current_cost_function = None
