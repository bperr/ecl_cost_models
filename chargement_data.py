import pandas as pd

df1 = pd.read_csv('Interconnections capacities.csv')
#df2 = pd.read_csv('BDD.csv')

pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)

print(df1)