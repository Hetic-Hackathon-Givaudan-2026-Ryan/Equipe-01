"""Construit la base CRM de démonstration (SQLite) à partir du faux CRM existant.

Lancement (depuis la racine du projet) :
    python -m crm.generate_data

Source : givaudan_crm_data.csv (520 interactions, 50 clients). On garde ses
13 vraies colonnes et on ignore les colonnes vides ajoutées par Excel.
On ajoute des données FICTIVES : noms d'entreprises, contacts, signaux.

Toutes les données générées sont fictives et marquées comme telles :
- e-mails en .example (domaine réservé, aucune vraie boîte possible) ;
- téléphones en 01 99 00 xx xx (plage réservée par l'ARCEP à la fiction).
"""

import csv
import random
import sqlite3

from datetime import date, timedelta
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent

CSV_SOURCE = ROOT_DIR / "givaudan_crm_data.csv"

DB_PATH = ROOT_DIR / "data" / "processed" / "crm_demo.db"

COLONNES_UTILES = [
    "client_id", "division", "category", "region", "is_returning_customer",
    "avg_order_volume_kg", "order_frequency_months", "interaction_timestamp",
    "pipeline_stage", "stakeholder_role", "transcript", "proof_strength", "language",
]

# Graine fixe : on obtient exactement les mêmes données à chaque génération.
GRAINE = 42

PREFIXES = ["Maison", "Laboratoires", "Atelier", "Groupe", "Société", "Compagnie"]
NOMS = [
    "Solenne", "Verdane", "Orelia", "Calistra", "Brumel", "Aurevia", "Nectaris",
    "Lunaé", "Florimond", "Sablon", "Azurine", "Mirabel", "Cendrine", "Opaline",
    "Velours", "Garance", "Ambrelle", "Céleste", "Tilleul", "Marjolaine",
]
SUFFIXES = {
    "Fine Fragrances": "Parfums",
    "Consumer Products": "Hygiène",
    "Fragrance Ingredients": "Ingrédients",
    "Active Beauty": "Cosmétiques",
    "Sweet Goods": "Confiserie",
    "Dairy": "Laitiers",
    "Beverages": "Boissons",
    "Savoury": "Saveurs",
}
PAYS_PAR_REGION = {
    "Europe": ["France", "Allemagne", "Italie", "Espagne", "Suisse"],
    "North America": ["États-Unis", "Canada"],
    "Latin America": ["Brésil", "Mexique", "Argentine"],
    "Asia-Pacific": ["Japon", "Singapour", "Australie", "Inde"],
    "Middle East & Africa": ["Émirats arabes unis", "Maroc", "Afrique du Sud"],
}
PRENOMS = [
    "Camille", "Julien", "Inès", "Thomas", "Léa", "Karim", "Sofia", "Hugo",
    "Amina", "Lucas", "Chloé", "Mehdi", "Emma", "Nathan", "Yasmine", "Paul",
]
NOMS_FAMILLE = [
    "Martin", "Bernard", "Diallo", "Moreau", "Laurent", "Benali", "Rossi",
    "Garcia", "Nguyen", "Lefèvre", "Mercier", "Fontaine", "Haddad", "Roux",
]
FONCTIONS = {
    "Decision-maker": ("Directeur général", "Direction générale"),
    "Technical": ("Responsable R&D formulation", "Recherche & Développement"),
    "Marketing": ("Chef de produit", "Marketing"),
    "Purchasing": ("Acheteur matières premières", "Achats"),
    "Regulatory": ("Responsable affaires réglementaires", "Réglementaire"),
}
SIGNAUX = [
    ("recrutement", "Recrutement d'un responsable formulation",
     "Offre d'emploi publiée pour renforcer l'équipe formulation."),
    ("lancement_produit", "Lancement d'une nouvelle gamme",
     "Annonce d'une nouvelle gamme de produits pour l'année en cours."),
    ("investissement", "Investissement dans un nouveau site de production",
     "Extension des capacités de production annoncée."),
    ("partenariat_rd", "Partenariat de recherche avec un laboratoire",
     "Accord de co-développement sur des ingrédients naturels."),
    ("expansion", "Ouverture d'un nouveau marché",
     "Arrivée annoncée sur un nouveau marché géographique."),
    ("innovation", "Brevet déposé sur une nouvelle formulation",
     "Dépôt de brevet portant sur une formulation plus durable."),
]
RESULTATS_PAR_ETAPE = {
    "Lead": ("Premier échange", "Qualifier le besoin"),
    "Brief Received": ("Brief reçu", "Préparer une proposition"),
    "Evaluation/Sampling": ("Échantillons envoyés", "Recueillir les retours"),
    "Negotiation": ("Négociation en cours", "Finaliser l'offre commerciale"),
    "Closed Won": ("Affaire gagnée", "Planifier le suivi client"),
    "Closed Lost": ("Affaire perdue", "Relancer dans six mois"),
}


SCHEMA = """
CREATE TABLE entreprises (
    id TEXT PRIMARY KEY,
    nom TEXT NOT NULL,
    fictif INTEGER NOT NULL,
    type TEXT NOT NULL,                 -- client | prospect
    division TEXT,
    categorie TEXT,
    region TEXT,
    pays TEXT,
    site_web TEXT,
    client_existant INTEGER,
    volume_moyen_commande_kg INTEGER,
    frequence_commande_mois INTEGER,
    chiffre_affaires_meur REAL,         -- millions d'euros, NULL si inconnu
    annee_ca INTEGER,
    effectif INTEGER,
    source TEXT
);
CREATE TABLE contacts (
    id TEXT PRIMARY KEY,
    entreprise_id TEXT REFERENCES entreprises(id),
    prenom TEXT,
    nom TEXT,
    fonction TEXT,
    service TEXT,
    role_crm TEXT,
    email_professionnel TEXT,
    telephone TEXT,
    source TEXT
);
CREATE TABLE interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entreprise_id TEXT REFERENCES entreprises(id),
    contact_id TEXT REFERENCES contacts(id),
    date TEXT,
    etape_pipeline TEXT,
    role_interlocuteur TEXT,
    compte_rendu TEXT,
    niveau_preuve TEXT,
    langue TEXT,
    resultat TEXT,
    prochaine_action TEXT,
    source TEXT
);
CREATE TABLE signaux (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entreprise_id TEXT REFERENCES entreprises(id),
    type_signal TEXT,
    titre TEXT,
    description TEXT,
    date_evenement TEXT,
    date_publication TEXT,
    source TEXT,
    url TEXT,
    fiabilite TEXT
);
"""


def lire_crm_existant():
    """Lit uniquement les 13 vraies colonnes du CSV."""

    with open(CSV_SOURCE, encoding="utf-8-sig", newline="") as fichier:
        lignes = [
            {colonne: ligne.get(colonne, "") for colonne in COLONNES_UTILES}
            for ligne in csv.DictReader(fichier)
        ]

    return [l for l in lignes if l["client_id"]]


def slug(texte):

    remplacements = str.maketrans("éèêëàâîïôöûüç", "eeeeaaiioouuc")

    return "".join(c for c in texte.lower().translate(remplacements) if c.isalnum())


def generer():

    rnd = random.Random(GRAINE)
    aujourd_hui = date.today()

    lignes = lire_crm_existant()

    par_client = {}
    for ligne in lignes:
        par_client.setdefault(ligne["client_id"], []).append(ligne)

    noms_utilises = set()
    entreprises, contacts, interactions, signaux = [], [], [], []

    for client_id, historique in sorted(par_client.items()):

        profil = historique[0]

        # Nom fictif unique, cohérent avec la catégorie
        while True:
            nom = (f"{rnd.choice(PREFIXES)} {rnd.choice(NOMS)} "
                   f"{SUFFIXES.get(profil['category'], '')}").strip()
            if nom not in noms_utilises:
                noms_utilises.add(nom)
                break

        # Les dates sont régénérées ici pour connaître la DERNIÈRE étape.
        dates = sorted(aujourd_hui - timedelta(days=rnd.randint(1, 540)) for _ in historique)
        derniere_etape = historique[-1]["pipeline_stage"]

        # Client = déjà client selon le CRM, ou dernière affaire gagnée.
        # Sinon c'est un prospect en cours de pipeline.
        client_existant = (profil["is_returning_customer"] == "True"
                           or derniere_etape == "Closed Won")

        # Une partie des CA / effectifs est volontairement inconnue (NULL)
        # pour montrer que le scoring ne pénalise pas une donnée absente.
        connu = rnd.random() < 0.7
        volume = int(profil["avg_order_volume_kg"] or 0)

        entreprises.append({
            "id": client_id,
            "nom": nom,
            "fictif": 1,
            "type": "client" if client_existant else "prospect",
            "division": profil["division"],
            "categorie": profil["category"],
            "region": profil["region"],
            "pays": rnd.choice(PAYS_PAR_REGION.get(profil["region"], ["Inconnu"])),
            "site_web": f"https://www.{slug(nom)}.example",
            "client_existant": int(client_existant),
            "volume_moyen_commande_kg": volume,
            "frequence_commande_mois": int(profil["order_frequency_months"] or 0),
            "chiffre_affaires_meur": round(volume * rnd.uniform(0.02, 0.08), 1) if connu else None,
            "annee_ca": 2025 if connu else None,
            "effectif": int(volume * rnd.uniform(0.1, 0.6)) if connu else None,
            "source": "Données fictives de démonstration (dérivées de givaudan_crm_data.csv)",
        })

        # Un contact fictif par rôle présent dans l'historique
        contact_par_role = {}
        for role in sorted({h["stakeholder_role"] for h in historique}):
            prenom, nom_famille = rnd.choice(PRENOMS), rnd.choice(NOMS_FAMILLE)
            fonction, service = FONCTIONS.get(role, (role, role))
            contact_id = f"{client_id}-{role[:3].upper()}"
            contact_par_role[role] = contact_id
            contacts.append({
                "id": contact_id,
                "entreprise_id": client_id,
                "prenom": prenom,
                "nom": nom_famille,
                "fonction": fonction,
                "service": service,
                "role_crm": role,
                "email_professionnel": f"{slug(prenom)}.{slug(nom_famille)}@{slug(nom)}.example",
                "telephone": f"+33 1 99 00 {rnd.randint(10, 99)} {rnd.randint(10, 99)}",
                "source": "Contact fictif de démonstration",
            })

        # Les dates du CSV sont inutilisables (toutes à "08:59.8") :
        # elles ont été réparties plus haut sur les 18 derniers mois.
        for jour, h in zip(dates, historique):
            resultat, action = RESULTATS_PAR_ETAPE.get(h["pipeline_stage"], ("", ""))
            interactions.append({
                "entreprise_id": client_id,
                "contact_id": contact_par_role.get(h["stakeholder_role"]),
                "date": jour.isoformat(),
                "etape_pipeline": h["pipeline_stage"],
                "role_interlocuteur": h["stakeholder_role"],
                "compte_rendu": h["transcript"],
                "niveau_preuve": h["proof_strength"],
                "langue": h["language"],
                "resultat": resultat,
                "prochaine_action": action,
                "source": "givaudan_crm_data.csv (date régénérée)",
            })

        # 0 à 5 signaux : certaines entreprises n'en ont aucun (cas réel fréquent)
        for type_signal, titre, description in rnd.sample(SIGNAUX, rnd.randint(0, 5)):
            age = rnd.randint(3, 500)
            jour_evenement = aujourd_hui - timedelta(days=age)
            jour_publication = jour_evenement + timedelta(days=rnd.randint(0, min(5, age)))
            signaux.append({
                "entreprise_id": client_id,
                "type_signal": type_signal,
                "titre": titre,
                "description": description,
                "date_evenement": jour_evenement.isoformat(),
                "date_publication": jour_publication.isoformat(),
                "source": "Source fictive de démonstration",
                "url": None,
                "fiabilite": rnd.choice(["haute", "moyenne", "faible"]),
            })

    return entreprises, contacts, interactions, signaux


def inserer(conn, table, lignes):

    if not lignes:
        return

    colonnes = list(lignes[0].keys())
    marqueurs = ", ".join("?" for _ in colonnes)

    conn.executemany(
        f"INSERT INTO {table} ({', '.join(colonnes)}) VALUES ({marqueurs})",
        [tuple(l[c] for c in colonnes) for l in lignes],
    )


def main():

    entreprises, contacts, interactions, signaux = generer()

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    # On reconstruit la base de zéro : la génération est reproductible.
    if DB_PATH.exists():
        DB_PATH.unlink()

    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(SCHEMA)
        inserer(conn, "entreprises", entreprises)
        inserer(conn, "contacts", contacts)
        inserer(conn, "interactions", interactions)
        inserer(conn, "signaux", signaux)

    nb_clients = sum(1 for e in entreprises if e["type"] == "client")

    print("Base CRM de démonstration créée :", DB_PATH)
    print(f"  Entreprises  : {len(entreprises)} ({nb_clients} clients, "
          f"{len(entreprises) - nb_clients} prospects) - toutes FICTIVES")
    print(f"  Contacts     : {len(contacts)}")
    print(f"  Interactions : {len(interactions)}")
    print(f"  Signaux      : {len(signaux)}")


if __name__ == "__main__":
    main()
