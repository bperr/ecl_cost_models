class Sector:
    """
    Class that gives the information of each sector of production (gas, nuclear, wind offshore,...)
    """

    def __init__(self, production: int, production_date: str, price: float):
        """
        :param production: current production capacity in MW
        :param production_date: corresponding day and hour in format dd/mm/yyyy hh:mm
        :param price: marginal cost of production in €/MWh
        """
        self._production = production  # in MW
        self._production_date = production_date
        self._price = price  # €/MWh

    def get_production_value(self):
        """
        :return: Gives the production value in MW
        """
        return self._production

    def get_production_date(self):
        """
        :return: Gives the production date in format dd/mm/yyyy hh:mm
        """
        return self._production_date

    def get_price(self):
        """
        :return: Gives the marginal cost of the sector for the given production in €/MWh
        """
        return self._price


class Country:
    """
    Class with a list of the countries studied and their sectors of production
    """

    def __init__(self, type, sectors: list):
        """
        :param type: TO FILL
        :param sectors: List of production sectors used in the country
        """
        self._sectors = sectors

    def add_sector(self, sector: str):
        """
        Add a sector to the list of country sectors.
        :param sector: Sector to add to the country.
        """
        self._sectors.append(sector)


class Interco:
    """
    Class that defines the interconnection between two countries and the production exchanged
    """

    def __init__(self, from_country: str, to_country: str, production_transferred: int, transfer_date: str,
                 is_max: bool):
        """
        :param from_country: country that sends the production to the other
        :param to_country: country that receives the production from the other
        :param production_transferred: production transferred between two countries at a given time in MW
        :param transfer_date: date at which the transfer has occurred, in format dd/mm/yyyy hh:mm
        :param is_max: A boolean that gives if the inteconnexion is saturated or not
        """
        self._from_country = from_country
        self._to_country = to_country
        self._production_transferred = production_transferred  # in MW
        self._transfer_date = transfer_date  # in format dd/mm/yyyy hh:mm
        self._is_max = is_max

    def get_from_country(self):
        """
        :return: The name of the country that sends the production
        """
        return self._from_country

    def get_to_country(self):
        """
        :return: The name of the country that receives the production
        """
        return self._to_country

    def get_production_transferred(self):
        """
        :return: The production that was effectively sent from a country to another in MW
        """
        return self._capacity

    def get_transfer_date(self):
        """
        :return: The date at which the transfer has occurred, at the format dd/mm/yyyy hh:mm
        """
        return self._transfer_date

    def get_is_max(self):
        """
        :return: Whether the interconnection is saturated or not
        """
        return self._is_max


class Price:
    """
    Class that gives the Spot price of electricity for a given country and at a given time of the year
    """

    def __init__(self, price_date: str, economic_area: str, price: float):
        """
        :param price_date: date at which the price is calculated, in format dd/mm/yyyy hh:mm
        :param economic_area: corresponding economic area
        :param price: Spot price in €/MWh
        """
        self._price_date = price_date
        self._economic_area = economic_area
        self._price = price  # €/MWh

    def get_spot_price(self):
        """
        :return: The Spot price
        """
        return self._price


class Storage:  # In pause for instance, because of the issue with the time step
    """
    TO FILL
    """

    def __init__(self, country: str, capacity_date: str, flow: int):
        """
        :param country: country in which the capacity is measured
        :param capacity_date: week of the year at which the capacity is measured
        :param flow: value of the flow in MWh
        """
        self._country = country
        self._capacity_date = capacity_date
        self._flow = flow  # MWh

    def get_storage_country(self):
        """
        :return: The country in which the capacity is measured
        """
        return self._country

    def get_storage_capacity_date(self):
        """
        :return: The week of the year at which the capacity is measured
        """
        return self._capacity_date

    def get_storage_flow(self):
        """
        :return: The value of the flow in MWh
        """
        return self._flow
