# -*- coding: utf-8 -*-
"""
Created on Fri Feb 14 08:27:09 2025

@author: cgoas
"""

import pandas as pd
import os
from pathlib import Path

def load_database_prod_user(folder_path, country_list, start_year, end_year):
    
    # Dictionnaire pour stocker les données
    data_dict_prod_user = {}
    
    # Liste des fichiers avec leur chemin complet
    file_paths = [os.path.join(folder_path, file) for file in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, file))]
    
    # Création du DataFrame
    folder_path_df = pd.DataFrame(file_paths, columns=["File Path"])
    

    for file_path in folder_path_df :
        
        file_path = folder_path_df.loc[0, "File Path"]  # Récupère la première valeur de la colonne
        file_name = os.path.splitext(os.path.basename(file_path))[0]
        df = pd.read_excel(file_path, sheet_name=file_name, header=0)
               
        df = df[ (df["Début de l'heure"].dt.year >= start_year) & (df["Début de l'heure"].dt.year <= end_year)]
        
        # Définir la première colonne comme index (time)
        df.set_index(df.columns[0], inplace=True)
        df.index.name = "Time"  # Renommer l'index pour la lisibilité
        
        for country in countries_list : 
    
            # Initialiser l'entrée pour le country
            data_dict_prod_user[country] = {}
    
            # Restructurer les données sous la forme souhaitée
            for prod_mode in df[df.columns[1:]]:  # Parcours des modes de production
                data_dict_prod_user[country][prod_mode] = df[prod_mode].to_dict()
        

    return data_dict_prod_user



def load_database_price_user(folder_path, country_list, start_year, end_year):
    
    # Dictionnaire pour stocker les données
    data_dict_price_user = {}
    
    # Liste des fichiers avec leur chemin complet
    file_paths = [os.path.join(folder_path, file) for file in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, file))]
    
    # Création du DataFrame
    folder_path_df = pd.DataFrame(file_paths, columns=["File Path"])
    

    for file_path in folder_path_df :
        
        file_path = folder_path_df.loc[0, "File Path"]  # Récupère la première valeur de la colonne
        file_name = os.path.splitext(os.path.basename(file_path))[0]
        df = pd.read_excel(file_path, sheet_name=file_name, header=0)
        
        df = df[ (df["Time"].dt.year >= start_year) & (df["Time"].dt.year <= end_year)]
        df = df[["Time"] + countries_list]
        
        # Définir la première colonne comme index (time)
        df.set_index(df.columns[0], inplace=True)
        df.index.name = "Time"  # Renommer l'index pour la lisibilité
        
        for country in countries_list : 
    
            # # Initialiser l'entrée pour le country
            # data_dict_price_user[country] = {}
            
            data_dict_price_user = df.to_dict()
        

    return data_dict_price_user
    
    
    
    

# Exemple d'utilisation
if __name__ == "__main__":
    
    folder_path_prod = r"C:\Users\cgoas\OneDrive\Documents\S9\Projet EN Supergrid\BDD\2. Base De Données\Production par pays et par filière 2015-2019"
    folder_path_price = r"C:\Users\cgoas\OneDrive\Documents\S9\Projet EN Supergrid\BDD\2. Base De Données\Prix spot par an et par zone 2015-2019"
    countries_list = ['AT','BE','CH','CZ','DE_LU','DK','EE','ES','FI','FR','GB','GR','HU','IT','LT','NL','NO','PL','PT','RO','SE','SI','SK']
    start_year, end_year = 2015, 2015 # years of production database
    
    prod_users = load_database_prod_user(folder_path_prod, countries_list, start_year, end_year)
    price_users = load_database_price_user(folder_path_price, countries_list, start_year, end_year)
    
    # Exemple d'accès aux données
    time = pd.to_datetime("2015-02-20 14:00:00")
    country = "FR"
    production_mode = "fossil_gas_MW"

    try:
        value_prod = prod_users[country][production_mode][time]
        print(f"Production à {time} pour {production_mode} en {country}: {value_prod} MW")
        
        value_price = price_users[country][time]
        print(f"Prix à {time} en {country}: {value_price} €")
    except KeyError:
        print("Donnée introuvable, vérifiez les entrées.")



