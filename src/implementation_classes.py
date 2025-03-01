import pandas as pd

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
class Sector :  #Definition of the class Sector, that gives the information of each sector of production (gas, nuclear, wind offshore,...)
    
    def __init__(self,production: int,production_date: str,price: float): #production gives the value in MW; production_date gives the corresponding day and hour of the day; and price gives the marginal cost of production for a given sector of production
        self._production=production     #private attribute, as defined in the UML
        self._production_date=production_date   #private attribute, as defined in the UML
        self._price=price   #private attribute, as defined in the UML
        
    def get_production_value(self):
        return self._production     #gives the production value in MW
    
    def get_production_date(self):
        return self._production_date    #gives the production date in format dd/mm/yyyy hh:mm
    
    def get_price(self):
        return self._price  #gives the marginal cost of the sector for the given production in €/MWh


    
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------

class Country:  #Definition of the class Country, with a list of the countries studied and their sectors of production
    
    def __init__(self,type,sectors: list):  #Sectors is the list of production sectors used in the country
        self._sectors=sectors   #create the list of sectors
        
    def add_sector(self,sector: str):    #add the sectors to the list for a given country
        self._sectors.append(sector)    

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------

class Interco:  #Definition of the class Interco, that defines the interconnexion between two countries and the production exchanged
    
    def __init__(self,from_country: str,to_country: str,production_transfered: int, transfer_date: str, is_max: bool):
        self._from_country=from_country     #country that sends the production to the other
        self._to_country=to_country     #country that receives the production from the other
        self._production_transfered=production_transfered    #production transfered between two countries at a given time in MW
        self._transfer_date=transfer_date   #date at which the transfer has occured, at the format dd/mm/yyyy hh:mm
        self._is_max=is_max     #A boolean that gives if the inteconnexion is satured or not
        
    def get_from_country(self):     #get the name of the country that sends the production
        return self._from_country
    
    def get_to_country(self):   #get the name of the country that receives the production
        return self._to_country
    
    def get_production_transfered(self):     #get the production that was effectively sent from a country to another in MW
        return self._capacity
    
    def get_transfer_date(self):    #get the date at which the transfer has occured, at the format dd/mm/yyyy hh:mm
        return self._transfer_date
    
    def get_is_max(self):   #Get the parameter is_max, that tells us if the interconnexion is satured or not
        return self._is_max


#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
        
class Price:    #definition of the class Price, that gives the Spot price of electricity for a given country and at a given time of the year
    
    def __init__(self,price_date: str,economic_area: str, price: float):
        self._price_date=price_date     #date at which the price is calculated, in format dd/mm/yyyy hh:mm
        self._economic_area=economic_area   #corresponding economic area
        self._price=price   #Sport price in €/MWh
        
    def get_spot_price(self):
        return self._price  #gives the Spot price
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------

class Storage: #In pause for instance, because of the issue with the time step
    
    def __init__(self,country: str,capacity_date: str,flow: int):
        self._country=country   #country in which the capacity is mesured
        self._capacity_date=capacity_date   #week of the year at which the capacity is mesured
        self._flow=flow     #value of the flow in MWh
        
        
    def get_storage_country(self):  #gives the country in which the capacity is mesured
        return self._country
    
    def get_storage_capacity_date(self):   #gives the week of the year at which the capacity is mesured
        return self._capacity_date
    
    def get_storage_flow(self):     #gives the value of the flow in MWh
        return self._flow
    
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------

    