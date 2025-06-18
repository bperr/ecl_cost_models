import pandas as pd
import re
from datetime import datetime, timedelta
from pathlib import Path


def parse_slot(slot_str):
    match = re.match(r"(.+?) - (.+)", slot_str)
    if match:
        start_str, end_str = match.groups()
        try:
            start_dt = datetime.strptime(re.sub(r"\s+\(.*?\)", "", start_str), "%d/%m/%Y %H:%M:%S")
            end_dt = datetime.strptime(re.sub(r"\s+\(.*?\)", "", end_str), "%d/%m/%Y %H:%M:%S")
            return start_dt, end_dt
        except ValueError:
            return None, None
    return None, None


def read_slots_from_file(filepath):
    df = pd.read_excel(filepath, header=None)
    column = df.iloc[7:, 0].dropna()
    slots = []
    for row in column:
        start, end = parse_slot(str(row))
        if start and end:
            slots.append((start, end))
    return slots


def find_gaps(slots):
    gaps = []
    for i in range(1, len(slots)):
        prev_end = slots[i - 1][1]
        curr_start = slots[i][0]
        if curr_start != prev_end:
            gaps.append((i, prev_end, curr_start))
    return gaps


def process_yearly_data(folder_path):
    folder = Path(folder_path)
    files = sorted(folder.glob("GUI_ENERGY_PRICES_*.xlsx"))

    # Extraire les années disponibles
    file_years = sorted([int(re.search(r"(\d{4})", f.name).group(1)) for f in files])

    for year in file_years[:-1]:  # On a besoin de l'année suivante aussi
        current_file = folder / f"GUI_ENERGY_PRICES_{year}.xlsx"
        next_file = folder / f"GUI_ENERGY_PRICES_{year + 1}.xlsx"

        if not next_file.exists():
            print(f"⚠️ Fichier suivant manquant pour {year} → {next_file.name}")
            continue

        # Lire les slots des deux fichiers
        slots = read_slots_from_file(current_file) + read_slots_from_file(next_file)

        # Filtrer les créneaux pour l’année civile
        start_of_year = datetime(year, 1, 1, 0, 0, 0)
        end_of_year = datetime(year, 12, 31, 23, 0, 0) + timedelta(hours=1)  # inclusif jusqu'au 01/01/YYYY+1 00:00:00
        slots_in_year = [s for s in slots if s[0] >= start_of_year and s[1] <= end_of_year]

        expected_hours = int((end_of_year - start_of_year).total_seconds() // 3600)
        found_hours = len(slots_in_year)
        missing_hours = expected_hours - found_hours

        gaps = find_gaps(slots_in_year)

        print(f"\n📅 Année {year}")
        print(f" - Créneaux attendus : {expected_hours}")
        print(f" - Créneaux trouvés  : {found_hours}")
        print(f" - Manquants         : {missing_hours}")
        print(f" - Trous détectés    : {len(gaps)}")

        for idx, prev_end, curr_start in gaps:
            print(f"   → Trou entre {prev_end} et {curr_start}")


if __name__ == "__main__":
    dossier = "C:/Users/a.faivre/PycharmProjects/ECL cost models/DataBase/Prix GB"
    process_yearly_data(dossier)
