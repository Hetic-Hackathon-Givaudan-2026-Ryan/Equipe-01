# ProspectAI — Équipe 01 · Hackathon HETIC × Givaudan

ProspectAI aide les équipes commerciales de Givaudan à identifier, documenter et
qualifier des entreprises susceptibles de devenir des clients. Le système répond
à trois questions :

1. **Pourquoi cette entreprise ?** — adéquation avec les activités Givaudan
   (Taste & Wellbeing, Fragrance & Beauty), score expliqué.
2. **Pourquoi maintenant ?** — signaux commerciaux datés (recrutements,
   lancements, investissements, partenariats…).
3. **Qui contacter et comment ?** — interlocuteurs et questions à poser au client.

> **État du projet : POC.** L'API de qualification fonctionne sur des données
> **fictives**. La collecte de données réelles (identité, documents publics) fonctionne
> pour l'identification et la collecte ; l'extraction IA, l'alimentation automatique
> des CSV et le dossier final ne sont pas encore réalisés.

---

## Sommaire

- [Installation](#installation)
- [1. API de qualification (CRM de démonstration)](#1-api-de-qualification-crm-de-démonstration)
- [2. Collecte de données réelles](#2-collecte-de-données-réelles)
- [Conformité : RGPD, robots.txt, droit d'auteur](#conformité--rgpd-robotstxt-droit-dauteur)
- [Structure du dépôt](#structure-du-dépôt)
- [Reste à faire](#reste-à-faire)

---

## Installation

Windows / PowerShell, Python 3.12 ou plus récent.

```powershell
python -m venv .venv-1
.\.venv-1\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

---

## 1. API de qualification (CRM de démonstration)

API FastAPI interrogeable, sur une base SQLite construite à partir du faux CRM
`givaudan_crm_data.csv` (520 interactions) complété par des données fictives.

| Contenu de la base | Volume |
|---|---|
| Entreprises (toutes **fictives**) | 50 — 29 clients, 21 prospects |
| Contacts fictifs | 215 |
| Interactions commerciales | 520 |
| Signaux commerciaux | 127 |

E-mails en `.example` (domaine réservé) et téléphones en `01 99 00 xx xx`
(plage réservée par l'ARCEP à la fiction) : aucune vraie personne ne peut être contactée.

### Lancer

```powershell
python -m crm.generate_data     # crée data/processed/crm_demo.db (reproductible)
python -m crm.api               # démarre l'API sur http://127.0.0.1:8001
```

La documentation des routes s'ouvre automatiquement :

- **Swagger (interactif)** : http://127.0.0.1:8001/docs — bouton *Try it out* sur chaque route
- **ReDoc (lisible)** : http://127.0.0.1:8001/redoc

Le terminal de l'API reste occupé : interroger l'API depuis un second terminal.

### Routes

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/top-prospects?limit=10` | **Les 10 meilleurs prospects** : score, potentiel, timing, dernier signal, interlocuteur clé, question d'accroche |
| GET | `/entreprises/{id}/questions` | **Questions à poser au client**, avec objectif, élément déclencheur et destinataire |
| GET | `/classement` | Classement par score (filtres : `type`, `division`, `region`, `recherche`) |
| GET | `/entreprises/{id}/score` | Score détaillé critère par critère, avec justifications et preuves |
| GET | `/entreprises` | Liste filtrable (`type`, `division`, `categorie`, `region`, `recherche`) |
| GET | `/entreprises/{id}` | Fiche complète : identité, contacts, signaux, interactions, score, questions |
| GET | `/contacts` | Interlocuteurs (filtres : `entreprise_id`, `service`) |
| GET | `/signaux` | Signaux récents (filtres : `depuis_jours`, `type_signal`) |
| GET | `/stats` | Répartitions par type, division, région et étape du pipeline |
| GET | `/health` | Volume de données en base |
| POST | `/interactions` | Enregistrer le résultat d'un contact commercial |

### Exemples

```powershell
# Top 10 des prospects
Invoke-RestMethod "http://127.0.0.1:8001/top-prospects?limit=10"

# Questions à poser pour le n°1
Invoke-RestMethod "http://127.0.0.1:8001/entreprises/Client_5591/questions" | ConvertTo-Json -Depth 5

# Enregistrer un appel
$corps = @{ entreprise_id = "Client_5591"; etape_pipeline = "Lead"; resultat = "Appel de découverte réalisé" } | ConvertTo-Json
Invoke-RestMethod "http://127.0.0.1:8001/interactions" -Method Post -ContentType "application/json" -Body $corps
```

### Scoring (grille officielle Product)

| Critère | Poids | Calcul |
|---|---:|---|
| Adéquation avec les activités Givaudan | 40 | Catégorie couverte par une division, statut client, taux de conversion historique |
| Taille et potentiel économique | 15 | Volume annuel de commandes, sinon chiffre d'affaires |
| Innovation et développement | 15 | Lancements, brevets, partenariats R&D sur 12 mois |
| Signaux détectés | 20 | Nombre de signaux sur 12 mois, pondérés par fiabilité |
| Date récente du signal | 10 | Ancienneté du dernier signal |

- **Une donnée absente n'est pas une mauvaise note** : le critère est marqué
  `non_disponible`, exclu du calcul, et le score est ramené sur 100.
- `confiance` indique la part de la grille réellement évaluée ; sous 70 %, la
  priorité porte la mention « à confirmer ».
- **Potentiel** = adéquation + taille + innovation · **Timing** = signaux + récence.
- Chaque critère a un statut : `confirme`, `estime`, `non_disponible` ou `obsolete`.

### Questions commerciales

Générées **par règles, sans IA** : rien n'est inventé et chaque question est traçable.
Elles sont déclenchées par :

- les **signaux récents** (ex. recrutement R&D → « quels projets ces recrues vont-elles porter ? ») ;
- la **catégorie** (ex. confiserie → réduction du sucre ; parfumerie → naturalité) ;
- les **critères non disponibles** du score (questions de qualification) ;
- l'**étape de la dernière interaction** (découverte, brief, échantillons, négociation…) ;
- les **interlocuteurs identifiés** (une question par service) ;
- le **statut client** (proposer la seconde division Givaudan).

Chaque question précise son `theme`, son `objectif`, l'élément qui la justifie
(`base_sur`) et à qui la poser (`a_qui`).

Détails techniques : [`crm/README.md`](crm/README.md).

---

## 2. Collecte de données réelles

Orchestrateur qui transforme un nom de marque en fiche d'identité officielle et en
documents publics.

```powershell
python main.py
```

1. Recherche de l'entreprise dans l'**API Recherche d'Entreprises** (open data de l'État).
2. Affichage de toutes les entités juridiques, avec les sociétés qui les dirigent
   (reconstitution de la chaîne marque → société d'exploitation → holdings) ;
   choix humain de l'entité, jamais automatique.
3. Sauvegarde d'une fiche d'identité **minimisée** dans `data/raw/said/identite/`.
4. Collecte des pages publiques autorisées et des actualités dans `data/raw/said/documents/`.
5. Bilan : documents collectés, refus robots.txt, échecs.

| Fichier | Rôle |
|---|---|
| `research/company_lookup.py` | Identification juridique (`selectionner_entreprise(nom)`) |
| `research/collect.py` | Collecte documentaire (`main(company, siren)`) |
| `research/entreprises_config.json` | Pages officielles et alias par entreprise |

**Exemple Aroma-Zone :** la marque est exploitée par plusieurs sociétés dirigées par
AROMA ZONE BIDCO — HYTECK (éditeur du site, 250-499 salariés), AROMA-ZONE STORE
(magasins), GREENLOG (logistique). La page recrutement est collectée ; le site
principal et le flux Google Actualités refusent les robots dans leur robots.txt :
la collecte s'arrête, comme prévu.

Structure de données cible : `data/raw/said/` (`entreprises.csv`, `signaux.csv`,
`contacts.csv`, `sources.csv`).

---

## Conformité : RGPD, robots.txt, droit d'auteur

- **robots.txt respecté** : lu avant chaque page ou flux ; en cas d'interdiction ou de
  doute, la page n'est pas collectée. Aucun contournement (403, protections anti-robots).
- **Données personnelles minimisées** : la réponse brute de l'API n'est pas conservée ;
  pour les dirigeants, seuls le nom, les prénoms et la fonction sont gardés (ni date de
  naissance ni nationalité), et rien si la diffusion est restreinte.
- **Pas d'aspiration de coordonnées** (LinkedIn, e-mails) : en production, ProspectAI
  se brancherait sur l'outil de coordonnées sous licence de Givaudan.
- **Droit d'auteur** : les textes d'articles et les données brutes ne sont pas publiés
  sur GitHub (voir `.gitignore`).
- **Traçabilité** : chaque document garde son URL, son média, sa date de publication et
  sa date de collecte ; les résumés RSS sont marqués `resume_rss`.

---

## Structure du dépôt

```text
Equipe-01/
├── crm/                      API de qualification (démonstration)
│   ├── api.py                Routes FastAPI
│   ├── generate_data.py      Construction de la base fictive
│   ├── scoring.py            Scoring explicable (grille Product)
│   ├── questions.py          Questions commerciales
│   └── README.md             Documentation technique de l'API
├── research/                 Collecte de données réelles
│   ├── company_lookup.py
│   ├── collect.py
│   └── entreprises_config.json
├── main.py                   Orchestrateur identification + collecte
├── data/
│   ├── raw/said/             CSV de référence (+ documents non versionnés)
│   └── processed/            Base SQLite générée (non versionnée)
├── givaudan_crm_data.csv     Faux CRM source
├── Data_Prospect.txt         Base de connaissances (méthodologie, grille)
├── rag.py, ingest.py, api.py RAG ChromaDB + Ollama (en cours d'adaptation)
└── requirements.txt
```

Non versionnés : `.venv-1/`, `chroma_db/`, `.env`, `data/raw/said/documents/`,
`data/raw/said/identite/`, `data/processed/*.db`.

---

## Reste à faire

- [ ] Ajouter Aroma-Zone, Groupe Rocher et Nestlé France à la base avec leurs données
      réelles sourcées (`fictif = 0`), après validation du statut prospect par Product.
- [ ] Sources de signaux conformes : BODACC (open data), flux RSS des médias autorisés,
      API France Travail.
- [ ] Extraction des signaux par Qwen (Ollama) avec source obligatoire.
- [ ] Alimentation automatique des CSV et génération du dossier de prospection.
- [ ] Adapter le RAG (`rag.py`, `ingest.py`, `api.py`) aux documents collectés.
