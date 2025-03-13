# -*- coding: utf-8 -*-
"""
Created on Fri Mar  7 13:55:19 2025

@author: trist
"""

from pathlib import Path
from datetime import datetime, timedelta
from load_database import load_database_prod_user
from load_database import load_database_price_user

import pandas as pd



# Function adding the missing dates of the database
def add_missing_dates_prod(production: dict, countries_list: list[str], start_year: int, end_year: int):
    
    #Define the date range
    start_date = pd.Timestamp(str(start_year)+'-01-01 00:00:00')
    end_date = pd.Timestamp(str(end_year)+'-12-31 23:00:00')
    
    
    for country in countries_list: #Loop over all countries
        
        power_plant_list = list(production[country]) #List of the power plant existing in the country
        first_power_plant = power_plant_list[0]
        current_date = start_date
    
        # Loop over all the dates in the specified range
        while current_date <= end_date:
            
            if current_date not in production[country][first_power_plant]: #Check if the date is missing in the database
                
                if current_date == start_date or current_date == end_date : #Averaging the previous and the next values is not possible for limit values
                
                    for power_plant in power_plant_list: #If a date is missing for the first power plant, it is also missing for the others
                         production[country][power_plant][current_date] = 0
                
                else:
                    
                    next_date = current_date + pd.Timedelta(hours=1)
                    previous_date = current_date - pd.Timedelta(hours=1)
                    
                    if next_date in production[country][first_power_plant]:  #Check if creating a power value by averaging the previous and the next values is possible
                        
                        for power_plant in power_plant_list:
                            production[country][power_plant][current_date] = (production[country][power_plant][previous_date] + production[country][power_plant][next_date])/2
                    else:
                        # If the next power value is missing, the previous power value is copied
                        for power_plant in power_plant_list:
                            production[country][power_plant][current_date] = production[country][power_plant][previous_date]
                        
            current_date += pd.Timedelta(hours=1)  # Iteration process
            
    
def add_missing_dates_price(price: dict, countries_list: list[str], start_year: int, end_year: int):
    
    #Define the date range
    start_date = pd.Timestamp(str(start_year)+'-01-01 00:00:00')
    end_date = pd.Timestamp(str(end_year)+'-12-31 23:00:00')
    
    first_country = countries_list[0]
    current_date = start_date
    
    # Loop over all the dates in the specified range
    while current_date <= end_date:
        
        if current_date not in price[first_country]: #Check if the date is missing in the database
        
            if current_date == start_date or current_date == end_date : #Averaging the previous and the next values is not possible for limit values
                for country in countries_list: #If a date is missing for the first country, it is also missing for the others
                    price[country][current_date] = 0
                    
            else: 
                next_date = current_date + pd.Timedelta(hours=1)
                previous_date = current_date - pd.Timedelta(hours=1)
            
                if next_date in price[first_country]:  #Check if creating a price value by averaging the previous and the next values is possible
                
                    for country in countries_list:
                        price[country][current_date] = (price[country][previous_date] + price[country][next_date])/2
                else:
                    # If the next price value is missing, the previous price value is copied
                    for country in countries_list:
                        price[country][current_date] = price[country][previous_date]
            
        current_date += pd.Timedelta(hours=1)  # Iteration process
        

            
# Utilization example
if __name__ == "__main__":
    
    # db_path = Path(__file__).parents[1] / "instance" / "database"
    db_path = Path(r"C:\Users\trist\OneDrive\Documents\ECL3A\Option énergie\Projet d'option\Code\database")
    folder_path_prod = db_path / "Production par pays et par filière 2015-2019"
    folder_path_price = db_path / "Prix spot par an et par zone 2015-2019"
    countries = ['AT', 'BE', 'CH']
    #'AT', 'BE', 'CH', 'CZ', 'DE', 'DK', 'EE', 'ES', 'FI', 'FR','GB', 'GR', 'HU', 'IT', 'LT', 'NL', 'NO', 'PL', 'PT', 'RO','SE', 'SI', 'SK'
    start_year, end_year = 2015, 2015  # years of production database

    prod_users = load_database_prod_user(folder_path_prod, countries, start_year, end_year)
    price_users = load_database_price_user(folder_path_price, countries, start_year, end_year)
    
    add_missing_dates_prod(prod_users, countries, start_year, end_year)
    add_missing_dates_price(price_users, countries, start_year, end_year)
    
    
    
    
    