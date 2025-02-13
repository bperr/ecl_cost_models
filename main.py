import pandas as pd

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------


class Pays:
    
    def __init__(self,type,production,opex,capex,priorite):
        self.type=type
        self.production=production
        self.opex=opex
        self.capex=capex
        self.priorite=priorite
        self.ListeProd()

    def ChangerOrdre(self,priorite):
        self.priorite=priorite
        
        
    def Affiche(self):
        print(f"type de production : '{self.type}', production : {self.production}MW, ordre : {self.ordre}")
        
        
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
        
class Interco:
    
    def __initi__(self,pays1,pays2,capa):
        self.pays1=pays1
        self.pays2=pays2
        self.capa=capa
        
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
        
def Affiche(matrice):
    largeur=15
    for ligne in matrice:
        print("".join(f"{x:^{largeur}}" for x in ligne))
       
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------

        
if __name__ == "__main__":
    
    # col1 = df['Country 1']
    # col2 = df['Country 2']
    # col3 = df['Capacity (MW)']
    
    # list_col1 = df['Country 1'].tolist()
    # list_col2 = df['Country 2'].tolist()
    # list_col3 = df['Capacity (MW)'].tolist()
    
    # Matrice_Interconnections = [list_col1,list_col2,list_col3]