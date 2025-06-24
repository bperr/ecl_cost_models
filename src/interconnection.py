class Interconnection:
    """
        Represents an electrical interconnection between two countries.

        This class models an interconnection from a source zone (`zone_from`)
        to a destination zone (`zone_to`) with a maximum power capacity (`power_rating`).
        It stores incoming and outgoing power values at different time steps.

        Attributes:
            _zone_from (str): The source zone of the interconnection.
            _zone_to (str): The destination zone of the interconnection.
            _power_rating (float): The maximum power capacity of the interconnection (in MW).
            _powers_in (pd Series): stores incoming power values by time step.
            _powers_out (pd Series): stores outgoing power values by time step.
    """
    def __init__(self, zone_from: str, zone_to: str, power_rating: float):
        self._zone_from = zone_from
        self._zone_to = zone_to
        self._power_rating = power_rating
        self._powers_in = dict()
        self._powers_out = dict()
