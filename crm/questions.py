"""Questions à poser par les commerciaux, générées à partir des données de l'entreprise.

Génération par règles (pas d'IA) : chaque question est déclenchée par un
élément précis de la fiche (catégorie, signal, donnée manquante, étape de
l'affaire, interlocuteur) et indique cet élément dans "base_sur".
Rien n'est inventé : sans élément déclencheur, pas de question.

Chaque question a :
- theme      : découverte | pourquoi maintenant | qualification | avancer l'affaire
- question   : la phrase à poser au client
- objectif   : ce que le commercial cherche à apprendre
- base_sur   : l'élément de la fiche qui justifie la question
- a_qui      : l'interlocuteur à qui la poser (si identifié)
"""


# Questions de découverte par catégorie Givaudan
PAR_CATEGORIE = {
    "Fine Fragrances": [
        "Quelles familles olfactives souhaitez-vous développer dans vos prochaines créations ?",
        "Quelle part de naturalité visez-vous dans vos formules de parfum ?",
    ],
    "Consumer Products": [
        "Sur quels produits (lessive, entretien, hygiène) cherchez-vous à renouveler la signature olfactive ?",
        "Vos clients vous demandent-ils des parfums plus durables ou plus rémanents ?",
    ],
    "Fragrance Ingredients": [
        "Quels ingrédients sont aujourd'hui difficiles à sourcer ou trop coûteux pour vous ?",
        "Recherchez-vous des alternatives biosourcées à certaines molécules ?",
    ],
    "Active Beauty": [
        "Quels bénéfices peau ou cheveux voulez-vous revendiquer sur vos prochains produits ?",
        "Avez-vous besoin d'actifs avec des preuves d'efficacité cliniques ?",
    ],
    "Sweet Goods": [
        "Travaillez-vous sur la réduction du sucre sans perte de goût ?",
        "Quels profils aromatiques vos consommateurs plébiscitent-ils en ce moment ?",
    ],
    "Dairy": [
        "Développez-vous des alternatives végétales aux produits laitiers ?",
        "Rencontrez-vous des difficultés de goût ou de texture sur vos recettes allégées ?",
    ],
    "Beverages": [
        "Quels arômes ou saveurs souhaitez-vous lancer sur vos prochaines boissons ?",
        "Cherchez-vous à passer à des arômes 100 % naturels ?",
    ],
    "Savoury": [
        "Travaillez-vous sur la réduction du sel ou des exhausteurs de goût ?",
        "Développez-vous des recettes végétariennes qui demandent un travail sur le goût umami ?",
    ],
}

# Questions déclenchées par un signal commercial
PAR_SIGNAL = {
    "recrutement": (
        "Vous renforcez vos équipes : quels projets ces nouvelles recrues vont-elles porter ?",
        "Identifier les projets à venir et le bon moment pour proposer un accompagnement.",
    ),
    "lancement_produit": (
        "Pour votre nouvelle gamme, quels sont vos critères de choix d'un partenaire arômes ou parfums ?",
        "Se positionner sur les prochains développements de la gamme.",
    ),
    "investissement": (
        "Votre nouveau site va augmenter vos volumes : comment sécurisez-vous l'approvisionnement en ingrédients ?",
        "Évaluer les nouveaux besoins en volume et la place pour un second fournisseur.",
    ),
    "partenariat_rd": (
        "Votre partenariat de recherche porte sur des ingrédients naturels : où avez-vous encore besoin d'expertise ?",
        "Repérer les manques techniques que Givaudan peut combler.",
    ),
    "expansion": (
        "Sur ce nouveau marché, devez-vous adapter vos produits aux goûts ou à la réglementation locale ?",
        "Proposer l'expertise locale de Givaudan (préférences consommateurs, conformité).",
    ),
    "innovation": (
        "Votre nouvelle formulation brevetée doit-elle être déclinée sur d'autres produits ?",
        "Identifier les déclinaisons où apporter des ingrédients ou des parfums.",
    ),
}

# Questions pour combler une donnée manquante du scoring
PAR_DONNEE_MANQUANTE = {
    "taille": (
        "Quels volumes annuels d'arômes ou de parfums utilisez-vous aujourd'hui ?",
        "Estimer le potentiel économique (critère taille non renseigné).",
    ),
    "innovation": (
        "Quels lancements ou reformulations prévoyez-vous dans les 12 prochains mois ?",
        "Documenter la dynamique d'innovation (aucun signal connu).",
    ),
    "signaux": (
        "Quels sont vos grands projets pour l'année à venir ?",
        "Détecter un événement déclencheur (aucun signal récent connu).",
    ),
    "adequation": (
        "Sur quels marchés et quelles catégories de produits êtes-vous présents ?",
        "Vérifier l'adéquation avec les activités Givaudan.",
    ),
}

# Questions selon l'étape de la dernière interaction
PAR_ETAPE = {
    "Lead": (
        "Comment choisissez-vous aujourd'hui vos fournisseurs d'arômes ou de parfums ?",
        "Comprendre le processus d'achat avant de proposer quoi que ce soit.",
    ),
    "Brief Received": (
        "Quels critères feront gagner une proposition sur ce brief : coût, naturalité, délai, performance ?",
        "Aligner la proposition sur les vrais critères de décision.",
    ),
    "Evaluation/Sampling": (
        "Comment se passe l'évaluation de nos échantillons : panel consommateurs, tests internes, délais ?",
        "Suivre l'évaluation et anticiper les ajustements.",
    ),
    "Negotiation": (
        "Qui doit valider la décision finale, et quel est votre calendrier ?",
        "Sécuriser le processus de décision et la date de signature.",
    ),
    "Closed Won": (
        "Quels autres produits de votre portefeuille pourraient bénéficier du même travail ?",
        "Étendre la collaboration à d'autres gammes.",
    ),
    "Closed Lost": (
        "Qu'est-ce qui a fait la différence lors de votre dernier choix de fournisseur ?",
        "Comprendre la perte pour revenir avec une meilleure offre.",
    ),
}

# Une question ciblée par type d'interlocuteur
PAR_SERVICE = {
    "Direction générale": "Quelles sont vos priorités stratégiques pour les trois prochaines années ?",
    "Recherche & Développement": "Quelles contraintes techniques rencontrez-vous sur vos formulations actuelles ?",
    "Marketing": "Quelles tendances consommateurs voulez-vous capter avec vos prochains produits ?",
    "Achats": "Quels sont vos critères de sélection fournisseur : prix, sécurité d'approvisionnement, RSE ?",
    "Réglementaire": "Quelles évolutions réglementaires vous obligent à reformuler certains produits ?",
}

# Service le plus concerné par chaque type de signal
SERVICE_PAR_SIGNAL = {
    "recrutement": "Recherche & Développement",
    "lancement_produit": "Marketing",
    "investissement": "Achats",
    "partenariat_rd": "Recherche & Développement",
    "expansion": "Marketing",
    "innovation": "Recherche & Développement",
}

AUTRE_DIVISION = {
    "Fragrance & Beauty": "Taste & Wellbeing",
    "Taste & Wellbeing": "Fragrance & Beauty",
}


def generer_questions(entreprise, contacts, signaux, interactions, score):
    """Retourne une liste de questions, sans doublon, les plus utiles d'abord."""

    questions = []

    def ajouter(theme, question, objectif, base_sur, a_qui=None):
        if all(q["question"] != question for q in questions):
            questions.append({
                "theme": theme,
                "question": question,
                "objectif": objectif,
                "base_sur": base_sur,
                "a_qui": a_qui,
            })

    par_service = {c["service"]: f"{c['prenom']} {c['nom']} ({c['fonction']})" for c in contacts}

    # 1. Pourquoi maintenant : un signal récent est le meilleur point d'accroche.
    for signal in sorted(signaux, key=lambda s: s["date_publication"], reverse=True)[:3]:
        modele = PAR_SIGNAL.get(signal["type_signal"])
        if modele:
            ajouter("pourquoi maintenant", modele[0], modele[1],
                    f"Signal du {signal['date_publication']} : {signal['titre']} "
                    f"(fiabilité {signal['fiabilite']})",
                    par_service.get(SERVICE_PAR_SIGNAL.get(signal["type_signal"]))
                    or par_service.get("Direction générale"))

    # 2. Avancer l'affaire : selon la dernière étape connue.
    if interactions:
        derniere = max(interactions, key=lambda i: i["date"] or "")
        modele = PAR_ETAPE.get(derniere["etape_pipeline"])
        if modele:
            ajouter("avancer l'affaire", modele[0], modele[1],
                    f"Dernier échange le {derniere['date']} : étape {derniere['etape_pipeline']}",
                    par_service.get("Achats") or par_service.get("Direction générale"))

    # 3. Découverte : besoins propres à la catégorie.
    for question in PAR_CATEGORIE.get(entreprise["categorie"], []):
        ajouter("découverte", question,
                "Faire émerger un besoin concret en arômes, parfums ou ingrédients.",
                f"Catégorie {entreprise['categorie']} ({entreprise['division']})",
                par_service.get("Recherche & Développement") or par_service.get("Marketing"))

    # 4. Qualification : combler les critères non disponibles du score.
    for critere in score["criteres"]:
        if critere["statut"] == "non_disponible" and critere["critere"] in PAR_DONNEE_MANQUANTE:
            question, objectif = PAR_DONNEE_MANQUANTE[critere["critere"]]
            ajouter("qualification", question, objectif,
                    f"Critère « {critere['critere']} » non disponible dans le score",
                    par_service.get("Direction générale") or par_service.get("Achats"))

    # 5. Une question par interlocuteur identifié.
    for contact in contacts:
        question = PAR_SERVICE.get(contact["service"])
        if question:
            ajouter("découverte", question,
                    f"Comprendre les enjeux du service {contact['service']}.",
                    f"Interlocuteur identifié : {contact['fonction']}",
                    f"{contact['prenom']} {contact['nom']} ({contact['fonction']})")

    # 6. Client existant : ouvrir l'autre division Givaudan.
    if entreprise["client_existant"] and entreprise["division"] in AUTRE_DIVISION:
        autre = AUTRE_DIVISION[entreprise["division"]]
        ajouter("avancer l'affaire",
                f"Au-delà de notre collaboration actuelle, avez-vous des projets côté {autre} ?",
                "Proposer la seconde division Givaudan à un client déjà convaincu.",
                "Client existant de la division " + entreprise["division"],
                par_service.get("Direction générale"))

    return questions
