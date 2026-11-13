"""Comparaison des modèles de score V1 et V2 sur 30 cas de référence.

Lancement (depuis la racine du projet) :
    python -m evaluation.compare_v1_v2

Modèles comparés
- V1 : scoring du pôle Tech (Ryan Annic), grille Potentiel 60 / Opportunité 30 /
       Accessibilité 10. Code copié sans modification dans evaluation/v1_ryan/.
- V2 : scoring du pôle Data (crm/scoring.py), grille officielle Product
       Adéquation 40 / Taille 15 / Innovation 15 / Signaux 20 / Récence 10.

Protocole (sans fuite d'information)
1. Source : givaudan_crm_data.csv (50 clients, 520 interactions). L'ordre des lignes
   sert de chronologie (les horodatages du fichier sont inutilisables).
2. Pour chaque client, la DERNIÈRE affaire conclue (Closed Won ou Closed Lost) est
   la vérité terrain. Elle est retirée de l'historique, ainsi que tout ce qui suit.
3. Les deux modèles notent chaque client avec le seul historique antérieur.
4. 30 cas de référence : 15 affaires gagnées et 15 perdues, tirées avec une graine fixe.
5. Question posée : un score plus élevé annonce-t-il une affaire gagnée ?

Métriques
- AUC : probabilité qu'un client gagné ait un meilleur score qu'un client perdu
  (0,5 = hasard, 1 = parfait).
- Précision@10 : part d'affaires gagnées parmi les 10 clients les mieux notés.
- Écart moyen : score moyen des gagnés moins score moyen des perdus.
- Corrélation de Spearman entre V1 et V2 : les deux modèles classent-ils pareil ?
- Couverture : part de la grille réellement évaluée (V2).

Sorties : evaluation/resultats_v1_v2.csv et evaluation/RESULTATS.md
"""

import csv
import io
import random
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from crm.scoring import calculer_score              # noqa: E402  (V2)
from evaluation.v1_ryan.data import load            # noqa: E402  (V1)
from evaluation.v1_ryan.scoring import score_dataset  # noqa: E402  (V1)

SOURCE = ROOT / "givaudan_crm_data.csv"
SORTIE_CSV = ROOT / "evaluation" / "resultats_v1_v2.csv"
SORTIE_MD = ROOT / "evaluation" / "RESULTATS.md"

COLONNES = [
    "client_id", "division", "category", "region", "is_returning_customer",
    "avg_order_volume_kg", "order_frequency_months", "interaction_timestamp",
    "pipeline_stage", "stakeholder_role", "transcript", "proof_strength", "language",
]
ISSUES = {"Closed Won": 1, "Closed Lost": 0}
NB_CAS = 30
GRAINE = 42


# ------------------------------------------------------------------
# Préparation des cas de référence
# ------------------------------------------------------------------

def lire_crm():
    groupes = defaultdict(list)
    with open(SOURCE, encoding="utf-8-sig", newline="") as f:
        for ligne in csv.DictReader(f):
            if ligne.get("client_id"):
                groupes[ligne["client_id"]].append({c: ligne.get(c, "") for c in COLONNES})
    return groupes


def construire_cas(groupes):
    """Pour chaque client : historique avant sa dernière affaire conclue + issue réelle."""
    cas = []
    for client_id, lignes in sorted(groupes.items()):
        positions = [i for i, l in enumerate(lignes) if l["pipeline_stage"] in ISSUES]
        if not positions or positions[-1] == 0:
            continue  # pas d'issue, ou aucun historique avant elle
        coupe = positions[-1]
        cas.append({
            "client_id": client_id,
            "historique": lignes[:coupe],
            "issue": ISSUES[lignes[coupe]["pipeline_stage"]],
        })
    return cas


def selectionner(cas, nb=NB_CAS):
    """nb cas équilibrés (moitié gagnés, moitié perdus), tirage reproductible."""
    rnd = random.Random(GRAINE)
    gagnes = [c for c in cas if c["issue"] == 1]
    perdus = [c for c in cas if c["issue"] == 0]
    moitie = min(nb // 2, len(gagnes), len(perdus))
    return sorted(rnd.sample(gagnes, moitie) + rnd.sample(perdus, moitie), key=lambda c: c["client_id"])


# ------------------------------------------------------------------
# Les deux modèles
# ------------------------------------------------------------------

def scores_v1(cas):
    """V1 : on donne au code de Ryan un CSV contenant uniquement les historiques tronqués."""
    tampon = io.StringIO()
    ecrivain = csv.DictWriter(tampon, fieldnames=COLONNES)
    ecrivain.writeheader()
    for c in cas:
        ecrivain.writerows(c["historique"])
    prospects = score_dataset(load(tampon.getvalue().encode("utf-8"), "historique.csv"))
    return {p["id"]: p["score"]["total"] for p in prospects}


def scores_v2(cas):
    """V2 : scoring du pôle Data sur les mêmes historiques (aucun signal externe dans le CRM)."""
    resultats = {}
    for c in cas:
        profil = c["historique"][0]
        entreprise = {
            "id": c["client_id"], "nom": c["client_id"], "fictif": 1,
            "division": profil["division"], "categorie": profil["category"],
            "client_existant": int(profil["is_returning_customer"] == "True"),
            "volume_moyen_commande_kg": int(float(profil["avg_order_volume_kg"] or 0)),
            "frequence_commande_mois": int(float(profil["order_frequency_months"] or 0)),
            "chiffre_affaires_meur": None, "annee_ca": None,
            "source": "givaudan_crm_data.csv",
        }
        interactions = [{"etape_pipeline": l["pipeline_stage"], "date": None} for l in c["historique"]]
        score = calculer_score(entreprise, interactions, signaux=[], aujourd_hui=date(2026, 11, 13))
        resultats[c["client_id"]] = (score["score_global"], score["poids_evalues"])
    return resultats


# ------------------------------------------------------------------
# Métriques (sans bibliothèque externe, pour rester lisible)
# ------------------------------------------------------------------

def auc(scores, issues):
    gagnes = [s for s, y in zip(scores, issues) if y == 1]
    perdus = [s for s, y in zip(scores, issues) if y == 0]
    paires = [(g > p) + 0.5 * (g == p) for g in gagnes for p in perdus]
    return sum(paires) / len(paires)


def precision_a_k(scores, issues, k=10):
    meilleurs = sorted(zip(scores, issues), key=lambda x: -x[0])[:k]
    return sum(y for _, y in meilleurs) / k


def rangs(valeurs):
    ordre = sorted(range(len(valeurs)), key=lambda i: valeurs[i])
    r = [0.0] * len(valeurs)
    i = 0
    while i < len(ordre):
        j = i
        while j + 1 < len(ordre) and valeurs[ordre[j + 1]] == valeurs[ordre[i]]:
            j += 1
        for k in range(i, j + 1):
            r[ordre[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def spearman(a, b):
    ra, rb = rangs(a), rangs(b)
    ma, mb = mean(ra), mean(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = (sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb)) ** 0.5
    return num / den if den else 0.0


def ecart(scores, issues):
    return mean(s for s, y in zip(scores, issues) if y == 1) - mean(s for s, y in zip(scores, issues) if y == 0)


def intervalle_auc(scores, issues, tirages=2000):
    """Intervalle de confiance à 95 % de l'AUC par rééchantillonnage (bootstrap)."""
    rnd = random.Random(GRAINE)
    n, valeurs = len(scores), []
    for _ in range(tirages):
        idx = [rnd.randrange(n) for _ in range(n)]
        ys = [issues[i] for i in idx]
        if 0 < sum(ys) < n:
            valeurs.append(auc([scores[i] for i in idx], ys))
    valeurs.sort()
    return valeurs[int(0.025 * len(valeurs))], valeurs[int(0.975 * len(valeurs))]


# ------------------------------------------------------------------
# Programme principal
# ------------------------------------------------------------------

def auc_v1_v2(cas):
    v1 = {k.lower().replace("_", "-"): v for k, v in scores_v1(cas).items()}
    v2 = scores_v2(cas)
    ys = [c["issue"] for c in cas]
    return (auc([v1[c["client_id"].lower().replace("_", "-")] for c in cas], ys),
            auc([v2[c["client_id"]][0] for c in cas], ys))


def robustesse(tous, tirages=200):
    """Le résultat dépend-il du choix des 30 cas ? On refait le tirage 200 fois."""
    global GRAINE
    graine_initiale, resultats = GRAINE, []
    for g in range(tirages):
        GRAINE = g
        resultats.append(auc_v1_v2(selectionner(tous)))
    GRAINE = graine_initiale
    return (mean(r[0] for r in resultats), mean(r[1] for r in resultats),
            sum(r[0] > r[1] for r in resultats) / tirages, auc_v1_v2(tous))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    tous = construire_cas(lire_crm())
    cas = selectionner(tous)

    v1 = scores_v1(cas)
    v2 = scores_v2(cas)

    # Le code de Ryan transforme les identifiants (ex. Client_5591 -> client-5591) : on les rapproche.
    def cle(x):
        return x.lower().replace("_", "-")

    v1 = {cle(k): v for k, v in v1.items()}
    lignes = [{
        "client_id": c["client_id"],
        "issue_reelle": "gagnée" if c["issue"] else "perdue",
        "interactions_historique": len(c["historique"]),
        "score_v1": v1[cle(c["client_id"])],
        "score_v2": v2[c["client_id"]][0],
        "couverture_v2": v2[c["client_id"]][1],
    } for c in cas]

    issues = [c["issue"] for c in cas]
    s1 = [l["score_v1"] for l in lignes]
    s2 = [l["score_v2"] for l in lignes]

    metriques = {
        "AUC": (auc(s1, issues), auc(s2, issues)),
        "IC95 AUC": (intervalle_auc(s1, issues), intervalle_auc(s2, issues)),
        "Précision@10": (precision_a_k(s1, issues), precision_a_k(s2, issues)),
        "Écart gagnés - perdus": (ecart(s1, issues), ecart(s2, issues)),
    }
    rho = spearman(s1, s2)
    top1 = {l["client_id"] for l in sorted(lignes, key=lambda l: -l["score_v1"])[:10]}
    top2 = {l["client_id"] for l in sorted(lignes, key=lambda l: -l["score_v2"])[:10]}
    couverture = mean(l["couverture_v2"] for l in lignes)
    rob_v1, rob_v2, part_v1, (tous_v1, tous_v2) = robustesse(tous)

    with open(SORTIE_CSV, "w", encoding="utf-8-sig", newline="") as f:
        ecrivain = csv.DictWriter(f, fieldnames=list(lignes[0].keys()))
        ecrivain.writeheader()
        ecrivain.writerows(lignes)

    def f2(x):
        return f"{x:.2f}".replace(".", ",")

    md = [
        "# Comparaison V1 / V2 — résultats",
        "",
        f"Généré par `python -m evaluation.compare_v1_v2` · {len(cas)} cas de référence "
        f"({sum(issues)} affaires gagnées, {len(issues) - sum(issues)} perdues) sur {len(tous)} clients disponibles.",
        "",
        "| Métrique | V1 (pôle Tech, 60/30/10) | V2 (pôle Data, grille Product) |",
        "|---|---:|---:|",
        f"| AUC (0,5 = hasard) | {f2(metriques['AUC'][0])} | {f2(metriques['AUC'][1])} |",
        f"| Intervalle de confiance 95 % de l'AUC | {f2(metriques['IC95 AUC'][0][0])} – {f2(metriques['IC95 AUC'][0][1])} "
        f"| {f2(metriques['IC95 AUC'][1][0])} – {f2(metriques['IC95 AUC'][1][1])} |",
        f"| Précision@10 (part de gagnés dans le top 10) | {f2(metriques['Précision@10'][0])} | {f2(metriques['Précision@10'][1])} |",
        f"| Écart de score moyen gagnés − perdus | {f2(metriques['Écart gagnés - perdus'][0])} | {f2(metriques['Écart gagnés - perdus'][1])} |",
        f"| Couverture de la grille | 100 % | {couverture:.0f} % |",
        "",
        f"Accord entre les deux modèles : corrélation de Spearman = {f2(rho)}, "
        f"{len(top1 & top2)} clients en commun dans les deux top 10.",
        "",
        "## Robustesse",
        "",
        f"- Sur 200 tirages différents de 30 cas : AUC moyenne V1 = {f2(rob_v1)}, V2 = {f2(rob_v2)} ; "
        f"V1 fait mieux que V2 dans {part_v1:.0%} des tirages.".replace("%", " %"),
        f"- Sur les {len(tous)} clients : AUC V1 = {f2(tous_v1)}, V2 = {f2(tous_v2)}.",
        "",
        "Lecture : une AUC dont l'intervalle de confiance contient 0,5 ne permet pas de dire que le "
        "modèle fait mieux que le hasard. Le détail par client est dans `resultats_v1_v2.csv`.",
    ]
    SORTIE_MD.write_text("\n".join(md) + "\n", encoding="utf-8")

    print("\n".join(md))


if __name__ == "__main__":
    main()
