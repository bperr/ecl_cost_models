"""
    Import of the library panda used to open the database
"""
import pandas as pd

"""
    Import of other programs used in the main
"""
import load_database
import load_hypothesis
import market_price
import comparison
import optimisation
import scenario_generator

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------

class Sector :
    
    """
        Sector of production of electricity
        
        Attributes : production, date of production and the price
        
        Methods : 3 methods to get thoses three attributes for a specific sector
        
    """
    
    def __init__(self,production,production_date,price):
        self.production=production
        self.production_date=production_date
        self.price=price
        
    def get_production_value(self):
        return self.production
    
    def get_production_date(self):
        return self.production_date
    
    def get_price(self):
        return self.price
    
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------

class Country:
    
    """
        Country in the E.U.
        
        Attributes : sectors (a list of sector)
        
        Methods : Addring a new sector to the existing list
    """
    
    def __init__(self,type,sectors):
        self.sectors=sectors
        
    def add_sector(self,sector):
        self.sectors.append(sector)

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------

class Interco:
    
    """
        Value of the flow transiting between two countries
        
        Attributes : country where it's sold and country where it's bought,
        transiting flow and the associated time
    
        Methods : 4 methods in order to get these attributes
    """
    
    def __init__(self,from_country,to_country,flow,time):
        self.from_country=from_country
        self.to_country=to_country
        self.flow=flow
        self.time=time
        
    def get_from_country(self):
        return self.from_country
    
    def get_tp_country(self):
        return self.to_country
    
    def get_capacity(self):
        return self.flow
    
    def get_time(self):
        return self.time

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
        
class Interco_max:
    
    """
        Max value of the flow between two countries
        
        Attributes : country where it's sold and country where it's bought and
        the maximum flow value 
    
        Methods : 3 methods to get both countries and the maximum flow
    """
    
    def __init__(self,from_country,to_country,capacity):
        self.from_country=from_country
        self.to_country=to_country
        self.capacity=capacity
        
    def get_from_country(self):
        return self.from_country
    
    def get_tp_country(self):
        return self.to_country
    
    def get_capacity(self):
        return self.capacity_max
        
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
        
class Price:

    """
        Spot price for a specific area
        
        Attributes : price and economic area for a specific date
        
        Method : extraction of the price for a specific area at a specific date
    """
    
    def __init__(self,price_date,economic_area):
        self.price_date=price_date
        self.economic_area=economic_area
    
    def get_Spot_price(self):
        return load_database.prod_users[self.price_date][self.economic_area]
        

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------

        
if __name__ == "__main__":
    pass