# Comparaison V1 / V2 — résultats

Généré par `python -m evaluation.compare_v1_v2` · 30 cas de référence (15 affaires gagnées, 15 perdues) sur 50 clients disponibles.

| Métrique | V1 (pôle Tech, 60/30/10) | V2 (pôle Data, grille Product) |
|---|---:|---:|
| AUC (0,5 = hasard) | 0,74 | 0,51 |
| Intervalle de confiance 95 % de l'AUC | 0,54 – 0,90 | 0,29 – 0,73 |
| Précision@10 (part de gagnés dans le top 10) | 0,70 | 0,60 |
| Écart de score moyen gagnés − perdus | 4,07 | 1,21 |
| Couverture de la grille | 100 % | 55 % |

Accord entre les deux modèles : corrélation de Spearman = 0,52, 6 clients en commun dans les deux top 10.

## Robustesse

- Sur 200 tirages différents de 30 cas : AUC moyenne V1 = 0,66, V2 = 0,55 ; V1 fait mieux que V2 dans 90 % des tirages.
- Sur les 50 clients : AUC V1 = 0,66, V2 = 0,54.

Lecture : une AUC dont l'intervalle de confiance contient 0,5 ne permet pas de dire que le modèle fait mieux que le hasard. Le détail par client est dans `resultats_v1_v2.csv`.
