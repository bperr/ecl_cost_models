# ecl_cost_models

Ce dépôt est destiné au projet ECL sur les modèles de coûts.

## Bonnes pratiques pour le développement

## Quelques recommandations

- Le code doit être écrit en anglais (nom de variables, commentaires ...)
- Lorsqu'une variable correspond à une grandeur physique, ajoutez un commentaire pour spécifier son unité.
- N'hésitez pas à écrire des commentaires régulièrement.
- Il existe des conventions de nommages des variables pour rendre la compréhension du code plus facile:
 - `variable` ou `my_long_variable_name` pour les variables.
 - `MyClass` pour les classes.
 - `MY_CONSTANT` pour les constantes.  
Ce sont des recommandations, pas des règles, il peut donc y avoir des exceptions (typiquement pour les unités il ne faudrait pas qu'on confonde mW et MW)
- En python, vous pouvez spécifier le type des variables dans une fonction. C'est optionnel et ne change rien au fonctionnement du code, mais c'est plus facile de comprendre pour ceux qui le relisent ;)
```python
def my_function(var1:int, var2:list[str]) -> bool:  # Cette fonction a pour premier argument un entier, son second argument une liste de chaine de caractères et elle renvoie un booléen
	# Some code
```

### Git et les branches

Git propose un système de branches: différentes versions du code qui évoluent indépendament.  
Cela permet de travailler sur différents aspects du code en parallèle sans risquer de modifier le travail d'un autre.

La bonne pratique est de toujours travailler sur une branche différente de `main` (la branche principale du dépôt git) et de rapatrier ses développements sur `main` qu'une fois qu'ils sont complètement implémentés et validés.  
Pour apprendre les bases de la gestion des branches, vous pouvez regarder ce [lien](https://learngitbranching.js.org/?locale=fr_FR). 
Pas la peine de faire tous les niveaux, la séquence d'ntroduction (onglet principal) et push & pull (onglet remote) suffiront à avoir de bonnes bases !

### Séquence classique

- `git checkout main`: se positionner sur la branche `main`
- `git pull`: récupérer la dernière version de main sur le dépôt en ligne et la sauvegarder sur votre version locale de `main`. L'objectif ici est simplement de se mettre à jour.
- `git branch develop` (où `develop` est le nom de votre nouvelle branche, à chosir librement): créer une nouvelle branche sur laquelle on va travailler.
- `git checkout develop`: se positionner sur cette nouvelle branche  
*Note:* Les deux dernières commandes peuvent être fusionnées en `git checkout -b develop`.
- Développer du code sur la branche `develop`. Régulièrement faire des commits pour ajouter les modifications à la branche (`git add <filename>`, `git commit -m <commit message>`, ...).
- Lorsque le code sur la branche `develop` est prêt, `git push --set-upstream origin develop`. Cela permet de créer la branche sur le dépôt distant. Si elle existe déjà `git push` suffit.
- Sur github, dans l'onglet "Code", un bouton "Compare & pull request" vous permet de créer un pull request, c'est à dire une demande de fusionner vos changements sur la branche `main`. Si le bouton n'apparait pas vous pouvez créer la pull request depuis l'onglet "Pull request" et le bouton "New pull request".
- Sur la page de création de la pull request, vous pouvez lui donner un nom et la décrire rapidement puis cliquer sur "Create pull request". Une page spécifique à cette pull request est alors créée.
- Prévenez nous sur Teams que vous avez créé une pull request ou ajoutez nous en tant que reviewers (en haut à droite de la page). **Ne cliquez pas sur le bouton "Merge pull request"**.
- A partir de là, c'est nous qui intervenons. L'idée est que l'on relise votre code pour suggérer au besoin des modifications.
 - Si nous avons des retours à vous faire, nous laisserons des commentaires. Vous devrez alors à nouveau travailler sur la branche `develop`: de nouveaux commits puis lorsque vous êtes satisfait `git push`.
 - Si tout nous convient, **nous** validons la pull request avec le bouton "Merge pull request".
- La branche `main` du dépôt distant contient maintenant vos modifications. Pour mettre à jour votre version locale de `main`, suivez les deux premiers points.

## Présentation du projet

N'hésitez pas à modifier la suite de ce fichier pour présenter votre travail comme bon vous semble.

