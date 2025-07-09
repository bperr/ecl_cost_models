import pandas as pd


class Interconnection:
    """
    Represents an electrical interconnection between two countries.

    This class models an interconnection from a source zone (`zone_from`)
    to a destination zone (`zone_to`) with a maximum power capacity (`power_rating`).
    It stores incoming and outgoing power values at different time steps.

    Attributes:
        _zone_from (Zone): The source zone of the interconnection.
        _zone_to (Zone): The destination zone of the interconnection.
        _power_rating (float): The maximum power capacity of the interconnection (in MW).
        _historical_powers (pd Series): stores incoming power values (in MW) by time step.
        _simulated_powers (pd Series): stores outgoing power values (in MW) by time step.
    """

    def __init__(self, zone_from, zone_to, power_rating: float, historical_power_flows: pd.Series):
        self._zone_from = zone_from  # Zone object
        self._zone_to = zone_to  # Zone_object
        self._power_rating = power_rating  # MW
        self._historical_powers = historical_power_flows  # MW
        self._current_power = 0
        self._simulated_powers = pd.Series()  # MW

    @property
    def zone_from(self):
        return self._zone_from

    @property
    def zone_to(self):
        return self._zone_to

    def optimize_export(self, timestep: pd.Timestamp) -> float:
        """
        To be updated by Nicolas
        :param timestep:
        :return:
        """
        # from_cost_function = self._zone_from.cost_function(timestep)
        # to_cost_function = self._zone_to.cost_function(timestep)

    def store_simulated_power(self, timestep: pd.Timestamp):
        """
        Updates the simulated powers series (transferred in the connection) by storing the current power stored in
        self._current_power and calculated during the OPF at the specified timestep and then resets the current
        power to zero (so that the next timesteps data can be saved)

        :param timestep: The timestep at which the current power should be recorded
        """
        self._simulated_powers[timestep] = self._current_power
        self._current_power = 0
