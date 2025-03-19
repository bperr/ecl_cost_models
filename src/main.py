from pathlib import Path

from controller import Controller

# studies_dir = Path(__file__).parents[1] / "studies"
# work_dir = studies_dir / "study_1"
# db_dir = studies_dir / "database"

work_dir = Path(r"C:\Users\cgoas\OneDrive\Documents\S9\Projet EN Supergrid\BDD\2. Base De Données\Hypothèses de prix Utilisateurs")
db_dir = Path(r"C:\Users\cgoas\OneDrive\Documents\S9\Projet EN Supergrid\BDD\2. Base De Données")

controller = Controller(work_dir=work_dir, db_dir=db_dir)
results = controller.run(export_to_excel=True)  # FIXME Export to Excel
print(results)
