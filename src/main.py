from pathlib import Path

from controller import Controller

# studies_dir = Path(__file__).parents[1] / "studies"
# work_dir = studies_dir / "study_1"
# db_dir = studies_dir / "database"

work_dir = Path(r"C:\Users\trist\OneDrive\Documents\ECL3A\Option énergie\Projet d'option\Code\database")
db_dir = Path(r"C:\Users\trist\OneDrive\Documents\ECL3A\Option énergie\Projet d'option\Code\database")

controller = Controller(work_dir=work_dir, db_dir=db_dir)
results = controller.run(export_to_excel=True)  # FIXME Export to Excel
print(results)
