# KSEARCHBOT hybride

Projet KSEARCH : interface PHP sur IONOS et crawler Python, avec recherche de secours Brave si configuree.

## Structure
- `search/` : dossier a deployer dans la racine web IONOS (`/search/`).
- `crawler/` : robot Python a executer ailleurs (local ou GitHub Actions).

## Demarrage local
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r crawler/requirements.txt
python crawler/ksearchbot.py --country FR --seed https://www.service-public.fr/ --max-pages 10
php -S localhost:8000 -t search
```

Le crawler respecte les directives robots.txt et peut donc ne pas indexer les URL fournies.
L'index local se cree dans `search/data/index.sqlite`. Ne le publiez pas sur GitHub.
Pour activer Brave, copier `search/config.example.php` vers `search/config.php` et y configurer sa cle (fichier ignore par Git).

## Deploiement
Copier uniquement le contenu de `search/` sous `www/search/` ou equivalent dans l'hebergement IONOS. Transferer l'index SQLite via un canal prive et atomique (ne jamais le mettre dans le depot public). Verifier que `search/data/` est inaccessible par HTTP. Le crawler n'est pas un service permanent sur GitHub.

## Limites V1
Index initial vide; crawl limite par pays et par graines. Filtrage par extension de domaine, pas par lieu effectif de l'entreprise. Pagination locale et classement hybrides a ameliorer.
