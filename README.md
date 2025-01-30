# ecl_cost_models

Ce dépôt est destiné au projet ECL sur les modèles de coûts.

## Git et les branches

Git propose un système de branches: différentes versions du code qui évoluent indépendament.  
Cela permet de travailler sur différents aspects du code en parallèle sans risquer de modifier le travail d'un autre.

La bonne pratique est de toujours travailler sur une branche différente de `master` (la branche principale du dépôt git) et de rapatrier ses développements sur `master` qu'une fois qu'ils sont complètement implémentés et validés.  
Pour apprendre les bases de la gestion des branches, vous pouvez regarder ce [lien](https://learngitbranching.js.org/?locale=fr_FR). 
Pas la peine de faire tous les niveaux, la séquence d'ntroduction (onglet principal) et push & pull (onglet remote) suffiront à avoir de bonnes bases !


### Séquence classique

- `git checkout master`: se positionner sur la branche `master`
- `git pull`: récupérer la dernière version de master sur le dépôt en ligne et la sauvegarder sur votre version locale de `master`. L'objectif ici est simplement de se mettre à jour.
- `git branch develop` (où `develop` est le nom de votre nouvelle branche): créer une nouvelle branche sur laquelle on va travailler.
- `git checkout develop`: se positionner sur cette nouvelle branche
*Note:* Les deux dernières commandes peuvent être fusionnées en `git checkout -b develop`.
- Développer du code sur la branche `develop`. Régulièrement faire des commits pour ajouter les modifications à la branche (`git add <filename>`, `git commit -m <commit message>`, ...).
- Lorsque le code sur la branche est prêt, `git push --set-upstream origin develop`
- Sur github, aller dans l'onglet "Pull requests"

