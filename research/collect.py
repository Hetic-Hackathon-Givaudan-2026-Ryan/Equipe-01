"""Collecte documentaire publique pour une entreprise (pages officielles + Google Actualités).

Utilisation autonome :
    python research/collect.py

Utilisation depuis un autre script :
    from research import collect
    bilan = collect.main(company="Aroma-Zone", siren="813023843")
"""

import json
import re
import time
import hashlib
import unicodedata

import requests
import feedparser
import trafilatura

from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import quote, urlparse
from urllib import robotparser
from email.utils import parsedate_to_datetime
from bs4 import BeautifulSoup


# =====================================================
# CONFIGURATION
# =====================================================

ROOT_DIR = Path(__file__).resolve().parent.parent

DOCUMENTS_DIR = ROOT_DIR / "data" / "raw" / "said" / "documents"

# Pages officielles, alias et requête d'actualités propres à chaque entreprise.
CONFIG_PATH = Path(__file__).resolve().parent / "entreprises_config.json"

HEADERS = {
    "User-Agent": "ProspectAI/1.0 (HETIC hackathon research project)"
}

TIMEOUT = 25

MAX_ARTICLES = 15

# Pause entre deux requêtes vers des sites tiers (politesse envers les serveurs).
PAUSE_SECONDES = 1

# Mots-clés SANS accents : le texte est lui aussi normalisé sans accents
# avant la comparaison (voir sans_accents()).
# Couvre les deux domaines Givaudan + les types de signaux commerciaux.
KEYWORDS = [
    # Fragrance & Beauty
    "cosmetique", "beaute", "soin", "formulation", "ingredient", "naturel",
    "parfum", "fragrance", "huile essentielle", "capillaire", "maquillage",
    "hygiene", "dermatologique",
    # Taste & Wellbeing
    "alimentaire", "agroalimentaire", "boisson", "arome", "saveur", "gout",
    "nutrition", "recette", "cafe", "chocolat", "cereale", "confiserie",
    # Signaux commerciaux
    "innovation", "recherche", "developpement", "recrutement", "recrute",
    "embauche", "emploi", "investissement", "investit", "levee de fonds",
    "expansion", "international", "ouverture", "magasin", "boutique", "usine",
    "lancement", "lance", "gamme", "produit", "croissance", "chiffre d'affaires",
    "partenariat", "acquisition", "rachat", "fonds",
]


# =====================================================
# NORMALISATION
# =====================================================

def normalize_text(text):
    """Retire le HTML et les espaces superflus."""

    if not text:
        return ""

    text = BeautifulSoup(text, "html.parser").get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def sans_accents(text):
    """'Cosmétique Été' -> 'cosmetique ete' (pour comparer des mots-clés)."""

    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))

    return text.lower()


def slugify(text):
    """'Nestlé France' -> 'nestle-france' (pour les noms de fichiers)."""

    text = re.sub(r"[^a-z0-9]+", "-", sans_accents(text))

    return text.strip("-") or "entreprise"


def contient_mot(texte_normalise, mot):
    """Recherche un mot entier (évite que 'soin' corresponde à 'besoin').
    Accepte le pluriel simple (s / x)."""

    motif = r"\b" + re.escape(mot) + r"[sx]?\b"

    return re.search(motif, texte_normalise) is not None


def is_relevant(title, summary, aliases):
    """Un résultat est pertinent si :
    1. il mentionne l'entreprise (un de ses alias) ;
    2. il contient au moins un mot-clé métier ou signal."""

    texte = sans_accents(normalize_text(f"{title} {summary}"))

    mentionne_entreprise = any(
        contient_mot(texte, sans_accents(alias)) for alias in aliases
    )

    if not mentionne_entreprise:
        return False, "entreprise non mentionnee"

    if not any(contient_mot(texte, kw) for kw in KEYWORDS):
        return False, "aucun mot-cle metier"

    return True, ""


def extract_date(value):

    if not value:
        return None

    try:
        return parsedate_to_datetime(value).isoformat()

    except Exception:
        return None


def decoder_html(response):
    """Retourne le HTML décodé avec le bon encodage.

    Origine du bug d'accents ('SantÃ©') : si le serveur n'indique pas de
    charset, requests suppose ISO-8859-1 pour tout contenu text/*, alors
    que la page est en UTF-8. On détecte alors l'encodage réel."""

    content_type = response.headers.get("Content-Type", "").lower()

    if "charset" not in content_type:
        response.encoding = response.apparent_encoding or "utf-8"

    return response.text


def charger_config(company):
    """Retourne la configuration de l'entreprise, ou une configuration
    par défaut (aucune page officielle, alias = nom saisi)."""

    config = {}

    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, encoding="utf-8") as fichier:
            config = json.load(fichier)

    entreprise = config.get(slugify(company), {})

    return {
        "alias": entreprise.get("alias") or [company],
        "requete_actualites": entreprise.get("requete_actualites") or f'"{company}"',
        "pages_officielles": entreprise.get("pages_officielles", []),
    }


# =====================================================
# RESPECT DU ROBOTS.TXT
# =====================================================

_robots_cache = {}


def autorise_par_robots(url):
    """Lit le robots.txt du site (une fois par site) et dit si on a le droit
    de récupérer cette URL. En cas de doute (robots.txt inaccessible ou
    refusé), on s'abstient : prudence plutôt que contournement."""

    parties = urlparse(url)
    base = f"{parties.scheme}://{parties.netloc}"

    if base not in _robots_cache:

        regles = robotparser.RobotFileParser()

        try:
            reponse = requests.get(base + "/robots.txt", headers=HEADERS, timeout=10)

            if reponse.status_code == 200:
                regles.parse(reponse.text.splitlines())
            elif reponse.status_code == 404:
                regles.allow_all = True      # pas de robots.txt = pas de restriction déclarée
            else:
                regles.disallow_all = True   # 401, 403, 5xx : on s'abstient

        except requests.RequestException:
            regles.disallow_all = True

        _robots_cache[base] = regles

    return _robots_cache[base].can_fetch(HEADERS["User-Agent"], url)


# =====================================================
# SAUVEGARDE
# =====================================================

def save_document(document):
    """Enregistre le document. Retourne True si nouveau, False si doublon.

    Le nom de fichier = entreprise + empreinte de l'URL : la même URL
    donne toujours le même fichier, ce qui évite les doublons entre deux
    exécutions."""

    identifier = hashlib.sha256(document["url"].encode("utf-8")).hexdigest()[:12]

    filename = f"{slugify(document['company'])}_{identifier}.json"

    filepath = DOCUMENTS_DIR / filename

    if filepath.exists():
        print(f"[DEJA PRESENT] {filename}")
        return False

    with open(filepath, "w", encoding="utf-8") as file:
        json.dump(document, file, ensure_ascii=False, indent=4)

    print(f"[ENREGISTRÉ] {filename}")

    return True


def nouveau_bilan():

    return {
        "pages_officielles_ok": 0,
        "pages_officielles_echec": [],
        "rss_total": 0,
        "rss_hors_sujet": 0,
        "articles_complets": 0,
        "resumes_rss": 0,
        "doublons": 0,
        "refus_robots": [],
    }


# =====================================================
# COLLECTE DES PAGES WEB
# =====================================================

def collect_webpage(company, siren, url, source_type, bilan):

    print(f"\n[COLLECTE] {url}")

    if not autorise_par_robots(url):
        print("[ROBOTS.TXT] Le site n'autorise pas cette page : ignorée.")
        bilan["refus_robots"].append(url)
        return

    try:

        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)

        response.raise_for_status()

        if "text/html" not in response.headers.get("Content-Type", ""):
            print("[IGNORÉ] Format non HTML.")
            bilan["pages_officielles_echec"].append(f"{url} (non HTML)")
            return

        html = decoder_html(response)

        content = trafilatura.extract(html, include_comments=False, include_tables=True)

        if not content or len(content) < 100:
            print("[IGNORÉ] Contenu insuffisant.")
            bilan["pages_officielles_echec"].append(f"{url} (contenu insuffisant)")
            return

        metadata = trafilatura.extract_metadata(html)

        document = {
            "company": company,
            "siren": siren,
            "title": metadata.title if metadata else None,
            "url": response.url,
            "media": urlparse(response.url).netloc,
            "source_type": source_type,
            "content_type": "page_complete",
            # Date détectée par trafilatura : peut être une estimation.
            "published_date": metadata.date if metadata else None,
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "content": normalize_text(content),
        }

        if save_document(document):
            bilan["pages_officielles_ok"] += 1
        else:
            bilan["doublons"] += 1

        print(f"[OK] {len(content)} caractères extraits.")

    except requests.RequestException as error:

        # 403 / erreur réseau : on ne contourne pas, on le note : on ne contourne pas, on le note.
        print(f"[ECHEC] {error.__class__.__name__} : {error}")
        bilan["pages_officielles_echec"].append(f"{url} ({error.__class__.__name__})")


# =====================================================
# COLLECTE DES ACTUALITÉS
# =====================================================

def recuperer_article(article_url):
    """Tente de récupérer le texte complet d'un article.

    Les liens Google Actualités pointent vers news.google.com, pas vers le
    média. Si on reste sur un domaine Google, la page obtenue n'est PAS
    l'article (page de redirection / consentement) : on renvoie "".
    """

    if not autorise_par_robots(article_url):
        return "", None

    try:

        response = requests.get(article_url, headers=HEADERS, timeout=TIMEOUT)

        if not response.ok:
            return "", None

        domaine = urlparse(response.url).netloc

        if domaine.endswith("google.com"):
            return "", None

        extracted = trafilatura.extract(
            decoder_html(response), include_comments=False, include_tables=True
        )

        if extracted and len(extracted) >= 300:
            return normalize_text(extracted), response.url

    except requests.RequestException:
        pass

    return "", None


def collect_news(company, siren, config, bilan):

    print("\n========== ACTUALITÉS ==========")

    query = quote(config["requete_actualites"])

    rss_url = (
        "https://news.google.com/rss/search?q=" + query + "&hl=fr&gl=FR&ceid=FR:fr"
    )

    titres_vus = set()

    if not autorise_par_robots(rss_url):
        print("[ROBOTS.TXT] Le flux RSS n'est pas autorisé : actualités non collectées.")
        bilan["refus_robots"].append(rss_url)
        return

    try:

        response = requests.get(rss_url, headers=HEADERS, timeout=TIMEOUT)

        response.raise_for_status()

        feed = feedparser.parse(response.content)

        bilan["rss_total"] = len(feed.entries)

        accepted = 0

        for entry in feed.entries:

            if accepted >= MAX_ARTICLES:
                break

            source_rss = entry.get("source") or {}

            media = source_rss.get("title")

            title = normalize_text(entry.get("title", ""))

            # Google ajoute " - Nom du média" à la fin du titre.
            if media and title.endswith(f" - {media}"):
                title = title[: -len(f" - {media}")].strip()

            summary = normalize_text(entry.get("summary", ""))

            pertinent, raison = is_relevant(title, summary, config["alias"])

            if not pertinent:
                print(f"[HORS SUJET : {raison}] {title[:70]}")
                bilan["rss_hors_sujet"] += 1
                continue

            # Même article relayé plusieurs fois : on ne garde que le premier.
            cle_titre = sans_accents(title)

            if cle_titre in titres_vus:
                bilan["doublons"] += 1
                continue

            titres_vus.add(cle_titre)

            article_url = entry.get("link", "")

            if not article_url:
                continue

            full_content, url_finale = recuperer_article(article_url)

            time.sleep(PAUSE_SECONDES)

            document = {
                "company": company,
                "siren": siren,
                "title": title,
                "url": article_url,
                "url_article": url_finale,
                "media": media,
                "media_url": source_rss.get("href"),
                "source_type": "actualite_rss",
                "content_type": "article_complet" if full_content else "resume_rss",
                "published_date": extract_date(entry.get("published")),
                "collected_at": datetime.now(timezone.utc).isoformat(),
                "content": full_content or summary,
            }

            if save_document(document):
                accepted += 1
                key = "articles_complets" if full_content else "resumes_rss"
                bilan[key] += 1
            else:
                bilan["doublons"] += 1

        print(f"\n[RESULTAT] {accepted} nouvelles actualités retenues "
              f"sur {bilan['rss_total']} résultats RSS.")

    except requests.RequestException as error:

        print(f"[ERREUR RSS] {error}")


# =====================================================
# PROGRAMME PRINCIPAL
# =====================================================

def main(company=None, siren=None):
    """Lance la collecte. Retourne un bilan (dict) exploitable par main.py."""

    if company is None:
        company = input("\nNom de l'entreprise à rechercher : ").strip()

    if not company:
        print("[ERREUR] Nom obligatoire.")
        return None

    DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)

    config = charger_config(company)

    bilan = nouveau_bilan()

    print("\n======================================")
    print(f" PROSPECTAI - COLLECTE : {company}")
    print("======================================")

    if not config["pages_officielles"]:
        print("[INFO] Aucune page officielle configurée pour cette entreprise "
              f"(voir {CONFIG_PATH.name}).")

    for page in config["pages_officielles"]:
        collect_webpage(company, siren, page["url"], page.get("type", "site_officiel"), bilan)
        time.sleep(PAUSE_SECONDES)

    collect_news(company, siren, config, bilan)

    total = len(list(DOCUMENTS_DIR.glob(f"{slugify(company)}_*.json")))

    bilan["documents_total_entreprise"] = total

    print("\n======================================")
    print(" COLLECTE TERMINÉE")
    print("======================================")
    print(f"Pages officielles collectées : {bilan['pages_officielles_ok']}")
    print(f"Pages officielles en échec   : {len(bilan['pages_officielles_echec'])}")
    print(f"Articles complets            : {bilan['articles_complets']}")
    print(f"Résumés RSS seulement        : {bilan['resumes_rss']}")
    print(f"Hors sujet écartés           : {bilan['rss_hors_sujet']}")
    print(f"Doublons ignorés             : {bilan['doublons']}")
    print(f"Refus robots.txt respectés   : {len(bilan['refus_robots'])}")
    print(f"Documents de {company} dans le dossier : {total}")

    return bilan


if __name__ == "__main__":
    main()
