# ACHÈVEMENT — ce qui reste, mesuré, et comment j'y vais seul

Établi le 2026-09-03 sur mandat de l'opérateur : *« prends les dispositifs et
outils nécessaires pour pouvoir poursuivre seul jusqu'à l'achèvement du projet
et la fin de ta mission. »*

Ce document est la **carte**, pas le plan. Il dit où est le bout, comment on
sait qu'on y est, et par quel geste on avance. Il se relit, il ne se raconte
pas.

---

## 1. Où est le bout — cinq conditions, toutes mesurables

| # | condition | mesure qui la tranche | état au 2026-09-03 |
| --- | --- | --- | --- |
| **A** | le rituel de fin de tour est VERT | `python scripts/nexus_rituel.py` → code 0 | **4 manques** |
| **B** | aucune correction posée sans audit tiers | rubrique 8 remplie sur chaque fiche | **8 fiches sur 15 vides** |
| **C** | la flotte est vidée | `nexus_filet.py` → 0 conflit, 0 commit non récolté | **8 conflits, 5 commits** |
| **D** | aucun contrôle aveugle connu | contre-épreuve par contrôle | **5 sur 12 aveugles** |
| **E** | la vitrine publie | `nexus_vitrine.py --simulation` → 0 blocage | non mesuré |

**On n'a pas fini tant qu'une seule est rouge.** Et « ranger » n'est jamais
« clore » : un sujet déplacé reste ouvert.

---

## 2. Les quatre manques du rituel, et à qui chacun revient

| manque | cause mesurée | à qui |
| --- | --- | --- |
| `travail commite` | `CLAUDE.md` à la racine, **0 octet**, antérieur à la session | **opérateur** — supprimer ou remplir |
| `cablage tenu` | 5 scripts `preuve_seule` ; l'arbitrage §33 dit : 3 outils manuels, `nexus_filet` à câbler, `nexus_quarantaine` à trancher | moi, puis un tiers |
| `outillage tenu` | `ruff SIM105 21→22` et alertes PowerShell | délégable au banc |
| `redaction declaree` | **il vient de rougir pour la première fois** — 52 commits sur 56 sans auteur déclaré | moi |

Le troisième est le plus intéressant : ce contrôle était **aveugle** hier, il
voit aujourd'hui, et il rougit à juste titre.

---

## 3. Les dispositifs dont je dispose, et ce que chacun coûte

| dispositif | coût | ce qu'il fait, mesuré |
| --- | --- | --- |
| banc **cloud**, 19 alias | zéro | 12 tâches en parallèle, 3 inexploitables — le taux normal |
| banc **local**, 55 modèles | zéro, privé | lent (2 servis à la fois), mais aucun octet ne sort |
| agents **Sonnet** en worktree | facturé | seuls capables de rejouer une épreuve et de manipuler git |
| `nexus_filet.py` | zéro | voit les 45 worktrees, refuse les suppressions, dit ce qu'il écarte |
| `nexus_appliquer.py` | zéro | vérifie l'unicité de l'ancre et la syntaxe **avant** d'écrire |
| corpus de livres | ~280 jetons | 217 ouvrages ; Bishop nomme quatre de nos défauts |
| `bespoke-minicheck` | zéro | **en installation** — juge si une affirmation est soutenue par un document |

---

## 4. Les trois règles qui me contraignent, et je les tiens

1. **J'applique, donc je n'audite pas.** Poser un correctif est une décision :
   quoi appliquer, quoi retirer. Elle appartient au temps 2. Tout ce que je
   pose part en file d'audit tiers.
2. **Je ne dépasse le livre que sur une mesure.** Ce qui n'est ni dans le livre
   ni dans une mesure se classe `NON VÉRIFIÉ` et ne s'écrit pas.
3. **Un contrôle vert ne se questionne pas** — donc je le confronte à un cas
   qui doit le faire rougir, ou je ne le crois pas.

---

## 5. Ce que la nuit a appris, et qui gouverne la suite

**Quatorze mécanismes** ont été confrontés à un cas qui aurait dû les faire
échouer. **Aucun n'a échoué.** Aucun n'était faux ligne à ligne : tous
répondaient à côté de la question qu'ils portaient en titre.

> On a mesuré ce qui était facile à mesurer, pas ce qu'on voulait savoir.

Et **trois fois**, j'ai annoncé un chiffre plus gros que le vrai — 14 travaux
condamnés pour 6, 71 fichiers pour 10, 8 contrôles pour 5. Le sens de l'erreur
est constant. **Une exagération n'est pas un hasard de calcul, c'est une
pente**, et elle se corrige par une mesure, jamais par de la prudence.

---

## 6. L'ordre de marche

1. **Vider la file d'audit** — 8 fiches sans rubrique 8, 4 correctifs posés.
   C'est la condition B, et rien ne se ferme sans elle.
2. **Fermer les manques du rituel** qui me reviennent (câblage, rédaction).
3. **Écrire la contre-épreuve par contrôle** — le seul remède commun aux cinq
   contrôles aveugles. Un correctif par contrôle ne protège pas du suivant.
4. **Récolter ou jeter la flotte** — 8 conflits, 5 commits, 13 vides.
5. **Mesurer la vitrine**, en dernier : elle ne publie que si tout le reste est
   sain, et c'est le seul geste irréversible.

**Ce qui revient à l'opérateur, et que je ne trancherai pas seul** : le
`CLAUDE.md` vide, l'assomption des 853 lignes facturées (`nexus_loi1
--reference`), et la rigueur voulue sur l'écriture en production (§35).
