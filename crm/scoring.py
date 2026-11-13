"""Scoring explicable selon la grille officielle Product.

| Critère                                  | Poids |
|------------------------------------------|-------|
| Adéquation avec les activités Givaudan   |  40   |
| Taille et potentiel économique           |  15   |
| Innovation et développement              |  15   |
| Signaux détectés                         |  20   |
| Date récente du signal                   |  10   |

Règle clé : une donnée ABSENTE n'est pas une mauvaise note. Le critère est
marqué "non_disponible", exclu du calcul, et le score est ramené sur 100
avec les critères disponibles. Le niveau de confiance indique la part de
la grille réellement évaluée.

Potentiel = adéquation + taille + innovation ; Timing = signaux + récence
(découpage du tableau Product "Score global + Potentiel / Timing").
"""

from datetime import date


POIDS = {
    "adequation": 40,
    "taille": 15,
    "innovation": 15,
    "signaux": 20,
    "recence": 10,
}

CATEGORIES_GIVAUDAN = {
    "Taste & Wellbeing": {"Sweet Goods", "Dairy", "Beverages", "Savoury"},
    "Fragrance & Beauty": {"Fine Fragrances", "Consumer Products",
                           "Fragrance Ingredients", "Active Beauty"},
}

TYPES_INNOVATION = {"lancement_produit", "innovation", "partenariat_rd"}

COEFFICIENT_FIABILITE = {"haute": 1.0, "moyenne": 0.7, "faible": 0.4}


def _critere(nom, note, statut, justification, preuves=None):

    return {
        "critere": nom,
        "note": round(note, 1) if note is not None else None,
        "max": POIDS[nom],
        "statut": statut,   # confirme | estime | non_disponible | obsolete
        "justification": justification,
        "preuves": preuves or [],
    }


def _age_jours(date_iso, aujourd_hui):

    return (aujourd_hui - date.fromisoformat(date_iso)).days


def critere_adequation(entreprise, interactions):

    division, categorie = entreprise["division"], entreprise["categorie"]

    if categorie not in CATEGORIES_GIVAUDAN.get(division, set()):
        return _critere("adequation", None, "non_disponible",
                        "Catégorie inconnue ou hors périmètre Givaudan : à qualifier.")

    note = 25
    raisons = [f"Catégorie « {categorie} » couverte par la division {division} (+25)."]
    preuves = ["Référentiel des catégories Givaudan"]

    if entreprise["client_existant"]:
        note += 5
        raisons.append("Client existant (+5).")

    gagnees = sum(1 for i in interactions if i["etape_pipeline"] == "Closed Won")
    perdues = sum(1 for i in interactions if i["etape_pipeline"] == "Closed Lost")

    if gagnees + perdues:
        taux = gagnees / (gagnees + perdues)
        note += 10 * taux
        raisons.append(f"Historique de conversion : {gagnees} affaire(s) gagnée(s) "
                       f"sur {gagnees + perdues} conclue(s), soit {taux:.0%} (+{10 * taux:.1f}).")
        preuves.append(f"{len(interactions)} interactions CRM")
        statut = "confirme"
    else:
        raisons.append("Aucune affaire conclue : historique de conversion non évaluable.")
        statut = "estime"

    return _critere("adequation", min(note, 40), statut, " ".join(raisons), preuves)


def critere_taille(entreprise):

    volume = entreprise["volume_moyen_commande_kg"]
    frequence = entreprise["frequence_commande_mois"]

    if volume and frequence:
        annuel = volume * 12 / frequence
        if annuel >= 20000:
            note = 15
        elif annuel >= 8000:
            note = 11
        elif annuel >= 3000:
            note = 7
        else:
            note = 4
        return _critere("taille", note, "confirme",
                        f"Volume annuel estimé : {annuel:,.0f} kg "
                        f"({volume} kg tous les {frequence} mois).".replace(",", " "),
                        ["Historique de commandes CRM"])

    ca = entreprise["chiffre_affaires_meur"]

    if ca:
        note = 15 if ca >= 500 else 11 if ca >= 100 else 7 if ca >= 20 else 4
        return _critere("taille", note, "confirme",
                        f"Chiffre d'affaires {entreprise['annee_ca']} : {ca} M€.",
                        [entreprise["source"]])

    return _critere("taille", None, "non_disponible",
                    "Ni historique de commandes, ni chiffre d'affaires connu.")


def critere_innovation(signaux, aujourd_hui):

    recents = [s for s in signaux
               if s["type_signal"] in TYPES_INNOVATION
               and _age_jours(s["date_publication"], aujourd_hui) <= 365]

    if not recents:
        return _critere("innovation", None, "non_disponible",
                        "Aucun signal d'innovation sur les 12 derniers mois "
                        "(absence d'information, pas preuve d'absence).")

    note = {1: 8, 2: 12}.get(len(recents), 15)

    return _critere("innovation", note, "confirme",
                    f"{len(recents)} signal(aux) d'innovation sur 12 mois.",
                    [f"{s['titre']} ({s['date_publication']}, {s['source']})" for s in recents])


def critere_signaux(signaux, aujourd_hui):

    recents = [s for s in signaux if _age_jours(s["date_publication"], aujourd_hui) <= 365]

    if not recents:
        return _critere("signaux", None, "non_disponible",
                        "Aucun signal commercial sur les 12 derniers mois.")

    # Un signal peu fiable compte moins qu'un signal de source officielle.
    poids_total = sum(COEFFICIENT_FIABILITE.get(s["fiabilite"], 0.5) for s in recents)
    note = min(20, 7 * poids_total)

    return _critere("signaux", note, "confirme",
                    f"{len(recents)} signal(aux) sur 12 mois, pondérés par fiabilité "
                    f"(total pondéré {poids_total:.1f}).",
                    [f"{s['type_signal']} : {s['titre']} ({s['date_publication']}, "
                     f"fiabilité {s['fiabilite']})" for s in recents])


def critere_recence(signaux, aujourd_hui):

    if not signaux:
        return _critere("recence", None, "non_disponible", "Aucun signal daté.")

    dernier = max(signaux, key=lambda s: s["date_publication"])
    age = _age_jours(dernier["date_publication"], aujourd_hui)

    if age <= 30:
        note, statut = 10, "confirme"
    elif age <= 90:
        note, statut = 8, "confirme"
    elif age <= 180:
        note, statut = 5, "confirme"
    elif age <= 365:
        note, statut = 2, "confirme"
    else:
        note, statut = 0, "obsolete"

    return _critere("recence", note, statut,
                    f"Dernier signal publié il y a {age} jours ({dernier['date_publication']}).",
                    [dernier["titre"]])


def _sous_score(criteres, noms):

    evalues = [c for c in criteres if c["critere"] in noms and c["note"] is not None]

    if not evalues:
        return None

    return round(100 * sum(c["note"] for c in evalues) / sum(c["max"] for c in evalues), 1)


def priorite(score):

    if score is None:
        return "non évaluable"
    if score >= 80:
        return "prioritaire"
    if score >= 60:
        return "intéressant"
    if score >= 40:
        return "à approfondir"
    return "faible adéquation identifiée"


def calculer_score(entreprise, interactions, signaux, aujourd_hui=None):

    aujourd_hui = aujourd_hui or date.today()

    criteres = [
        critere_adequation(entreprise, interactions),
        critere_taille(entreprise),
        critere_innovation(signaux, aujourd_hui),
        critere_signaux(signaux, aujourd_hui),
        critere_recence(signaux, aujourd_hui),
    ]

    score = _sous_score(criteres, POIDS.keys())
    poids_evalues = sum(c["max"] for c in criteres if c["note"] is not None)

    libelle = priorite(score)

    # Score non pénalisé par les absences, mais priorité signalée comme fragile.
    if score is not None and poids_evalues < 70:
        libelle += " (à confirmer : données incomplètes)"

    return {
        "entreprise_id": entreprise["id"],
        "nom": entreprise["nom"],
        "score_global": score,
        "potentiel": _sous_score(criteres, {"adequation", "taille", "innovation"}),
        "timing": _sous_score(criteres, {"signaux", "recence"}),
        "confiance": f"{poids_evalues}% de la grille évaluée",
        "poids_evalues": poids_evalues,
        "priorite": libelle,
        "criteres": criteres,
        "donnees_fictives": bool(entreprise["fictif"]),
    }
