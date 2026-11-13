# API ProspectAI — qualification de prospects (démonstration)

API FastAPI sur une base SQLite de démonstration : 50 entreprises **fictives**
(29 clients, 21 prospects), 215 contacts, 520 interactions, 127 signaux.

## Lancer

```powershell
.\.venv-1\Scripts\Activate.ps1
python -m pip install fastapi uvicorn     # une seule fois
python -m crm.generate_data               # crée data/processed/crm_demo.db
python -m crm.api                         # démarre l'API sur le port 8001
```

- Routes interactives (Swagger) : http://127.0.0.1:8001/docs
- Documentation lisible (ReDoc) : http://127.0.0.1:8001/redoc

Le terminal qui lance l'API reste occupé : interroger l'API depuis un second terminal.

## Routes

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/top-prospects?limit=10` | Meilleurs prospects : score, dernier signal, interlocuteur clé, question d'accroche |
| GET | `/entreprises/{id}/questions` | Questions à poser au client, avec objectif, justification et destinataire |
| GET | `/classement?type=prospect` | Classement par score (filtres : type, division, region, recherche) |
| GET | `/entreprises/{id}/score` | Score détaillé critère par critère |
| GET | `/entreprises` | Liste filtrable (type, division, categorie, region, recherche) |
| GET | `/entreprises/{id}` | Fiche complète : identité, contacts, signaux, interactions, score, questions |
| GET | `/contacts?entreprise_id=` | Interlocuteurs |
| GET | `/signaux?depuis_jours=90` | Signaux récents (filtre : type_signal) |
| GET | `/stats` | Répartitions par type, division, région, étape |
| GET | `/health` | Volume de données en base |
| POST | `/interactions` | Enregistrer le résultat d'un contact |

## Exemples (PowerShell)

```powershell
Invoke-RestMethod "http://127.0.0.1:8001/top-prospects?limit=10"
Invoke-RestMethod "http://127.0.0.1:8001/entreprises/Client_5591/questions" | ConvertTo-Json -Depth 5
Invoke-RestMethod "http://127.0.0.1:8001/classement?type=prospect&division=Fragrance%20%26%20Beauty"

$corps = @{ entreprise_id = "Client_5591"; etape_pipeline = "Lead"; resultat = "Appel de découverte réalisé" } | ConvertTo-Json
Invoke-RestMethod "http://127.0.0.1:8001/interactions" -Method Post -ContentType "application/json" -Body $corps
```

## Scoring (grille Product)

Adéquation 40 · Taille 15 · Innovation 15 · Signaux 20 · Récence 10.
Une donnée absente est marquée `non_disponible` et exclue du calcul (pas pénalisée) ;
le score est ramené sur 100 et `confiance` indique la part de la grille évaluée.
Potentiel = adéquation + taille + innovation ; Timing = signaux + récence.

## Questions commerciales

Générées par règles (pas d'IA), à partir de : signaux récents, catégorie,
critères non disponibles du score, étape de la dernière interaction,
interlocuteurs identifiés, statut client. Chaque question indique
`theme`, `objectif`, `base_sur` (élément déclencheur) et `a_qui`.

## Fichiers

- `generate_data.py` : construit la base depuis `givaudan_crm_data.csv` + données fictives
- `scoring.py` : grille de scoring explicable
- `questions.py` : génération des questions commerciales
- `api.py` : routes FastAPI
