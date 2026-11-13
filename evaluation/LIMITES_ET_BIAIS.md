# Limites et biais — pôle Data, ProspectAI

Ce document recense les limites connues des données, des modèles de score et de
leur évaluation. Il accompagne la comparaison V1 / V2 (`RESULTATS.md`). Chaque point
indique son effet sur les résultats et ce qu'il faudrait pour le lever.

---

## 1. Limites des données

### 1.1 Le CRM est fictif (`givaudan_crm_data.csv`)

| Constat | Effet |
|---|---|
| 50 clients et 520 interactions générés artificiellement, sans nom d'entreprise ni de contact | Aucun résultat ne peut être généralisé à de vrais clients Givaudan |
| Les étapes du pipeline sont réparties de façon quasi uniforme (entre 74 et 101 occurrences chacune) et chaque client a à la fois des affaires gagnées et perdues | Le lien entre l'historique et l'issue d'une affaire est faible : un modèle ne peut pas être très bon sur ces données |
| Horodatages inexploitables (toutes les dates écrasées en « 08:59.8 » par Excel) | La chronologie a été reconstituée à partir de l'ordre des lignes. C'est une **hypothèse**, non vérifiable |
| 16 371 colonnes vides ajoutées par Excel (16 384 au total) et 9 lignes en double | Corrigé à la lecture : seules les 13 vraies colonnes sont lues |
| Comptes rendus d'échange génériques | Inutilisables pour détecter des besoins précis |
| Aucun signal commercial (recrutement, lancement, investissement…) | 45 % de la grille Product (innovation, signaux, récence) ne peut pas être évaluée sur ce fichier |

### 1.2 Les données que nous avons générées (`crm/generate_data.py`)

- Noms d'entreprises, contacts et signaux sont **inventés**. Les signaux sont tirés au
  hasard : un bon score « signaux » reflète le générateur, pas une réalité commerciale.
- Le chiffre d'affaires et l'effectif sont volontairement absents pour environ 30 % des
  entreprises, afin de tester le comportement du score face à une donnée manquante.
- Graine fixe : la base est reproductible, mais toujours la même. On ne teste donc
  qu'un seul tirage de données fictives.

### 1.3 Les données réelles collectées (`research/`)

| Constat | Effet |
|---|---|
| Les effectifs de l'INSEE sont des **tranches**, publiées avec retard | Aroma-Zone : environ 500 à 850 salariés d'après l'INSEE, contre plus de 1 000 annoncés fin 2025. Source administrative en retard, pas une contradiction |
| Plusieurs sites refusent les robots dans leur robots.txt (aroma-zone.com, flux Google Actualités) | Nous ne les collectons pas, par choix. La couverture des signaux est donc faible tant que d'autres sources ne sont pas branchées |
| Quand un article n'est pas accessible, seul le résumé RSS est conservé (marqué `resume_rss`) | Information plus pauvre, à ne pas présenter comme un article complet |
| La date d'une page web est parfois estimée par l'outil d'extraction | Le critère de récence peut être faussé pour ces pages |
| Une marque correspond souvent à plusieurs sociétés (exploitation, magasins, logistique, holdings) | Le choix de la société de référence est humain. Une erreur de choix fausse la taille et le secteur |

---

## 2. Limites et biais des modèles de score

Les deux modèles (V1 du pôle Tech, V2 du pôle Data) sont **à base de règles** : les poids
sont fixés à la main, pas appris sur des données. Ils sont explicables, mais leur
pertinence dépend entièrement des choix des personnes qui les ont écrits.

| Biais | Modèle | Explication |
|---|---|---|
| **Critère peu discriminant** | V2 | Toute entreprise d'une catégorie Givaudan reçoit 25 points d'adéquation sur 40. Dans le CRM, toutes les entreprises en relèvent : ce critère ne les départage presque pas |
| **Renormalisation favorable aux fiches incomplètes** | V2 | Une donnée absente est exclue du calcul (règle Product : ne pas pénaliser l'absence). Une entreprise évaluée sur peu de critères peut donc obtenir un score élevé. Atténué par l'indicateur de confiance et la mention « à confirmer » sous 70 % |
| **Biais en faveur des grandes entreprises** | V1 et V2 | Le volume de commande et le chiffre d'affaires pèsent dans la taille : une petite entreprise innovante est structurellement moins bien notée |
| **Seuils arbitraires** | V1 et V2 | Paliers de volume, de chiffre d'affaires et de récence choisis sans calibrage |
| **Biais de sélection** | V1 et V2 | Le CRM ne contient que des entreprises **déjà en relation avec Givaudan**. Les modèles n'ont jamais été testés sur de vrais prospects jamais contactés, qui sont pourtant la cible de l'outil |
| **Grilles différentes** | V1 / V2 | V1 utilise Potentiel 60 / Opportunité 30 / Accessibilité 10, et V2 la grille officielle Product 40/15/15/20/10. Les scores ne sont pas directement comparables en valeur, seulement en classement |

### Questions commerciales

- Les questions générées par **règles** sont fiables (rien n'est inventé) mais parfois
  génériques, notamment les questions par catégorie.
- Les questions rédigées par le **LLM** (Qwen 2.5 3B, service du pôle Tech) peuvent
  contenir des détails inventés ; le pôle Tech l'a constaté et les marque « à vérifier ».

---

## 3. Limites de l'évaluation (comparaison V1 / V2)

| Limite | Effet |
|---|---|
| **30 cas seulement** | Intervalles de confiance larges (AUC V1 : 0,54 à 0,90 ; V2 : 0,29 à 0,73) |
| **Vérité terrain fictive** : la dernière affaire conclue de chaque client du faux CRM | Les métriques mesurent la capacité à retrouver une issue générée artificiellement, pas une vraie conversion commerciale |
| Chronologie reconstituée à partir de l'ordre des lignes | Si cet ordre n'est pas chronologique, la séparation historique / issue est approximative |
| V2 évaluée à 55 % de sa grille (pas de signaux dans le CRM) | La comparaison désavantage V2 : sa partie « signaux et récence » n'est pas testée |
| Pas de validation humaine par l'équipe Product | Personne n'a encore confirmé que le classement « a du sens » pour un commercial |

**Conclusion de l'évaluation.** Sur l'historique du CRM, la V1 classe mieux les affaires
que la V2 (AUC moyenne 0,66 contre 0,55 sur 200 tirages ; V1 meilleure dans 90 % des
tirages). La V2 respecte la grille Product, mais elle ne peut pas être jugée entièrement
sans signaux réels. Ces chiffres valident surtout le **protocole d'évaluation**, prêt à
être relancé sur de vraies données.

---

## 4. Limites liées au RGPD et au respect des sites

Ces limites sont **volontaires** : elles découlent de nos choix de conformité.

- Les coordonnées (e-mails, téléphones, profils LinkedIn) ne sont pas collectées.
  Le critère « qui contacter » repose sur les fonctions et les dirigeants légaux.
- Les sites qui refusent les robots ne sont pas collectés, même si leurs informations
  seraient utiles.
- Les données personnelles des dirigeants sont réduites au nom, aux prénoms et à la
  fonction.

---

## 5. Ce qu'il faudrait pour lever ces limites

1. **Un extrait anonymisé du vrai CRM Givaudan**, avec de vraies dates et de vraies issues
   d'affaires.
2. **30 cas étiquetés par l'équipe Product** : la priorité attendue pour chaque entreprise,
   pour mesurer l'accord entre le modèle et l'avis métier.
3. **Des sources de signaux réels et autorisées** : BODACC (annonces légales, open data),
   flux RSS des médias qui l'autorisent, API France Travail pour les offres d'emploi.
4. **Une V3** : la structure de la grille Product, enrichie de la dynamique du pipeline
   qui fait la force de la V1. À comparer à V1 et V2 avec le même script.
5. **Un arbitrage de l'équipe** sur la grille de score de référence (60/30/10 ou 40/15/15/20/10).
