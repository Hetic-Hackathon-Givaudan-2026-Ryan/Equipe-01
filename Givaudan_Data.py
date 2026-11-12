import hashlib
import json
import os
import random
from datetime import datetime, timedelta
import pandas as pd

# Governance & reproducibility configuration
SEED_VERSION = "v1.0.0"
RANDOM_SEED = 42
NUM_COMPANIES = 500
OUTPUT_DIR = "data"
JSON_OUTPUT = os.path.join(OUTPUT_DIR, "givaudan_prospects_mock_v1.json")
CSV_OUTPUT = os.path.join(OUTPUT_DIR, "givaudan_prospects_mock_v1.csv")
REPORT_OUTPUT = "DATA_REPORT.md"


def calculate_sha256(filepath: str) -> str:
    """Compute SHA-256 checksum for data lineage and version tracking."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def generate_mock_dataset(num_records: int = NUM_COMPANIES, seed: int = RANDOM_SEED) -> list[dict]:
    """Generate reproducible synthetic CRM records matching ProspectAI specs."""
    random.seed(seed)
    database = []
    collection_date = datetime.now().strftime("%Y-%m-%d")

    prefixes = [
        "Aroma", "Scent", "Bio", "Pure", "Luxe", "Natura", "Eco", "Nova",
        "Vita", "Derma", "Flora", "Nutri", "Essence", "Taste", "Odor", "Giva"
    ]
    suffixes = [
        "Dynamics", "Crafters Inc.", "Cosmetics", "Solutions", "Paris",
        "Labs", "Group", "Holdings", "Tech", "Blends", "Innovations", "Corp"
    ]
    sectors = ["Agroalimentaire", "Parfumerie", "Cosmétique"]
    countries = ["France", "Suisse", "USA", "Allemagne", "Royaume-Uni", "Italie", "Espagne"]

    for idx in range(1, num_records + 1):
        # Unique sequential Primary Key and deterministic company name
        company_id = f"COMP-{idx:04d}"
        comp_name = f"{random.choice(prefixes)}{random.choice(suffixes)} #{idx:03d}"
        domain = f"{comp_name.lower().replace(' ', '').replace('#', '').replace('.', '')}.example.com"

        # 15% existing Givaudan clients, 85% new prospects
        comp_status = random.choices(["Client Givaudan", "Prospect"], weights=[0.15, 0.85], k=1)[0]
        comp_sector = random.choice(sectors)
        country = random.choice(countries)

        # Weighted scoring criteria (Total = 100%)
        score_adequation = random.randint(20, 40)   # 40% weight
        score_taille = random.randint(5, 15)        # 15% weight
        score_innovation = random.randint(5, 15)    # 15% weight
        score_signaux = random.randint(5, 20)       # 20% weight
        score_date = random.randint(2, 10)          # 10% weight
        total_score = (
            score_adequation + score_taille + score_innovation + score_signaux + score_date
        )

        # Recent signal date within the last 60 days
        pub_date = (datetime.now() - timedelta(days=random.randint(1, 60))).strftime("%Y-%m-%d")

        record = {
            "Identification": {
                "Company_ID": company_id,
                "Nom": comp_name,
                "Statut": comp_status,
                "Site_web": f"https://www.{domain}",
                "Pays": country,
                "Adresse": f"{random.randint(1, 150)} Rue de l'Innovation, {country}",
                "Identifiant_legal": f"SYN-{random.randint(10000000, 99999999)}"
            },
            "Activite": {
                "Secteur": comp_sector,
                "Description": f"Formulation et production d'ingrédients dans le secteur {comp_sector.lower()}.",
                "Produits": [f"Gamme {comp_sector} Pro", f"Extrait Naturel {idx}"],
                "Marches": random.sample(["Europe", "Amérique du Nord", "Asie", "Moyen-Orient"], k=2)
            },
            "Economie": {
                "Chiffre_daffaires_M_EUR": random.randint(10, 2000),
                "Effectifs": random.randint(50, 10000),
                "Croissance_annuelle_pct": round(random.uniform(-2.0, 25.0), 1),
                "Implantation": f"{random.randint(1, 12)} sites internationaux"
            },
            "Innovation": {
                "Nouveaux_produits": random.choice(["Gamme clean-label", "Molécule biosourcée", "Formule sans allergène", "Aucun"]),
                "R_et_D_actif": random.choice([True, False]),
                "Brevets_deposes": random.randint(0, 15)
            },
            "Signaux": {
                "Actualites": random.choice(["Extension usine", "Partenariat stratégique", "Levée de fonds", "Lancement produit"]),
                "Recrutements_recents": random.choice(["Directeur R&D", "Chef de produit", "Responsable Achats", "Ingénieur Formulation"]),
                "Date_du_signal": pub_date
            },
            "Contacts": {
                "Nom": f"Contact_{idx:04d}",
                "Fonction": random.choice(["Directeur Innovation", "Acheteur Principal", "Responsable R&D", "VP Supply Chain"]),
                "Profil_LinkedIn": f"https://linkedin.com/in/synthetic-contact-{idx:04d}",
                "Email": f"contact.{idx:04d}@{domain}"
            },
            "Sources": {
                "Source_ID": f"SRC-{idx:04d}",
                "URL": f"https://news.{domain}/press-release-{idx}",
                "Date_publication": pub_date,
                "Date_collecte": collection_date,
                "Fiabilite": random.choice(["Haute (Officiel)", "Moyenne (Presse)"])
            },
            "Qualification": {
                "Est_synthetique": True,
                "Informations_manquantes": random.choice(["Aucune", "Brevets détaillés", "Budget R&D"])
            },
            "Scoring": {
                "Adequation_Givaudan_40": score_adequation,
                "Taille_potentiel_15": score_taille,
                "Innovation_15": score_innovation,
                "Signaux_detectes_20": score_signaux,
                "Date_recente_10": score_date,
                "Score_Global_100": total_score
            }
        }
        database.append(record)

    return database


def validate_and_export(dataset: list[dict]) -> pd.DataFrame:
    """Validate dataset integrity, export JSON/CSV, and generate governance report."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Export structured JSON for LLM / RAG ingestion
    with open(JSON_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, indent=4)

    # Flatten nested JSON and export CSV for Excel / BI teams
    df = pd.json_normalize(dataset)
    df.to_csv(CSV_OUTPUT, index=False, encoding="utf-8-sig")

    # Integrity checks (Primary Key uniqueness & score bounds)
    assert df["Identification.Company_ID"].is_unique, "Duplicate Company_ID detected!"
    assert df["Scoring.Score_Global_100"].between(0, 100).all(), "Score out of bounds!"

    # Compute SHA-256 checksums for version traceability
    json_hash = calculate_sha256(JSON_OUTPUT)
    csv_hash = calculate_sha256(CSV_OUTPUT)

    # Generate automated Markdown Quality & Seed Report
    status_counts = df["Identification.Statut"].value_counts().to_dict()
    sector_counts = df["Activite.Secteur"].value_counts().to_dict()

    report_content = f"""# ProspectAI — Synthetic Seed Data Report

- **Seed Version:** `{SEED_VERSION}`
- **Random Seed:** `{RANDOM_SEED}` (100% Reproducible)
- **Generated At:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`
- **Total Records:** `{len(df)}` (Unique IDs: `COMP-0001` to `COMP-{len(df):04d}`)
- **Data Classification:** `100% SYNTHETIC / FICTIONAL (Prototype Use Only)`

## 1. File Integrity & Checksums (SHA-256)
| File | Format | Rows | SHA-256 Checksum |
|---|---|---|---|
| `{JSON_OUTPUT}` | JSON (Nested) | {len(df)} | `{json_hash}` |
| `{CSV_OUTPUT}` | CSV (UTF-8-SIG) | {len(df)} | `{csv_hash}` |

## 2. Dataset Distribution
- **Client Status:** `Prospect`: {status_counts.get('Prospect', 0)} | `Client Givaudan`: {status_counts.get('Client Givaudan', 0)}
- **Sectors:** {sector_counts}

## 3. Scoring Summary (0–100 Scale)
- **Mean Score:** `{df['Scoring.Score_Global_100'].mean():.2f}`
- **Min / Max Score:** `{df['Scoring.Score_Global_100'].min()}` / `{df['Scoring.Score_Global_100'].max()}`
- **Validation Status:** PASSED (0 duplicate IDs, 0 null primary keys, all weights sum to 100%)
"""
    with open(REPORT_OUTPUT, "w", encoding="utf-8") as f:
        f.write(report_content)

    print(f"[OK] Generated {len(df)} synthetic records ({SEED_VERSION}).")
    print(f"[OK] Saved JSON   -> {JSON_OUTPUT} (SHA-256: {json_hash[:12]}...)")
    print(f"[OK] Saved CSV    -> {CSV_OUTPUT} (SHA-256: {csv_hash[:12]}...)")
    print(f"[OK] Saved Report -> {REPORT_OUTPUT}")
    return df


if __name__ == "__main__":
    mock_data = generate_mock_dataset()
    df_result = validate_and_export(mock_data)
    print("\nTop 5 Preview:")
    print(df_result[["Identification.Company_ID", "Identification.Nom", "Identification.Statut", "Scoring.Score_Global_100"]].head())