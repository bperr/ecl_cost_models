import pandas as pd

import load_database
import load_hypothesis
import market_price
import comparison
import optimisation
import scenario_generator

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
class Sector:
    def __init__(self, production, production_date, price): 
        self.production = production
        self.production_date = production_date
        self.price = price

    def get_production(self): 
        return load_database.df_production_value[self.production]

    def get_production_date(self):
        return load_database.df_production_date[self.production_date]
    
    def get_production_price(self):
        return load_database.file_hypothesis[self.price]

    
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------

class Country:
    
    def __init__(self,type,sectors):
        self.sectors=sectors
        
    def add_sector(self,sector):
        self.sectors.append(sector)

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------

class Interco:
    
    def __init__(self,from_country,to_country,capacity_max):
        self.from_country=from_country
        self.to_country=to_country
        self.capacity_max=capacity_max
        
    def get_from_country(self):
        return self.from_country
    
    def get_tp_country(self):
        return self.to_country
    
    def get_capacity(self):
        return self.capacity_max

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
        
class Interco_max:
    
    def __init__(self,from_country,to_country,capacity_max):
        self.from_country=from_country
        self.to_country=to_country
        self.capacity_max=capacity_max
        
    def get_from_country(self):
        return self.from_country
    
    def get_tp_country(self):
        return self.to_country
    
    def get_capacity(self):
        return self.capacity_max
        
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
        
class Price: #Tristan
    
    def __init__(self,price_date,economic_area):
        self.price_date=price_date
        self.economic_area=economic_area
        
    def get_Spot_price(self):
        return load_database.prod_users[self.price_date][self.economic_area]
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------

class Storage: #Gaspard 
    
    def __init__(self,country,capacity_date,flow):
        self.country=country
        self.capacity_date=capacity_date
        self.flow=flow
        
        
    def get_storage_country(self):
        return self.country
    
    def get_storage_capacity_date(self):
        return self.capacity_date
    
    def get_storage_flow(self):
        return self.flow
    
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------

        
if __name__ == "__main__":
    