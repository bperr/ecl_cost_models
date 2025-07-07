# ecl_cost_models 

Ce dépôt est destiné au projet d'option Energie d'étudiants de l'ECL (Ecole Centrale de Lyon) commandité par SuperGrid Institute. Ce dernier a eu lieu entre Janvier 2025 et Mars 2025.

**"Quelles hypothèses économiques pour modéliser l’avenir du système électrique ?"**

Les élèves de l'ECL ayant participés à ce projet sont les suivants :
- Gaspard CORONT DUCLUZEAU (E21)
- Matthieu FOUQUET (E22)
- Claire GOASDOUE (E21)
- Tristan LACOSTE DE LA REYMONDIE (E21)
- Thibault SUATTON (E21)
- Jeremy POUGET (E21)

Les commanditaires de SuperGrid Institute ayant pilotés le projet sont :
- Nicolas BARLA
- Baptiste PERREYON

## Présentation du projet

L'objectif de ce projet est de fournir un outil Python permettant d'optimiser des hypothèses de prix passés d'appel et d'offre pour charges, générateurs et moyens de stockage du réseau électrique. L'objectif étant de pouvoir appliquer l'outil à différents pays d'Europe, différentes filières et différentes périodes temporelles. 
Cet outil repose sur une base de données qui sera présentée par la suite.

## Présentation de la BDD 
L'outil Python, présenté par la suite, utilise comme support une BDD (Base De Données) qui a été conçue à partir des data d'EnergyGraph et de l'ENTSOE. 
Cette-dernière n'est pas présente sur ce dépot.
Elle est constituée de deux dossiers :
1. La production par pays, filière et heure sur la plage 2015-2019 (en MW)
2. Le prix Spot de l’électricité par zone économique et heure sur la plage 2015-2023 (en €/MWh)

## Présentation de l'outil Python

L' outil Python a pour objectif d'ajuster, optimiser des hypothèses utilisateurs de prix d'appel et d'offre par filière et pays. Pour cela, l'outil compare les données historiques contenues dans la BDD avec les hypothèses de prix utilisateur et utilise une méthode d'optimisation de la bibliothèque scipy de Python. Son fonctionnement est détaillé dans le schéma ci-dessous. Les hypothèses de prix sont alors des paramètres d'entrée permettant d'initialiser l'optimisation. Ils doivent être choisis judicieusement afin d'éviter les effets de plateau par exemple.

Le schéma global de l'outil est le suivant : 

![image](https://github.com/user-attachments/assets/3749f81b-47e5-42ac-806a-31ee001efd3d)

## Méthodologie mise en place 
L'utilisateur, en entrée de l'outil, renseigne, pour chaque zone, secteur et plage temporelle considérés deux valeurs de prix seuils.
L'outil, après optimisation, renverra ces deux valeurs ajustées.

L'hypothèse faite est qu'**en dessous de la première valeur de coût marginal (Prix seuil 0%), aucune centrale de ce type ne produit, et qu'au-dessus de la seconde (Prix seuil 100%), toutes les centrales sont prêtes à produire**. Entre ces deux valeurs, une fonction affine détermine la part des centrales prêtes à produire. Cette méthode permet de prendre en compte la diversité de coûts marginaux pouvant exister au sein d'un groupe de centrales ayant le même mode de production d'énergie. Le raisonnement inverse peut être utilisé dans le cas des charges.

### Par conséquent, le modèle de prix devient :

#### 1. Pour un producteur :
- Si le prix SPOT est inférieur au prix seuil de 0%, alors sa production est nulle, c'est-à-dire 0% de sa puissance maximale.
- Si le prix SPOT est supérieur au prix seuil de 100%, alors sa production est maximale, à 100%.
- Si le prix SPOT est compris entre les prix seuils de 0% et 100%, alors sa production est (en % de sa puissance maximale) :
  
  $$\text{Puissance produite} = \frac{\text{Prix SPOT} - \text{Prix 0\%}}{\text{Prix 100\%} - \text{Prix 0\%}} * \text{Puissance maximale}$$

#### 2. Pour un consommateur :
Les moyens de stockage comme les Stations de Transfert d'Énergie par Pompage (STEP) suivent une fonction affine décroissante (si on considère des puissances et des prix positifs avec $Price\_c100 > Price\_c0$) puisqu'ils consomment lorsque le prix de l'électricité est faible et ne consomment pas quand celui-ci est élevé :

- Si le prix SPOT est supérieur au prix seuil de 0%, alors sa consommation est nulle, c'est-à-dire 0% de sa puissance maximale.
- Si le prix SPOT est inférieur au prix seuil de 100%, alors sa consommation est maximale, à 100%.
- Si le prix SPOT est compris entre les prix seuils de 0% et 100%, alors sa consommation est (en % de sa puissance maximale) :
  
  $$\text{Puissance consommée} = -\frac{\text{Prix SPOT} - \text{Prix 0\%}}{\text{Prix 0\%} - \text{Prix 100\%}} * \text{Puissance maximale}$$

Ainsi, si on note **Price_p0**, **Price_p100** les prix seuils d'un producteur et **Price_c0**, **Price_c100** d'un consommateur, pour un producteur ayant la possibilité de consommer comme les stations hydrauliques de Turbinage-Pompage (à prix et puissance de consommation négatifs) :

$$Price_{c100} < Price_{c0} < Price_{p0} < Price_{p100}$$

## Structure du code 

Le code est structuré en différents fichiers `.py` contenant chacun différentes fonctions.

Toutes les fonctions sont ainsi appelées dans le fichier `controller.py`.
Le fichier `main.py` permet de lancer la simulation et d'extraire les différents résultats.

Vous pouvez trouver ci-dessous le diagramme de séquence UML de l'outil avec l'appel des différentes fonctions :

![image](https://github.com/user-attachments/assets/836a9acd-a278-4b6b-ba60-5a86f4f66ea8)

## Fichiers Inputs 

Deux fichiers excel templates, dit "inputs", sont à compléter en amont de la simulation, par l'utilisateur et sont nécessaires pour le fonctionnement de l'outil.

Le fichier Prices inputs permet de définir les hypothèses de prix pour les différents pays, secteurs et années à considérer tandis que le fichier User inputs paramètre la simulation (périodes temporelles, agrégation de pays en zones, agrégation de modes de productions en zone).

Ces deux fichiers sont disponibles dans le dossier *"Template"* de ce dépôt.

## Utilisation et lancement de la simulation 

Vous pouvez trouver ci-dessous le processus de paramétrage et d'utilisation de l'outil.

### 1. Paramétrage de la simulation dans le fichier Excel *User Inputs*
- Déclaration des pays & modes de production à uploader depuis la BDD.
- Déclaration des regroupements par zones (des pays) et sectors (des modes de production).
- Déclaration des plages temporelles de la simulation.

### 2. Remplissage des hypothèses de prix utilisateurs dans le fichier Excel *Prices Inputs*
Remplissage pour chaque secteur et zone géographique des prix seuils hypothèses. En effet, le fait de regrouper par zones et secteurs permet de ne remplir qu'une seule fois les hypothèses de prix pour chaque zone/secteur. L'outil Python se charge ensuite d'attribuer à chaque pays/modes de prod de chaque zone/secteur les hypothèses correspondantes.

### 3. Organisation des fichiers sur le serveur de l'outil
- Les données de production doivent être dans un dossier *"countries_power_production_by_sector_2015_2019"*.
- Les données de prix spot doivent être dans un dossier *"annual_spot_prices_by_country_2015_2019"*.
  
  ➝ Ces deux dossiers doivent être dans un même dossier dont l'adresse sera à indiquer plus tard (`db_dir`).
  
- Les inputs utilisateurs doivent être dans le fichier *User_Inputs.xlsx*.
- Les hypothèses de prix doivent être dans le fichier *Prices_Inputs.xlsx*.
  
  ➝ Ces deux fichiers doivent être dans un même dossier *"Working Directory"* dont l'adresse sera à indiquer plus tard (`work_dir`).
  
- Créer un dossier *results* dans le dossier *"Working Directory"* qui accueillera les résultats.

### 4. Lancement de la simulation via le fichier `main.py`

```python
from pathlib import Path
from controller import Controller

work_dir = Path(r"C:\Users\Working Directory")
db_dir = Path(r"C:\Users\Database")

controller = Controller(work_dir, db_dir)
results = controller.run(export_to_excel=True)
```

- Indication du chemin des deux répertoires `work_dir` et `db_dir`.
- Exécution du main :
    - La ligne 7 du code crée l'instance `Controller` en prenant en entrée les deux chemins d'accès aux données.
    - La ligne 8 du code lance l'optimisation des hypothèses et l'exportation des résultats dans le fichier Excel d'Outputs.

### 5. Export auto des résultats
Export des résultats dans un fichier d'output : *"Output_prices.xlsx"* dans le dossier *"results"* du dossier *"Working Directory"*.
