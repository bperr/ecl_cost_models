from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

# Define the folder
path = Path("C:/Users/a.faivre/PycharmProjects/ECL cost models/Working/availabilities analysis")

# Load the Excel file
df = pd.read_excel(path / "Yearly availability (energygraph.info).xlsx")


df["Time"] = pd.to_datetime(df["Time"], dayfirst=True) # Convert the ‘Time’ column to datetime
df.set_index("Time", inplace=True) # Define "Time" as index

# Group by time using .resample and average
hourly_df = df.resample("h").mean()
hourly_df.reset_index(inplace=True) # Reset the index to have the ‘Time’ column again

# --- 1. Load modelled availabilities (index = 2025, column = y2019) ---
df_model = hourly_df
df_model["Time"] = pd.to_datetime(df_model["Time"], dayfirst=True)
df_model["Time"] = df_model["Time"].apply(lambda dt: dt.replace(year=2000))
df_model.set_index("Time", inplace=True)
serie_model = df_model["y2019"].rename("Real (energy graph)")

# --- 2. Load actual availabilities (correct year: 2019) ---
df_reel = pd.read_excel(path / "French_nuclear_availabilities_2019-2019.xlsx")
df_reel["Début de l'heure"] = pd.to_datetime(df_reel["Début de l'heure"], dayfirst=True)
df_reel["Début de l'heure"] = df_reel["Début de l'heure"].apply(lambda dt: dt.replace(year=2000))
df_reel.set_index("Début de l'heure", inplace=True)
serie_real = df_reel["Availabilities (MW)"].rename("Modelled")

# --- 3. Merge the two series ---
comparison_df = pd.concat([serie_real, serie_model], axis=1)

# --- 4. Compare the two series ---
df = comparison_df.dropna()

# Calculations
mae = np.mean(np.abs(df["Modelled"] - df["Real (energy graph)"]))
rmse = np.sqrt(np.mean((df["Modelled"] - df["Real (energy graph)"])**2))
r2 = df.corr().loc["Real (energy graph)", "Modelled"]**2  # carré du coefficient de corrélation de Pearson
mean_reel = df["Real (energy graph)"].mean()
mean_model = df["Modelled"].mean()
relative_error = 100 * mae / mean_reel

# Calculate the hourly variance (modelled - actual)
comparison_df["Error (MW)"] = comparison_df["Modelled"] - comparison_df["Real (energy graph)"]

# Delete NaN for plots
df_error = comparison_df.dropna()

# Display in terminal
textstr = '\n'.join((
    f"MAE   : {mae:.0f} MW",
    f"RMSE  : {rmse:.0f} MW",
    f"Erreur : {relative_error:.2f} %",
    f"R²     : {r2:.3f}",
    f"Reel   : {mean_reel:.0f} MW",
    f"Model  : {mean_model:.0f} MW"
))
print("Statistiques de comparaison")
print(f"- MAE (écart absolu moyen)      : {mae:.2f} MW")
print(f"- RMSE (erreur quadratique moy) : {rmse:.2f} MW")
print(f"- Erreur relative moyenne       : {relative_error:.2f} %")
print(f"- R² (corrélation)              : {r2:.3f}")
print(f"- Moyenne réelle                : {mean_reel:.2f} MW")
print(f"- Moyenne modélisée             : {mean_model:.2f} MW")

# --- 4. Plot ---
ax = comparison_df.plot(figsize=(12, 5), title="Comparison 2019 : real vs modelled data")
ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
ax.xaxis.set_major_locator(mdates.DayLocator(interval=7))
props = dict(boxstyle='round', facecolor='white', alpha=0.8)
ax.text(0.98, 0.02, textstr, transform=ax.transAxes, fontsize=10,
        verticalalignment='bottom', horizontalalignment='right', bbox=props)

plt.xlabel("Date (day / month)")
plt.ylabel("Available Power (MW)")
plt.grid(True)
plt.tight_layout()
plt.show()

# Plot of the error
plt.figure(figsize=(12, 5))
plt.plot(df_error.index, df_error["Error (MW)"], color="orange", label="Hourly error (MW)")
plt.axhline(0, color="gray", linestyle="--", linewidth=1)

plt.title("Modelled - Actual gap over time (2019)")
plt.xlabel("Date (day / month)")
plt.ylabel("Availability modelling error (MW)")
plt.grid(True)
plt.legend()

# Récupérer l’axe actuel et formater l’axe X
ax = plt.gca()
ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
ax.xaxis.set_major_locator(mdates.DayLocator(interval=14))

plt.tight_layout()
plt.show()