import pandas as pd
import re
from datetime import datetime, timedelta
from pathlib import Path


def parse_slot(slot_str):
    """
    Parses a timeslot string and extracts the start and end datetimes.

    The expected format is:
    "DD/MM/YYYY HH:MM:SS - DD/MM/YYYY HH:MM:SS"

    This format is typically used in ENTSO-E Excel exports (e.g. GUI_ENERGY_PRICES files),
    where timeslots are defined as a string separated by a hyphen.

    :param slot_str: A string containing the start and end datetimes separated by a hyphen.
    :return: A tuple of two datetime objects (start, end), or (None, None) if parsing fails.
    """
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
    """
    Reads timeslots from a given Excel file and parses them into start and end datetime tuples.

    The timeslots are expected to start from row 8 in the first column, following the format
    "DD/MM/YYYY HH:MM:SS - DD/MM/YYYY HH:MM:SS".

    :param filepath: The path to the Excel file containing the timeslot strings.
    :return: A list of tuples, each containing a start and end datetime object.
    """

    df = pd.read_excel(filepath, header=None)
    column = df.iloc[7:, 0].dropna()
    slots = []
    for row in column:
        start, end = parse_slot(str(row))
        if (start is not None) and (end is not None):
            slots.append((start, end))
    return slots


def find_gaps(slots):
    """
    Identifies discontinuities (gaps) between consecutive timeslots.

    A gap is defined as a mismatch between the end of one slot and the start of the next.

    :param slots: A list of tuples, each containing start and end datetime objects.
    :return: A list of tuples (index, previous_end, current_start) representing the position
             and boundaries of each gap found in the sequence.
    """
    gaps = []
    for i in range(1, len(slots)):
        prev_end = slots[i - 1][1]
        curr_start = slots[i][0]
        if curr_start != prev_end:
            gaps.append((i, prev_end, curr_start))
    return gaps


def process_yearly_data(folder_path):
    """
        Processes timeslot data from multiple yearly Excel files in a folder,
        detects missing hours and gaps within each calendar year.

        The function expects filenames to follow the pattern "GUI_ENERGY_PRICES_YYYY.xlsx".
        It compares the actual slots found to the expected number of hours in a year,
        and detects any discontinuities in the data.

        :param folder_path: Path to the folder containing the Excel files.
        :return: None. Prints results to the console.
    """
    folder = Path(folder_path)
    files = sorted(folder.glob("GUI_ENERGY_PRICES_*.xlsx"))

    # Extract the available years
    file_years = sorted([int(re.search(r"(\d{4})", f.name).group(1)) for f in files])

    for year in file_years[:-1]:  # Following year data is also required
        current_file = folder / f"GUI_ENERGY_PRICES_{year}.xlsx"
        next_file = folder / f"GUI_ENERGY_PRICES_{year + 1}.xlsx"

        if not next_file.exists():
            print(f"File of next year is missing for {year} → {next_file.name}")
            continue

        # Read time slots of the two files
        slots = read_slots_from_file(current_file) + read_slots_from_file(next_file)

        # Filter the timeslots for the year studied
        start_of_year = datetime(year, 1, 1, 0, 0, 0)
        end_of_year = datetime(year, 12, 31, 23, 0, 0) + timedelta(hours=1)  # includes 01/01/YYYY+1 00:00:00
        slots_in_year = [s for s in slots if s[0] >= start_of_year and s[1] <= end_of_year]

        expected_hours = int((end_of_year - start_of_year).total_seconds() // 3600)
        found_hours = len(slots_in_year)
        missing_hours = expected_hours - found_hours

        gaps = find_gaps(slots_in_year)

        print(f"\n Year {year}")
        print(f" - Expected hours : {expected_hours}")
        print(f" - Found hours  : {found_hours}")
        print(f" - Missing hours         : {missing_hours}")
        print(f" - Gaps found    : {len(gaps)}")

        for idx, prev_end, curr_start in gaps:
            print(f"   → Gap between {prev_end} and {curr_start}")


if __name__ == "__main__":
    directory = "C:/Users/a.faivre/PycharmProjects/ECL cost models/DataBase/Prix GB"
    process_yearly_data(directory)
