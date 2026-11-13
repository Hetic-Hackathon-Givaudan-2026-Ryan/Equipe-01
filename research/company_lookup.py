"""Identification juridique via l'API officielle Recherche d'Entreprises.

Utilisation autonome :
    python research/company_lookup.py

Utilisation depuis un autre script :
    from research.company_lookup import selectionner_entreprise
    fiche = selectionner_entreprise("Aroma-Zone")   # None si annulé
"""

import requests
import json
import re

from pathlib import Path
from datetime import datetime, timezone


# ==================================================
# CONFIGURATION
# ==================================================

API_URL = "https://recherche-entreprises.api.gouv.fr/search"

# Chemin ancré sur la racine du projet : fonctionne quel que soit
# le dossier depuis lequel on lance le script.
ROOT_DIR = Path(__file__).resolve().parent.parent

OUTPUT_DIR = ROOT_DIR / "data" / "raw" / "said" / "identite"

HEADERS = {
    "User-Agent": "ProspectAI-HETIC-Hackathon/1.0 (recherche de donnees publiques)",
    "Accept": "application/json"
}


# ==================================================
# OUTILS
# ==================================================

def nettoyer_nom(nom):
    return re.sub(r"[^a-zA-Z0-9_-]", "_", nom)


def rechercher_entreprise(nom):
    """Interroge l'API. Accepte un nom ou directement un SIREN."""

    params = {
        "q": nom,
        "page": 1,
        "per_page": 10
    }

    try:
        response = requests.get(
            API_URL,
            params=params,
            headers=HEADERS,
            timeout=20
        )

        if response.status_code == 429:
            delai = response.headers.get("Retry-After", "quelques")
            print(f"[LIMITE] Trop de requêtes. Réessaie dans {delai} secondes.")
            return []

        response.raise_for_status()

        donnees = response.json()

        return donnees.get("results", [])

    except requests.exceptions.Timeout:
        print("[ERREUR] Le serveur n'a pas répondu à temps.")

    except requests.exceptions.HTTPError as erreur:
        print(f"[ERREUR HTTP] {erreur}")

    except requests.exceptions.RequestException as erreur:
        print(f"[ERREUR RESEAU] {erreur}")

    except ValueError:
        print("[ERREUR] Réponse JSON invalide.")

    return []


def _personnes_morales(entreprise):

    return [
        {
            "denomination": d.get("denomination"),
            "siren": d.get("siren"),
            "qualite": d.get("qualite") or "",
        }
        for d in entreprise.get("dirigeants") or []
        if d.get("type_dirigeant") == "personne morale"
    ]


def est_commissaire_aux_comptes(dirigeant):
    return "commissaire aux comptes" in dirigeant["qualite"].lower()


def dirigeants_personnes_morales(entreprise):
    """Sociétés qui dirigent celle-ci (souvent la holding mère), SANS les
    commissaires aux comptes (auditeurs externes, pas des sociétés mères).
    C'est la donnée clé pour reconstituer la chaîne marque -> exploitant -> holdings."""

    return [d for d in _personnes_morales(entreprise) if not est_commissaire_aux_comptes(d)]


def commissaires_aux_comptes(entreprise):

    return [d for d in _personnes_morales(entreprise) if est_commissaire_aux_comptes(d)]


def dirigeants_personnes_physiques(entreprise):
    """Minimisation RGPD : nom, prénoms et fonction uniquement
    (ni date de naissance, ni nationalité)."""

    return [
        {
            "nom": d.get("nom"),
            "prenoms": d.get("prenoms"),
            "qualite": d.get("qualite"),
        }
        for d in entreprise.get("dirigeants") or []
        if d.get("type_dirigeant") == "personne physique"
    ]


# ==================================================
# AFFICHAGE DES RESULTATS
# ==================================================

def afficher_resultats(resultats):

    print("\n========== ENTREPRISES TROUVEES ==========\n")

    for index, entreprise in enumerate(resultats, start=1):

        siege = entreprise.get("siege") or {}

        print(f"[{index}] {entreprise.get('nom_complet', 'Non renseigné')}")
        print(f"    SIREN : {entreprise.get('siren', 'Non renseigné')}")
        print(f"    Adresse : {siege.get('adresse', 'Non renseignée')}")
        print(f"    Activité NAF : {entreprise.get('activite_principale', 'Non renseignée')}")
        print(f"    Nature juridique : {entreprise.get('nature_juridique', 'Non renseignée')}")
        print(f"    Catégorie : {entreprise.get('categorie_entreprise', 'Non renseignée')}")
        print(f"    Tranche effectif (entreprise) : "
              f"{entreprise.get('tranche_effectif_salarie', 'Non renseignée')}")
        print(f"    Établissements : {entreprise.get('nombre_etablissements', 'Non renseigné')}")
        print(f"    État : {entreprise.get('etat_administratif', 'Non renseigné')}")

        for parent in dirigeants_personnes_morales(entreprise):
            print(f"    Dirigée par : {parent['denomination']} "
                  f"(SIREN {parent['siren']}) - {parent['qualite']}")

        auditeurs = [c["denomination"] for c in commissaires_aux_comptes(entreprise)]

        if auditeurs:
            print(f"    Commissaires aux comptes : {', '.join(auditeurs)}")

        print()


def choisir_resultat(resultats):
    """Demande un numéro jusqu'à obtenir une réponse valide.
    Retourne l'entreprise choisie, ou None si l'utilisateur tape 0."""

    while True:

        choix = input(
            "Numéro de l'entreprise à sélectionner (0 pour annuler) : "
        ).strip()

        if not choix.isdigit():
            print("[ERREUR] Tape un numéro.")
            continue

        index = int(choix)

        if index == 0:
            return None

        if 1 <= index <= len(resultats):
            return resultats[index - 1]

        print(f"[ERREUR] Choisis un numéro entre 1 et {len(resultats)}.")


# ==================================================
# SAUVEGARDE
# ==================================================

def construire_fiche(entreprise, nom_recherche):
    """Fiche minimisée : on ne garde que ce qui sert à la qualification.
    La réponse brute de l'API n'est plus enregistrée."""

    siege = entreprise.get("siege") or {}

    # "O" = diffusible ; "P" = partiellement diffusible (données personnelles
    # masquées / opposition). Dans ce dernier cas, aucun nom de personne.
    statut_diffusion = entreprise.get("statut_diffusion")

    diffusion_restreinte = statut_diffusion not in (None, "O")

    return {
        "nom_recherche": nom_recherche,

        "identite": {
            "nom_officiel": entreprise.get("nom_raison_sociale"),
            "nom_complet": entreprise.get("nom_complet"),
            "sigle": entreprise.get("sigle"),
            "siren": entreprise.get("siren"),
            "nature_juridique": entreprise.get("nature_juridique"),
            "categorie_entreprise": entreprise.get("categorie_entreprise"),
            "activite_naf": entreprise.get("activite_principale"),
            "date_creation": entreprise.get("date_creation"),
            "etat_administratif": entreprise.get("etat_administratif"),
            "nombre_etablissements": entreprise.get("nombre_etablissements"),
            "nombre_etablissements_ouverts": entreprise.get("nombre_etablissements_ouverts"),
            "statut_diffusion": statut_diffusion,
        },

        # Effectif au niveau de l'ENTREPRISE (et non du seul siège).
        "effectif": {
            "tranche": entreprise.get("tranche_effectif_salarie"),
            "annee": entreprise.get("annee_tranche_effectif_salarie"),
            "nature": "tranche INSEE (code), pas un effectif exact",
        },

        "siege": {
            "siret": siege.get("siret"),
            "adresse": siege.get("adresse"),
            "code_postal": siege.get("code_postal"),
            "commune": siege.get("libelle_commune"),
        },

        "structure": {
            "dirigeants_personnes_morales": dirigeants_personnes_morales(entreprise),
            "commissaires_aux_comptes": commissaires_aux_comptes(entreprise),
        },

        "dirigeants_personnes_physiques": (
            [] if diffusion_restreinte else dirigeants_personnes_physiques(entreprise)
        ),

        # Dictionnaire {année: {"ca": ..., "resultat_net": ...}} quand publié.
        "finances": entreprise.get("finances") or {},

        "source": {
            "nom": "API Recherche d'Entreprises",
            "url": "https://recherche-entreprises.api.gouv.fr",
            "date_collecte": datetime.now(timezone.utc).isoformat(),
            "fiabilite": "A - Source administrative publique"
        },
    }


def sauvegarder_entreprise(entreprise, nom_recherche):

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    fiche = construire_fiche(entreprise, nom_recherche)

    siren = entreprise.get("siren") or nettoyer_nom(nom_recherche)

    chemin = OUTPUT_DIR / f"{siren}.json"

    with open(chemin, "w", encoding="utf-8") as fichier:
        json.dump(fiche, fichier, ensure_ascii=False, indent=4)

    print(f"\n[ENREGISTRE] {chemin}")

    return fiche, chemin


# ==================================================
# FONCTION REUTILISABLE (appelée par main.py)
# ==================================================

def selectionner_entreprise(nom):
    """Recherche, affiche, fait choisir et sauvegarde.
    Retourne la fiche minimisée (dict), ou None si rien n'est sélectionné."""

    print(f"\n[RECHERCHE] {nom}")

    resultats = rechercher_entreprise(nom)

    if not resultats:
        print("[RESULTAT] Aucune entreprise trouvée.")
        return None

    afficher_resultats(resultats)

    entreprise = choisir_resultat(resultats)

    if entreprise is None:
        print("[ANNULATION] Aucune entreprise sauvegardée.")
        return None

    fiche, chemin = sauvegarder_entreprise(entreprise, nom)

    fiche["fichier"] = str(chemin)

    return fiche


# ==================================================
# PROGRAMME PRINCIPAL (test autonome)
# ==================================================

def main():

    print("\n======================================")
    print(" PROSPECTAI - IDENTIFICATION JURIDIQUE")
    print("======================================")

    nom = input("\nNom de l'entreprise ou SIREN à rechercher : ").strip()

    if not nom:
        print("[ERREUR] Nom d'entreprise obligatoire.")
        return

    fiche = selectionner_entreprise(nom)

    if fiche is None:
        return

    print("\n======================================")
    print(" IDENTIFICATION TERMINEE")
    print("======================================")
    print(f"Entreprise : {fiche['identite']['nom_complet']}")
    print(f"SIREN : {fiche['identite']['siren']}")
    print(f"Fichier : {fiche['fichier']}")


if __name__ == "__main__":
    main()
