"""API ProspectAI - CRM de démonstration.

Lancement (depuis la racine du projet) :
    python -m crm.generate_data     # une fois, pour créer la base
    python -m crm.api               # démarre l'API

Documentation interactive (Swagger) : http://127.0.0.1:8001/docs
Documentation lisible (ReDoc)         : http://127.0.0.1:8001/redoc
"""

import sqlite3

from datetime import date, timedelta
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from crm.generate_data import DB_PATH
from crm.scoring import calculer_score
from crm.questions import generer_questions


DESCRIPTION = """
API de qualification de prospects B2B pour Givaudan.

Elle répond aux trois questions du commercial :
- **Pourquoi cette entreprise ?** score expliqué selon la grille Product
  (adéquation 40, taille 15, innovation 15, signaux 20, récence 10) ;
- **Pourquoi maintenant ?** signaux commerciaux datés ;
- **Qui contacter et comment ?** interlocuteurs et questions à poser.

**Par où commencer :** `GET /top-prospects`, puis `GET /entreprises/{id}/questions`
sur le n°1 (par exemple `Client_5591`).

Une donnée absente n'abaisse pas le score : le critère est marqué
`non_disponible`, exclu du calcul, et la confiance l'indique.

**Toutes les entreprises et tous les contacts sont fictifs** (e-mails en `.example`,
téléphones dans la plage réservée à la fiction).
"""

TAGS = [
    {"name": "commerciaux", "description": "Top prospects et questions à poser au client."},
    {"name": "scoring", "description": "Score expliqué critère par critère et classement."},
    {"name": "entreprises", "description": "Liste et fiche complète des entreprises."},
    {"name": "contacts", "description": "Interlocuteurs (fictifs)."},
    {"name": "signaux", "description": "Événements commerciaux datés."},
    {"name": "interactions", "description": "Saisie du résultat d'un contact."},
    {"name": "système", "description": "État de la base et statistiques."},
]

app = FastAPI(
    title="ProspectAI - API de qualification de prospects",
    description=DESCRIPTION,
    version="1.1.0",
    openapi_tags=TAGS,
)


# ==================================================
# ACCÈS À LA BASE
# ==================================================

def connexion():

    if not DB_PATH.exists():
        raise HTTPException(503, "Base absente : lance d'abord `python -m crm.generate_data`.")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    return conn


def lignes(conn, requete, params=()):

    return [dict(r) for r in conn.execute(requete, params).fetchall()]


def charger_entreprise(conn, entreprise_id):

    trouvees = lignes(conn, "SELECT * FROM entreprises WHERE id = ?", (entreprise_id,))

    if not trouvees:
        raise HTTPException(404, f"Entreprise '{entreprise_id}' introuvable.")

    return trouvees[0]


def charger_details(conn, entreprise_id):
    """Contacts, signaux et interactions d'une entreprise."""

    return {
        "contacts": lignes(conn, "SELECT * FROM contacts WHERE entreprise_id = ?",
                           (entreprise_id,)),
        "signaux": lignes(conn, "SELECT * FROM signaux WHERE entreprise_id = ? "
                                "ORDER BY date_publication DESC", (entreprise_id,)),
        "interactions": lignes(conn, "SELECT * FROM interactions WHERE entreprise_id = ? "
                                     "ORDER BY date DESC", (entreprise_id,)),
    }


def score_entreprise(conn, entreprise, details=None):

    details = details or charger_details(conn, entreprise["id"])

    return calculer_score(entreprise, details["interactions"], details["signaux"])


def questions_entreprise(conn, entreprise, details=None, score=None):

    details = details or charger_details(conn, entreprise["id"])
    score = score or score_entreprise(conn, entreprise, details)

    return generer_questions(entreprise, details["contacts"], details["signaux"],
                             details["interactions"], score)


# ==================================================
# ENDPOINTS
# ==================================================

@app.get("/", include_in_schema=False)
def accueil():
    """La racine renvoie vers la documentation interactive."""

    return RedirectResponse("/docs")


@app.get("/health", tags=["système"])
def health():
    """Vérifie que la base existe et donne le volume de données."""

    with connexion() as conn:
        return {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("entreprises", "contacts", "interactions", "signaux")
        }


@app.get("/entreprises", tags=["entreprises"])
def lister_entreprises(
    type: Literal["client", "prospect"] | None = None,
    division: Literal["Taste & Wellbeing", "Fragrance & Beauty"] | None = None,
    categorie: str | None = None,
    region: str | None = None,
    recherche: str | None = Query(None, description="Texte contenu dans le nom"),
    limit: int = Query(50, ge=1, le=200),
):
    """Liste des entreprises, filtrable (vue « dashboard » du tableau Product)."""

    conditions, params = [], []

    for colonne, valeur in (("type", type), ("division", division),
                            ("categorie", categorie), ("region", region)):
        if valeur:
            conditions.append(f"{colonne} = ?")
            params.append(valeur)

    if recherche:
        conditions.append("nom LIKE ?")
        params.append(f"%{recherche}%")

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    with connexion() as conn:
        return lignes(
            conn,
            f"SELECT id, nom, type, division, categorie, region, pays, fictif "
            f"FROM entreprises {where} ORDER BY nom LIMIT ?",
            (*params, limit),
        )


@app.get("/entreprises/{entreprise_id}", tags=["entreprises"])
def fiche_entreprise(entreprise_id: str):
    """Fiche complète : identité, contacts, signaux, dernières interactions,
    score et questions à poser."""

    with connexion() as conn:
        entreprise = charger_entreprise(conn, entreprise_id)
        details = charger_details(conn, entreprise_id)
        score = score_entreprise(conn, entreprise, details)
        return {
            "entreprise": entreprise,
            "contacts": details["contacts"],
            "signaux": details["signaux"],
            "dernieres_interactions": details["interactions"][:5],
            "score": score,
            "questions": questions_entreprise(conn, entreprise, details, score),
        }


@app.get("/entreprises/{entreprise_id}/questions", tags=["commerciaux"])
def questions(entreprise_id: str):
    """Questions à poser au client, générées à partir de ses données.
    Chaque question indique son objectif, l'élément qui la justifie et à qui la poser."""

    with connexion() as conn:
        entreprise = charger_entreprise(conn, entreprise_id)
        return {
            "entreprise_id": entreprise_id,
            "nom": entreprise["nom"],
            "questions": questions_entreprise(conn, entreprise),
        }


@app.get("/top-prospects", tags=["commerciaux"])
def top_prospects(
    limit: int = Query(10, ge=1, le=50),
    division: Literal["Taste & Wellbeing", "Fragrance & Beauty"] | None = None,
    region: str | None = None,
):
    """Les meilleurs prospects avec les détails utiles au commercial :
    score, dernier signal, interlocuteur clé et question d'accroche."""

    conditions, params = ["type = 'prospect'"], []
    if division:
        conditions.append("division = ?")
        params.append(division)
    if region:
        conditions.append("region = ?")
        params.append(region)

    with connexion() as conn:
        resultats = []
        for entreprise in lignes(conn, f"SELECT * FROM entreprises WHERE {' AND '.join(conditions)}", params):
            details = charger_details(conn, entreprise["id"])
            score = score_entreprise(conn, entreprise, details)
            liste = questions_entreprise(conn, entreprise, details, score)
            signal = details["signaux"][0] if details["signaux"] else None
            cle = next((c for c in details["contacts"] if c["service"] == "Direction générale"),
                       details["contacts"][0] if details["contacts"] else None)
            resultats.append({
                "entreprise_id": entreprise["id"],
                "nom": entreprise["nom"],
                "division": entreprise["division"],
                "categorie": entreprise["categorie"],
                "pays": entreprise["pays"],
                "region": entreprise["region"],
                "score_global": score["score_global"],
                "potentiel": score["potentiel"],
                "timing": score["timing"],
                "confiance": score["confiance"],
                "poids_evalues": score["poids_evalues"],
                "priorite": score["priorite"],
                "dernier_signal": {k: signal[k] for k in ("type_signal", "titre", "date_publication")}
                                  if signal else None,
                "interlocuteur_cle": f"{cle['prenom']} {cle['nom']} - {cle['fonction']}" if cle else None,
                "question_cle": liste[0]["question"] if liste else None,
                "nb_questions": len(liste),
                "fictif": bool(entreprise["fictif"]),
            })

    resultats.sort(key=lambda r: (r["score_global"] is None, -(r["score_global"] or 0), -r["poids_evalues"]))

    for rang, r in enumerate(resultats[:limit], start=1):
        r["rang"] = rang

    return resultats[:limit]


@app.get("/entreprises/{entreprise_id}/score", tags=["scoring"])
def score(entreprise_id: str):
    """Score détaillé critère par critère, avec justification et preuves."""

    with connexion() as conn:
        return score_entreprise(conn, charger_entreprise(conn, entreprise_id))


@app.get("/classement", tags=["scoring"])
def classement(
    type: Literal["client", "prospect"] | None = None,
    division: Literal["Taste & Wellbeing", "Fragrance & Beauty"] | None = None,
    region: str | None = None,
    recherche: str | None = Query(None, description="Texte contenu dans le nom"),
    limit: int = Query(10, ge=1, le=100),
):
    """Entreprises classées par score global, puis par part de la grille évaluée.
    Les non évaluables sont placées en dernier."""

    with connexion() as conn:
        conditions, params = [], []
        if type:
            conditions.append("type = ?")
            params.append(type)
        if division:
            conditions.append("division = ?")
            params.append(division)
        if region:
            conditions.append("region = ?")
            params.append(region)
        if recherche:
            conditions.append("nom LIKE ?")
            params.append(f"%{recherche}%")
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        scores = [score_entreprise(conn, e)
                  for e in lignes(conn, f"SELECT * FROM entreprises {where}", params)]

    scores.sort(key=lambda s: (s["score_global"] is None,
                               -(s["score_global"] or 0),
                               -s["poids_evalues"]))

    return [
        {k: s[k] for k in ("entreprise_id", "nom", "score_global", "potentiel",
                           "timing", "confiance", "priorite")}
        for s in scores[:limit]
    ]


@app.get("/contacts", tags=["contacts"])
def lister_contacts(entreprise_id: str | None = None, service: str | None = None):
    """Interlocuteurs (nom, fonction, service, source). Tous fictifs."""

    conditions, params = [], []
    if entreprise_id:
        conditions.append("entreprise_id = ?")
        params.append(entreprise_id)
    if service:
        conditions.append("service = ?")
        params.append(service)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    with connexion() as conn:
        return lignes(conn, f"SELECT * FROM contacts {where} ORDER BY entreprise_id", params)


@app.get("/signaux", tags=["signaux"])
def lister_signaux(
    type_signal: str | None = None,
    depuis_jours: int = Query(365, ge=1, description="Publiés dans les N derniers jours"),
):
    """Signaux commerciaux récents (« Pourquoi maintenant ? »)."""

    limite = (date.today() - timedelta(days=depuis_jours)).isoformat()
    conditions, params = ["s.date_publication >= ?"], [limite]
    if type_signal:
        conditions.append("s.type_signal = ?")
        params.append(type_signal)

    with connexion() as conn:
        return lignes(
            conn,
            "SELECT s.*, e.nom AS entreprise FROM signaux s "
            "JOIN entreprises e ON e.id = s.entreprise_id "
            f"WHERE {' AND '.join(conditions)} ORDER BY s.date_publication DESC",
            params,
        )


@app.get("/stats", tags=["système"])
def statistiques():
    """Répartition par type, division, région et étape du pipeline."""

    with connexion() as conn:
        def repartition(requete):
            return {r[0]: r[1] for r in conn.execute(requete).fetchall()}

        return {
            "par_type": repartition("SELECT type, COUNT(*) FROM entreprises GROUP BY type"),
            "par_division": repartition("SELECT division, COUNT(*) FROM entreprises GROUP BY division"),
            "par_region": repartition("SELECT region, COUNT(*) FROM entreprises GROUP BY region"),
            "interactions_par_etape": repartition(
                "SELECT etape_pipeline, COUNT(*) FROM interactions GROUP BY etape_pipeline"),
        }


class NouvelleInteraction(BaseModel):
    entreprise_id: str = Field(examples=["Client_1008"])
    contact_id: str | None = None
    etape_pipeline: Literal["Lead", "Brief Received", "Evaluation/Sampling",
                            "Negotiation", "Closed Won", "Closed Lost"]
    resultat: str = Field(examples=["Appel de découverte réalisé"])
    prochaine_action: str | None = Field(None, examples=["Envoyer des échantillons"])
    compte_rendu: str | None = None


@app.post("/interactions", tags=["interactions"], status_code=201)
def ajouter_interaction(interaction: NouvelleInteraction):
    """Renseigner le résultat d'un contact (étape « Après » du tableau Product)."""

    with connexion() as conn:
        charger_entreprise(conn, interaction.entreprise_id)
        curseur = conn.execute(
            "INSERT INTO interactions (entreprise_id, contact_id, date, etape_pipeline, "
            "compte_rendu, resultat, prochaine_action, source) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (interaction.entreprise_id, interaction.contact_id, date.today().isoformat(),
             interaction.etape_pipeline, interaction.compte_rendu, interaction.resultat,
             interaction.prochaine_action, "Saisie via l'API"),
        )
        return {"id": curseur.lastrowid, "statut": "interaction enregistrée"}


if __name__ == "__main__":
    import threading
    import webbrowser

    import uvicorn

    URL = "http://127.0.0.1:8001"

    print(f"\n  API ProspectAI        : {URL}")
    print(f"  Routes (Swagger)      : {URL}/docs")
    print(f"  Documentation (ReDoc) : {URL}/redoc")
    print("  (Ctrl+C pour arrêter)\n")

    # Ouvre la documentation des routes dans le navigateur, 2 s après le démarrage.
    threading.Timer(2, lambda: webbrowser.open(f"{URL}/docs")).start()

    uvicorn.run("crm.api:app", host="127.0.0.1", port=8001, reload=True)
