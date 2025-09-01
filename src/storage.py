from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import warnings

import pandas as pd

from src.opf_utils import TOL, bounded_value
from src.sector import Sector


class Storage:
    """
        Represents an energy storage system composed of two separate sectors having the same name:
        one acting as a load (charging) and the other as a generator (discharging).
    """

    def __init__(self, sector_name: str, historical_powers: pd.Series, is_controllable: bool, opf_mode: bool,
                 production_efficiency=1., consumption_efficiency=1.):
        """
        Initializes the Storage instance by splitting historical power data into load (negative powers) and
        generator sectors (positive powers).

        :param sector_name: Name of the sectors associated with this storage
        :param historical_powers: Time series of historical power values (can be positive or negative)
        :param is_controllable: Indicates whether the storage system is controllable
        :param production_efficiency: Between 0 & 1 (Electrical production / Stored energy decrease)
        :param consumption_efficiency: Between 0 & 1 (Stored energy increase / Electrical consumption)
        """
        self._name = sector_name
        self._production_efficiency = production_efficiency
        self._consumption_efficiency = consumption_efficiency

        # Updated in build_energy_constraints
        self._energy_rating: float | None = None
        self._mean_inflow: float | None = None
        self._energy_constraints = pd.DataFrame()

        # Updated each hour
        self._timestep: pd.Timestamp | None = None
        self._constrained_production = 0  # MW, < 0 if constrained consumption
        self._stored_energy: float | None = None
        self._next_energy: float | None = None  #: energy at the end of the hour

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
        self._name = sector_name

    @property
    def name(self):
        return self._name

    @property
    def load(self):
        return self._load

    @property
    def generator(self):
        return self._generator

    def build_energy_constraints(self, datetime_index: list[pd.Timestamp], energy_rating: float, mean_inflow: float,
                                 reasonable_forced_power_factor: float = 0.5):
        """
        Compute time series of min/max energy requirements to ensure no stored energy change between start and end of
        the simulation (initial energy = final energy).

        Parameters
        ----------
        datetime_index: Time steps for which an OPF will be run
        energy_rating: Energy rating of the storage. Stored energy is initialised at half of it.
        mean_inflow: Constant natural charging
        reasonable_forced_power_factor: The final stored energy must be equal to the initial one. At the end of the
                                        simulation the storage is forced to consume (or produce) if its stored power is
                                        too low (or high). This ratio (between 0 and 1) is a maximum for
                                        constrained power / power rating.

        Returns
        -------
        List of (min energy, max energy) to be respected by the stored energy
        """
        self._energy_rating = energy_rating
        consumption_rating_mw = self._load.power_rating  # >= 0
        production_rating_mw = self._generator.power_rating
        charging_rating = consumption_rating_mw * self._consumption_efficiency
        discharging_rating = production_rating_mw / self._production_efficiency

        if mean_inflow > discharging_rating:
            warnings.warn(f"Storage {self._name}: mean inflow set to {discharging_rating} instead of {mean_inflow} to "
                          f"be compatible with discharging rating")
            mean_inflow = discharging_rating
        self._mean_inflow = mean_inflow

        self._stored_energy = energy_rating / 2  # = initial energy
        last_energy = self._stored_energy  # Consistency between initial energy and final energy
        energy_constraints = list()
        n_hours = len(datetime_index)
        for i in range(n_hours):
            next_hours = n_hours - i - 1
            future_inflow = self._mean_inflow * next_hours
            max_reasonable_charging = charging_rating * next_hours * reasonable_forced_power_factor
            max_reasonable_discharging = discharging_rating * next_hours * reasonable_forced_power_factor
            min_energy = bounded_value(value=last_energy - future_inflow - max_reasonable_charging,
                                       min_value=0, max_value=last_energy)
            max_energy = bounded_value(value=last_energy - future_inflow + max_reasonable_discharging,
                                       min_value=last_energy, max_value=self._energy_rating)
            energy_constraints.append((min_energy, max_energy))
        self._energy_constraints = pd.DataFrame(energy_constraints, columns=["Min", "Max"], index=datetime_index)

    @property
    def constrained_production(self) -> float:
        """
        Returns production (consumption if < 0) required to ensure min/max stored energy next hour
        """
        return self._constrained_production

    def update_availabilities(self, timestep: pd.Timestamp):
        """
        Update the available power of the storage load and generator and the storage constrained production based on
        its energy level and constraints.

        Parameters
        ----------
        timestep: The current timestep (used to identify energy constraints)
        """
        self._timestep = timestep
        min_expected_energy, max_expected_energy = self._energy_constraints.loc[timestep]

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
        min_expected_energy, max_expected_energy = self._energy_constraints.loc[self._timestep]

        net_production = self._constrained_production + self.generator.current_power - self.load.current_power
        if net_production >= 0:
            new_energy = self._stored_energy + self._mean_inflow - net_production / self._production_efficiency
        else:
            new_energy = self._stored_energy + self._mean_inflow - net_production * self._consumption_efficiency
        error_info = (f"Stored energy: {self._stored_energy}. Mean inflow: {self._mean_inflow}. "
                      f"Net production: {net_production}")
        if not (min_expected_energy - TOL <= new_energy <= max_expected_energy + TOL):
            raise ValueError(f"{min_expected_energy} <= {new_energy} <= {max_expected_energy}\n{error_info}")
        if not (-TOL <= new_energy <= self._energy_rating + TOL):
            raise ValueError(f"0 <= {new_energy} <= {self._energy_rating}\n{error_info}")
        self._next_energy = min(new_energy, self._energy_rating)

    def update_energy(self):
        """
        Update current hour and stored energy (as 1 hour has passed)
        """
        if self._next_energy is None:
            self._compute_new_energy()
        self._stored_energy = self._next_energy
        self._next_energy = None

    def compare_power_series(self, zone_name: str, path: Path):
        historical_powers = self._load.historical_powers + self._generator.historical_powers
        simulated_powers = self._load.simulated_powers + self._generator.simulated_powers

        simulated_energy = simulated_powers.sum()
        historical_energy = historical_powers.sum()

        power_error_series = historical_powers - simulated_powers  # MW
        energy_error = historical_energy - simulated_energy  # MWh

        # Relative Energy error - difference of simulated & historical energy (sum of powers) - (value - MWh)
        relative_total_energy_difference = energy_error / abs(historical_energy) if historical_energy != 0 else (
            0 if simulated_energy == 0 else np.nan)
        # Relative Energy of the power error - energy (sum) of differences of powers - (value - MWh)
        cumulative_relative_energy_error = abs(power_error_series).sum() / abs(historical_energy) if (
                historical_energy != 0) else (0 if (power_error_series == 0).all() else np.nan)

        # Mean absolute error of powers - (value - MW)
        power_MAE = np.mean(abs(power_error_series))
        # Relative error of powers - (time series - MW)
        relative_power_error_series = (
            pd.Series(0, index=historical_powers.index)
            if (historical_powers == 0).all() and (simulated_powers == 0).all()
            else (abs(power_error_series) / abs(historical_powers).replace(0, np.nan)).dropna()
        )

        # Maximum and mean relative error of powers (value - MW)
        max_relative_power_error = relative_power_error_series.max()
        mean_relative_power_error = relative_power_error_series.mean()

        sectors_errors_data = {
            "zone": zone_name,
            "sector": self.name,
            "load": "Storage",
            "relative_total_energy_error": round(float(relative_total_energy_difference), 3),
            "cumulative_relative_energy_error": round(float(cumulative_relative_energy_error), 3),
            "max_relative_power_error": round(float(max_relative_power_error), 3),
            "mean_relative_power_error": round(float(mean_relative_power_error), 3),
            "mean_absolute_error_MW": round(float(power_MAE), 3),
        }

        self.plot_power_errors(zone_name, sectors_errors_data, simulated_powers, historical_powers, path)
        return sectors_errors_data

    def plot_power_errors(self, zone_name: str, sector_errors_data: dict, simulated_powers: pd.Series(),
                          historical_powers: pd.Series, path: Path):
        """
        Plot and save a comparison graph of simulated vs historical powers for the sector

        Parameters
        ----------
        zone_name:str: Name of the zone being analyzed

        path:Path: Directory path where the generated comparison plot is saved

        sector_errors_data : Dictionary containing error metrics for the sector
        """

        max_relative_power_error = sector_errors_data["max_relative_power_error"]
        mean_relative_power_error = sector_errors_data["mean_relative_power_error"]
        relative_total_energy_error = sector_errors_data["relative_total_energy_error"]
        cumulative_relative_energy_error = sector_errors_data["cumulative_relative_energy_error"]

        plt.figure(figsize=(10, 6))
        historical_powers.plot(label='Historical', linewidth=0.5, drawstyle='steps-post')
        simulated_powers.plot(label='Simulation', linewidth=0.5, linestyle='--', drawstyle='steps-post')
        plt.axhline(0, color='red', linestyle='-', linewidth=1.5, alpha=0.7)

        plt.legend()
        plt.title(f"{zone_name} - {self._name}")
        plt.xlabel("Timestep")
        plt.ylabel("Power (MW)")

        if historical_powers.min() > 0 and simulated_powers.min() > 0:
            plt.ylim(bottom=0)

        error_text = (f"Max error : {max_relative_power_error:.2%}\n"
                      f"Mean error : {mean_relative_power_error:.2%}\n"
                      f"Cumulative energy error : {cumulative_relative_energy_error:.2%}\n"
                      f"Total energy error : {relative_total_energy_error:.2%}")
        plt.text(0.05, 0.95, error_text, transform=plt.gca().transAxes,
                 fontsize=10, verticalalignment='top', bbox=dict(facecolor='white', alpha=0.6))

        # Saving
        file_name = f"{zone_name}_{self._name}_storage_comparison.png".replace(" ", "_")
        file_path = path / f"{file_name}"
        plt.tight_layout()
        plt.savefig(file_path, dpi=600)
        plt.close()
