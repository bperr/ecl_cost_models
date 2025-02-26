# -*- coding: utf-8 -*-
"""
Created on Fri Feb 14 08:27:09 2025

@author: cgoas
"""

from pathlib import Path

import pandas as pd


def load_database_prod_user(folder_path: Path, country_list: list[str], start_year: int, end_year: int) -> dict:
    if end_year < start_year:
        raise ValueError("End year cannot be before start year")

    # Dictionnaire pour stocker les données
    data_dict_prod_user = {}

    file_name_template = "Prod_{}_2015_2019.xlsx"  # Country code will be inserted instead of brackets

    for country in country_list:
        file_name = file_name_template.format(country)  # Replace {} by the country code
        sheet_name = file_name[:-5]  # filename without .xlsx
        df = pd.read_excel(folder_path / f"{file_name}", sheet_name=sheet_name, header=0)

        df = df[(df["Début de l'heure"].dt.year >= start_year) & (df["Début de l'heure"].dt.year <= end_year)]

        # Définir la première colonne comme index (time)
        df.set_index(df.columns[0], inplace=True)  # Column name is also kept as index name

        # Initialiser l'entrée pour le country
        data_dict_prod_user[country] = {}

        # Restructurer les données sous la forme souhaitée
        for prod_mode in df[df.columns]:  # Parcours des modes de production
            data_dict_prod_user[country][prod_mode] = df[prod_mode].to_dict()

    return data_dict_prod_user


def load_database_price_user(folder_path, country_list, start_year, end_year):
    if end_year < start_year:
        raise ValueError("End year cannot be before start year")

    # Dictionnaire pour stocker les données
    data_dict_price_user = {country: dict() for country in country_list}

    file_name_template = "SPOT_{}.xlsx"  # Year will be inserted instead of brackets

    for year in range(start_year, end_year + 1):
        file_name = file_name_template.format(year)
        sheet_name = file_name[:-5]  # filename without .xlsx

        # index_col = 0 to set column time as index
        df = pd.read_excel(folder_path / file_name, sheet_name=sheet_name, header=0, index_col=0)

        for country in country_list:
            country_columns = [zone for zone in df.columns if zone.startswith(country)]
            country_df = zones_to_country(df[country_columns])
            data_dict_price_user[country].update(country_df.to_dict())

    return data_dict_price_user


def zones_to_country(df: pd.DataFrame) -> pd.Series:
    return df.mean(axis=1)


# Exemple d'utilisation
if __name__ == "__main__":
    # db_path = Path(__file__).parents[1] / "instance" / "database"
    db_path = Path(r"C:\Users\b.perreyon\Documents\ECL cost models\database")
    folder_path_prod = db_path / "Production par pays et par filière 2015-2019"
    folder_path_price = db_path / "Prix spot par an et par zone 2015-2019"
    countries_list = ['AT', 'BE', 'CH', 'CZ', 'DE', 'DK', 'EE', 'ES', 'FI', 'FR',
                      'GB', 'GR', 'HU', 'IT', 'LT', 'NL', 'NO', 'PL', 'PT', 'RO',
                      'SE', 'SI', 'SK']
    start_year, end_year = 2015, 2015  # years of production database

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
        print(f"Prix à {time} en {country}: {value_price} €/MWh")
    except KeyError:
        print("Donnée introuvable, vérifiez les entrées.")
