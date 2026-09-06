# SAUVETAGE — 2026-09-01

Deux sessions Claude Code ont perdu leur volume a **11:35:16**, sur une
reinitialisation de la liaison USB-SCSI (`UASPStor` 129). Elles se sont
retrouvees sans disque, sans shell, sans droit d'ecriture — et **ce qu'elles
portaient encore n'etait sur aucun disque** : un contexte de session ne survit
pas a un redemarrage.

Cette session-ci etait sur un autre volume. Elle pouvait encore ecrire et
pousser. Ce repertoire est ce qui a ete sauve.

| fichier | ce qu'il porte |
| --- | --- |
| [`ea-mt5_lot1_mesures.md`](ea-mt5_lot1_mesures.md) | le test d'acceptation des 9 figures, la mesure appariee du stop, le net apres couts, la concentration, le drawdown de sept mois, et deux tests invalides consignes plutot qu'effaces |
| [`sovereign_vidage_complet.md`](sovereign_vidage_complet.md) | le plan courant que son contrat ne designe plus, les 11 echecs de suite et leur fermeture, l'inventaire des 23 gardes dont un orphelin qui ferme son P0, la decomposition Merkle, et six decisions d'arbitrage rejetees |

## Ce que la journee a etabli sur les sauvegardes

> **Deux sauvegardes sur le meme BUS ne sont pas deux sauvegardes.**

La these de depart, de `sovereign`, portait sur l'hote : arbre vif et miroir
sont tombes ENSEMBLE parce qu'ils partageaient la machine. La mesure l'a
resserree d'un cran — ils partageaient le **lien USB** qui a lache, et
l'evenement `disk 11` designe la cle qui portait les miroirs, **a la meme
seconde**.

Seul `origin` a tenu. C'est le seul chemin qui n'etait pas physique.

## La regle de provenance, et pourquoi ces fichiers restent utilisables

Chaque bloc porte sa marque : mesure et commite, mesure et jamais ecrit, ou lu
dans le contexte et non re-verifiable.

> **La classe 1 — affirmer sans interroger le disque — commise en la NOMMANT
> reste exploitable. Commise en silence, elle ne l'est pas.**

`ea-mt5` a donne ses quatre coordonnees de depot en declarant qu'il ne pouvait
plus les relire. La verification les a **toutes** confirmees. C'est la bonne
facon de transmettre ce qu'on ne peut plus verifier.

## A la reprise

Les deux depots sont **PROUVES** clonables — clone reel, `git fsck`, comptage,
puis suppression :

```
sovereign   392 commits, fsck muet, f3a2d523, CLAUDE.md section 30 ligne 1127
ea-mt5      615 commits, fsck muet, 4b8d30c4, checkout COMPLET 18 829 / 18 829
```

⚠️ **Cloner avec `git -c core.longpaths=true`.** Sans ce reglage, le checkout de
`sovereign` echouait a **33 465 fichiers** sur `Filename too long`, alors que
les objets etaient tous presents. Chez `ea-mt5`, ce seul reglage a suffi, sans
meme raccourcir le chemin.

⚠️ **Verifier le COMPTE de fichiers materialises, jamais le code de retour.**
Un clone superficiellement reussi trompe mieux qu'un clone rate : les quatre
fichiers temoins de `sovereign` etaient apparus parce que leurs chemins sont
courts, et un controle porte sur eux seuls aurait rendu un vert franc sur un
arbre incomplet.
