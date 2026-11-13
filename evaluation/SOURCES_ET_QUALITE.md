# Inventaire des sources et analyse de la qualité des données — pôle Data, ProspectAI

Livrables du lundi 9 novembre (exploration) : inventaire des sources et de leurs
modalités d'accès, premier échantillon, analyse initiale de la qualité, solution
alternative quand les données sont indisponibles. Ce document les met par écrit à
partir de ce que nous avons réellement collecté et mesuré.

---

## 1. Inventaire des sources

### 1.1 Sources utilisées

| Source | Données apportées | Modalité d'accès | Statut | Fiabilité |
|---|---|---|---|---|
| **API Recherche d'Entreprises** (`recherche-entreprises.api.gouv.fr`) | Identité légale, SIREN, code NAF, nature juridique, tranche d'effectif, dirigeants (dont sociétés mères), finances publiées | Open data de l'État, sans clé. Limite de débit : réponse 429 gérée | Collectée (`research/company_lookup.py`) | A — administrative |
| **Page recrutement Aroma-Zone** (`careers.aroma-zone.com/jobs`) | Offres d'emploi (signal de recrutement) | Page publique, autorisée par le robots.txt | Collectée (2 255 caractères extraits) | B — déclaration de l'entreprise |
| **Faux CRM** (`givaudan_crm_data.csv`, créé par Abanoub) | 50 clients, 520 interactions : division, catégorie, région, volume, fréquence, étape du pipeline, rôle, preuve | Fichier du dépôt | Utilisé par les APIs V1 et V2 | Fictive |
| **Base de démonstration** (`crm/generate_data.py`) | Faux CRM enrichi : noms, 215 contacts, 127 signaux, tous inventés | Générée, reproductible | Utilisée par l'API de qualification | Fictive |

### 1.2 Sources identifiées mais non collectées automatiquement

| Source | Raison |
|---|---|
| **Site principal** et **mentions légales** d'Aroma-Zone | Le robots.txt interdit l'accès aux robots. Respecté, pas de contournement |
| **Flux RSS Google Actualités** | Le robots.txt interdit l'accès aux robots. Respecté depuis l'ajout du contrôle (13 nov.) |
| **Articles de presse** (Le Journal des Entreprises, CFNEWS) | Droit d'auteur : lecture humaine et citation dans `sources.csv`, pas d'aspiration |
| **Profils LinkedIn, annuaires de coordonnées** | Conditions d'utilisation et RGPD : non collectés |
| **Societe.com** | Conditions d'utilisation interdisant l'aspiration : consultation manuelle seulement |

> **Point de vigilance.** Une première collecte d'actualités (12 nov.), faite avant
> l'ajout du contrôle robots.txt, a produit 16 documents. Ils ont été mis de côté
> (`data/raw/said/documents_archive_v1/`, non versionné) et ne sont **pas exploités**.

### 1.3 Sources prévues (accès autorisé, non encore branchées)

| Source | Données | Modalité d'accès |
|---|---|---|
| **BODACC** (annonces légales) | Levées de fonds, cessions, changements de capital ou de dirigeants, datés | Open data, sans clé |
| **API France Travail** | Offres d'emploi (formulation, R&D, achats) | API officielle, inscription gratuite |
| **Flux RSS de médias spécialisés** | Actualités datées et sourcées | Selon le robots.txt de chaque média, vérifié automatiquement |
| **INPI** (brevets, registre national des entreprises) | Innovations, comptes déposés | Open data, compte gratuit |

---

## 2. Premier échantillon collecté

Test réel du 13 novembre sur **Aroma-Zone** (`python main.py`) :

- **10 entités juridiques** renvoyées par l'API. Huit appartiennent au groupe : la holding
  AROMA ZONE BIDCO dirige HYTECK (éditeur du site, NAF 46.75Z, 250 à 499 salariés),
  AROMA-ZONE STORE (magasins, 47.78C, 54 établissements), GREENLOG (logistique) et deux
  SCI ; les holdings AROMA ZONE TOPCO et INVESTCO complètent la liste. Deux autres
  résultats sont des homonymes sans lien avec le groupe (HELPAC, AROMA POLTI FRANCE).
- **Fiches d'identité** enregistrées pour HYTECK (334806502) et AROMA-ZONE STORE (813023843).
- **1 document** collecté (page recrutement). **3 refus** du robots.txt respectés.

---

## 3. Analyse de la qualité des données

### 3.1 Faux CRM (`givaudan_crm_data.csv`)

Mesures effectuées sur le fichier du dépôt :

| Dimension | Mesure | Verdict |
|---|---|---|
| Structure | 16 384 colonnes (le maximum d'Excel) dont **16 371 entièrement vides** ; fichier de 8,9 Mo pour 520 lignes | ❌ Corrigé à la lecture : seules les 13 vraies colonnes sont gardées |
| Complétude | 0 valeur manquante sur les 13 colonnes utiles | ✅ |
| Cohérence | Profil identique (division, catégorie, région, volume, fréquence) pour toutes les lignes d'un même client | ✅ |
| Doublons | 9 lignes en double exact | ⚠️ À dédoublonner avant tout calcul de fréquence |
| Dates | Une seule valeur pour les 520 lignes : « 08:59.8 » (format écrasé par Excel) | ❌ Inexploitable : chronologie reconstituée par l'ordre des lignes |
| Comptes rendus | 31 textes distincts pour 520 lignes, gabarits répétés, données personnelles retirées (« [PII REMOVED] ») | ⚠️ Peu informatifs |
| Distribution | 6 étapes du pipeline réparties entre 74 et 101 occurrences ; chaque client a des affaires gagnées et perdues | ⚠️ Distribution quasi aléatoire, faible pouvoir prédictif |
| Équilibre | Fragrance & Beauty 306 lignes, Taste & Wellbeing 214 ; langues FR 255 / EN 265 | ✅ Acceptable |
| Signaux commerciaux | Absents | ❌ 45 % de la grille Product non évaluable |

### 3.2 Données réelles collectées

| Dimension | Constat |
|---|---|
| Fiabilité | Bonne pour l'identité (source administrative), moyenne pour les pages d'entreprise (déclaratif) |
| Fraîcheur | Effectifs INSEE en tranches et publiés avec retard ; dates de pages parfois estimées |
| Encodage | Accents cassés (« SantÃ© ») lors de la première collecte : cause identifiée (encodage par défaut de la bibliothèque HTTP) et corrigée |
| Complétude | Faible pour les signaux : plusieurs sites refusent les robots |
| Traçabilité | Chaque document garde URL, média, date de publication, date de collecte et type de contenu (`article_complet`, `resume_rss`, `page_complete`) |
| Données personnelles | Réduites au nom, aux prénoms et à la fonction des dirigeants ; réponse brute de l'API non conservée |

---

## 4. Solution alternative retenue

Les données réelles étant partielles (sites fermés aux robots, pas de vrai CRM Givaudan),
nous avons suivi deux voies en parallèle :

1. **Pour le prototype : des données fictives** conformes aux besoins du produit
   (faux CRM, base de démonstration générée). Elles permettent de montrer tout le parcours
   et de tester les modèles de score.
2. **Pour le projet final : une collecte de données réelles** limitée aux sources
   autorisées (open data, pages permises par le robots.txt), à étendre avec les sources
   prévues (BODACC, France Travail, flux RSS des médias, INPI).
