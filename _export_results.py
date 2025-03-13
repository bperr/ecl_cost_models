

def _export_results(self, results : dict):

    """
    Takes the dictionary results and displays its data in a spreadsheet in 
    xlsx format. Each sheet represents a range of years entered by the user.
    
    :param results : dictionnary made by run with the computed 
    price model for each year range x zone x main sector.
    :return : an xlsx sheet with the calculated values
    """

    with pd.ExcelWriter('Output_prices.xlsx', engine='xlsxwriter') as writer:
        for year, zones_data in results.items():
            year_str = str(year)  
    
            data = []
            all_sectors = set()  
    
            
            for zone_info in zones_data.values():
                for sector in zone_info.keys():
                    all_sectors.add(sector)
    
            all_sectors = sorted(all_sectors)
            columns = ['Zone', 'Price Type'] + list(all_sectors)
    
            for zone, sectors in zones_data.items():
                price_type_values = {
                    'Cons_max': {sector: None for sector in all_sectors},
                    'Cons_min': {sector: None for sector in all_sectors},
                    'Prod_min': {sector: None for sector in all_sectors},
                    'Prod_max': {sector: None for sector in all_sectors}
                }
    
    
                for sector, values in sectors.items():
                    price_type_values['Cons_max'][sector] = values[0]
                    price_type_values['Cons_min'][sector] = values[1]
                    price_type_values['Prod_min'][sector] = values[2]
                    price_type_values['Prod_max'][sector] = values[3]
                    
    
                for price_type, values in price_type_values.items():
                    row = [zone, price_type] + [values[sect] for sect in all_sectors]
                    data.append(row)
    
            df = pd.DataFrame(data, columns=columns)
            df.to_excel(writer, sheet_name=year_str, index=False)
