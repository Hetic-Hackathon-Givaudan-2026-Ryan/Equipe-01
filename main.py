"""ProspectAI - orchestrateur : identification juridique + collecte documentaire.

Lancement (depuis la racine du projet, venv activé) :
    python main.py

Ce programme N'EST PAS encore le pipeline complet : il ne fait ni
l'extraction IA, ni le scoring, ni le remplissage des CSV.
"""

import sys

from research.company_lookup import selectionner_entreprise
from research import collect


def demander_oui_non(question):

    return input(f"{question} (o/n) : ").strip().lower() in ("o", "oui", "y")


def main():

    # Force l'affichage UTF-8 des accents dans la console Windows.
    sys.stdout.reconfigure(encoding="utf-8")

    print("\n======================================")
    print(" PROSPECTAI - IDENTIFICATION + COLLECTE")
    print("======================================")

    nom = input("\nNom de l'entreprise : ").strip()

    if not nom:
        print("[ERREUR] Nom obligatoire.")
        return

    # Étape 1 : entité juridique (choix humain, jamais automatique)
    fiche = selectionner_entreprise(nom)

    siren = None

    if fiche is None:
        if not demander_oui_non("Continuer la collecte SANS entité juridique ?"):
            print("[ARRET] Rien n'a été collecté.")
            return
    else:
        siren = fiche["identite"]["siren"]

    # Étape 2 : collecte documentaire (le nom saisi sert de nom de marque)
    bilan = collect.main(company=nom, siren=siren)

    # Étape 3 : bilan
    print("\n======================================")
    print(" BILAN PROSPECTAI")
    print("======================================")
    print(f"Marque recherchée : {nom}")

    if fiche:
        print(f"Entité juridique  : {fiche['identite']['nom_complet']} (SIREN {siren})")
        print(f"Fiche identité    : {fiche['fichier']}")
    else:
        print("Entité juridique  : non sélectionnée")

    if bilan:
        for echec in bilan["pages_officielles_echec"]:
            print(f"Page non collectée : {echec}")

        print(f"Documents collectés pour {nom} : {bilan['documents_total_entreprise']}")

    print("\nÉtapes NON réalisées à ce stade : analyse IA, signaux, contacts, "
          "scoring, alimentation des CSV, dossier final.")


if __name__ == "__main__":
    main()
