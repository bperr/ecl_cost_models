class Interconnection:
    """
        Represents an electrical interconnection between two countries.

        This class models an interconnection from a source country (`country_from`)
        to a destination country (`country_to`) with a maximum power capacity (`power_rating`).
        It stores incoming and outgoing power values at different time steps.

        Attributes:
            _country_from (str): The source country of the interconnection.
            _country_to (str): The destination country of the interconnection.
            _power_rating (float): The maximum power capacity of the interconnection (in MW).
            _powers_in (pd Series): stores incoming power values by time step.
            _powers_out (pd Series): stores outgoing power values by time step.
    """
    def __init__(self, country_from: str, country_to: str, power_rating: float):
        self._country_from = country_from
        self._country_to = country_to
        self._power_rating = power_rating
        self._powers_in = dict()
        self._powers_out = dict()
