import pandas as pd

from src.opf_utils import TOL
from src.sector import Sector


class Storage:
    """
        Represents an energy storage system composed of two separate sectors having the same name:
        one acting as a load (charging) and the other as a generator (discharging).
    """

    def __init__(self, sector_name: str, historical_powers: pd.Series, is_controllable: bool, opf_mode: bool,
                 energy_rating: float, mean_inflow: float, production_efficiency=1., consumption_efficiency=1.):
        """
        Initializes the Storage instance by splitting historical power data into load (negative powers) and
        generator sectors (positive powers).

        :param sector_name: Name of the sectors associated with this storage
        :param historical_powers: Time series of historical power values (can be positive or negative)
        :param is_controllable: Indicates whether the storage system is controllable
        :param energy_rating: Energy rating (in MW) of the storage. Used to run OPF but not to build price models.
        :param production_efficiency: Between 0 & 1 (Electrical production / Stored energy decrease)
        :param consumption_efficiency: Between 0 & 1 (Stored energy increase / Electrical consumption)
        """
        self._energy_rating = energy_rating
        self._mean_inflow = mean_inflow
        self._production_efficiency = production_efficiency
        self._consumption_efficiency = consumption_efficiency
        self._stored_energy: float = energy_rating / 2  #: energy at the beginning of the hour
        self._next_energy: float | None = None  #: energy at the end of the hour
        self.time_step_to_hour = {time_step: i for i, time_step in enumerate(historical_powers.index)}
        self._current_hour = 0
        self._n_hours = len(historical_powers)
        self._constrained_production = 0  # MW, < 0 if constrained consumption

        if opf_mode:
            # In OPF mode, all timestamp are kept.
            # They are replaced by zero when the storage behaves in the opposite operating mode.
            powers_load = historical_powers.apply(lambda power: min(0, power))
            powers_generator = historical_powers.apply(lambda power: max(0, power))
        else:
            # In price model mode, timestamp are split between load and generator
            powers_load = historical_powers[historical_powers <= 0]
            powers_generator = historical_powers[historical_powers >= 0]

        self._load = Sector(sector_name, powers_load, is_controllable=is_controllable, is_load=True)
        self._generator = Sector(sector_name, powers_generator, is_controllable=is_controllable)

        if opf_mode:
            self._energy_constraints = self._build_energy_constraints()
        else:
            self._energy_constraints = list()

    @property
    def load(self):
        return self._load

    @property
    def generator(self):
        return self._generator

    def _build_energy_constraints(self):
        """
        Compute time series of min/max energy requirements to ensure no stored energy change between start and end of
        the simulation (initial energy = final energy).

        Returns
        -------
        List of (min energy, max energy) to be respected by the stored energy
        """
        # assert len(self._energy_constraints) == 0
        consumption_rating_mw = self._load.power_rating  # >= 0
        production_rating_mw = self._generator.power_rating
        last_energy = self._energy_rating / 2  # = initial energy
        energy_constraints = list()
        for i in range(self._n_hours):
            next_hours = self._n_hours - i - 1
            # Compute possible storing next hours
            future_inflow = self._mean_inflow * next_hours
            max_storing = consumption_rating_mw * self._consumption_efficiency * next_hours
            max_unstoring = production_rating_mw / self._production_efficiency * next_hours
            max_future_reasonable_storing = future_inflow + max_storing / 2  # max_storing/2 to keep margin
            min_future_reasonable_storing = future_inflow - max_unstoring / 2

            min_energy = max(0., last_energy - max_future_reasonable_storing)
            max_energy = min(self._energy_rating, last_energy - min_future_reasonable_storing)

            energy_constraints.append((min_energy, max_energy))
        return energy_constraints

    @property
    def constrained_production(self) -> float:
        """
        Returns production (consumption if < 0) required to ensure min/max stored energy next hour
        """
        return self._constrained_production

    def update_availabilities(self, time_step: pd.Timestamp):
        """
        Update the available power of the storage load and generator and the storage constrained production based on
        its energy level and constraints.

        Parameters
        ----------
        time_step: Must be coherent with self._current_hour
        """
        assert self._current_hour == self.time_step_to_hour[time_step]  # int

        (min_expected_energy, max_expected_energy) = self._energy_constraints[self._current_hour]

        # Allowed net production to keep min_expected_energy <= stored energy <= max_expected_energy
        allowed_production = min(
            self.generator.power_rating,
            (self._stored_energy + self._mean_inflow - min_expected_energy) * self._production_efficiency)
        allowed_consumption = min(
            self.load.power_rating,
            (max_expected_energy - (self._stored_energy + self._mean_inflow)) / self._consumption_efficiency)

        # Constrained net production to keep min_expected_energy <= stored energy <= max_expected_energy
        if self._stored_energy + self._mean_inflow > max_expected_energy + TOL:
            # Storage too full: need to produce (no consumption)
            self._constrained_production = min(
                self.generator.power_rating,
                (self._stored_energy + self._mean_inflow - max_expected_energy) * self._production_efficiency)  # > 0
            self.generator.set_available_power(power=allowed_production - self._constrained_production)
            self.load.set_available_power(power=0)
        elif self._stored_energy + self._mean_inflow < min_expected_energy - TOL:
            # Storage too empty: need to consume (no production)
            self._constrained_production = - min(self.load.power_rating,
                                                 (min_expected_energy - self._stored_energy - self._mean_inflow)
                                                 / self._consumption_efficiency)  # < 0
            self.generator.set_available_power(power=0)
            self.load.set_available_power(power=allowed_consumption + self._constrained_production)
        else:
            # Possible to consume or to produce
            self._constrained_production = 0
            self.generator.set_available_power(power=allowed_production)
            self.load.set_available_power(power=allowed_consumption)

    def _compute_new_energy(self):
        """
        Computes stored energy at current hour + 59 mn
        """
        assert self._next_energy is None
        (min_expected_energy, max_expected_energy) = self._energy_constraints[self._current_hour]

        net_production = self._constrained_production + self.generator.current_power - self.load.current_power
        if net_production >= 0:
            new_energy = self._stored_energy + self._mean_inflow - net_production / self._production_efficiency
        else:
            new_energy = self._stored_energy + self._mean_inflow - net_production * self._consumption_efficiency
        assert (min_expected_energy - TOL <= new_energy <= max_expected_energy + TOL)
        assert -TOL <= new_energy <= self._energy_rating + TOL
        self._next_energy = min(new_energy, self._energy_rating)

    def update_energy(self):
        """
        Update current hour and stored energy (as 1 hour has passed)
        """
        if self._next_energy is None:
            self._compute_new_energy()
        self._stored_energy = self._next_energy
        self._next_energy = None
        self._current_hour += 1
