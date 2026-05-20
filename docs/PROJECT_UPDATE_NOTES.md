# AgroVision Olive AI - notes de mise a jour

## Commandes de lancement

Backend FastAPI :

```powershell
cd C:\Users\Win11\Downloads\pfe\agrovision-ai
.\.venv312\Scripts\python.exe -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend React/Vite :

```powershell
cd C:\Users\Win11\Downloads\pfe\agrovision-ai\frontend
npm.cmd install
npm.cmd run dev
```

Application : `http://localhost:5173`

Note port backend : si la commande Uvicorn retourne une erreur de socket sur `8000`, verifier d'abord si une instance est deja active :

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Si la reponse est `{"status":"ok"}`, le backend tourne deja et il ne faut pas lancer une deuxieme instance sur le meme port. En cas de port alternatif, lancer le frontend avec `VITE_API_TARGET=http://127.0.0.1:<port>`.

## Flux principaux a tester

1. Ouvrir l'application et naviguer entre les pages.
2. Creer ou modifier une ferme dans Configuration de la ferme.
3. Cliquer sur la carte pour placer le marqueur.
4. Tester le bouton "Utiliser ma position".
5. Enregistrer la ferme, rafraichir, puis verifier que la localisation reste sauvegardee.
6. Lancer Detection de maladie avec une feuille saine, une feuille malade, puis une image floue ou non supportee.
7. Lancer Periode de recolte avec une image et les donnees de ferme.
8. Lancer Modele de production et verifier que le resultat est un intervalle estimatif.
9. Ouvrir le Tableau de bord et verifier la ferme, la meteo, les alertes, l'historique et la production.
10. Utiliser l'Assistant et verifier les messages de fallback si le service IA local est indisponible.

## Disease Scan

Endpoint principal :

```http
POST /disease-scan-expert
```

Classes foliaires actuellement supportees :

- `healthy_leaf`
- `olive_peacock_spot`
- `aculus_olearius`

Pipeline :

1. controle qualite de l'image ;
2. routage de la partie vegetale ;
3. rejet prudent des images non supportees ;
4. classification des feuilles ;
5. seuil de confiance ;
6. regles expertes et recommandation ;
7. sauvegarde possible dans l'historique ferme.

Correctif final applique : l'inference utilise maintenant l'image complete validee au lieu d'un recadrage secondaire trop agressif. Cela reduit les faux positifs sur feuilles saines. Lorsque le routeur de partie vegetale et l'analyse foliaire se contredisent, le service retourne un resultat incertain au lieu d'annoncer une maladie avec trop de certitude.

Tests rapides effectues sur des images du dataset :

| Type d'image | Resultat attendu | Resultat observe | Statut |
| --- | --- | --- | --- |
| Feuille saine | `healthy_leaf` ou absence de symptome visible | 2/3 sain, 1/3 oeil de paon avec symptomes visuels forts | A revoir dataset |
| Oeil de paon | `olive_peacock_spot` ou incertain prudent | 1/3 diagnostic, 2/3 incertain prudent | Conforme prudent |
| Aculus olearius | `aculus_olearius` | 3/3 diagnostic correct | Conforme |
| Image non supportee / ravageur | incertain ou non supporte | 2/2 incertain | Conforme |
| Image floue | demander une image plus claire | 2/2 `needs_better_image` | Conforme |

Chemins importants :

- Dataset organise : `data\disease_training_data\final_curated`
- Dataset pret entrainement : `data\disease_training_data\train_ready`
- Modele foliaire courant : `models\curated\leaf_disease_model.pt`
- Routeur partie vegetale : `models\curated\plant_part_router.pt`
- Metriques : `models\curated\leaf_disease_model.metrics.json`

Inference rapide avec API :

```powershell
curl.exe -X POST http://127.0.0.1:8000/disease-scan-expert -F "file=@C:\path\to\olive_leaf.jpg" -F "language=fr"
```

Reentrainement des modeles Disease Scan :

```powershell
cd C:\Users\Win11\Downloads\pfe\agrovision-ai
.\.venv312\Scripts\python.exe models\train_curated_disease_models.py --execute --epochs 12 --router-epochs 8 --batch-size 16
```

Entrainement direct d'un classifieur ImageFolder :

```powershell
.\.venv312\Scripts\python.exe models\train_classifier.py --dataset data\disease_training_data\final_curated\leaf --output models\curated\leaf_disease_model.pt --model efficientnet_b0 --epochs 12 --batch-size 16
```

## Harvest Time

Le module Periode de recolte utilise une approche hybride :

- image envoyee par l'utilisateur ;
- cultivar ;
- date/saison ;
- localisation de la ferme ;
- meteo Open-Meteo ;
- regles agronomiques et logique prudente.

Important : ce module ne pretend pas etre un modele profond entraine sur un grand dataset annote de maturite. Si les donnees sont incompletes ou contradictoires, le resultat doit rester prudent.

Reentrainement du modele huile/maturite si un CSV de mesures est disponible :

```powershell
.\.venv312\Scripts\python.exe models\train_harvest_model.py --dataset data\olive_ripening_measurements.csv --output models\olive_harvest_model.pkl
```

## Production Model

Le module de production retourne une plage estimative, pas une valeur garantie. Les facteurs pris en compte cote frontend sont notamment :

- nombre d'arbres ;
- age moyen ;
- cultivar ;
- irrigation ;
- pression maladie ;
- meteo/pluie ;
- historique de production s'il existe.

## Base de donnees

Base SQLite par defaut :

```text
data\analysis_history.db
```

Tables principales :

- `farm_profiles`
- `tree_groups`
- `farm_scan_records`
- `farm_alerts`
- `farm_notes`
- tables historiques d'analyse et d'observation.

La migration ajoute les champs de ferme manquants sans supprimer les donnees :

- `primary_cultivar`
- `tree_age`
- `irrigation_mode`
- `notes`

## Limites connues

- Les resultats IA dependent fortement de la qualite et de la diversite des images.
- Les fruits et branches restent traites de maniere conservative dans le diagnostic maladie.
- Harvest Time n'est pas encore un modele profond specialise entraine sur un grand dataset annote de maturite.
- Production Model reste une aide a la decision et doit etre interprete comme une estimation.
- Une validation terrain avec agronome reste necessaire avant usage agricole reel.
