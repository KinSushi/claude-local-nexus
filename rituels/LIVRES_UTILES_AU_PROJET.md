# Les livres qui servent DIRECTEMENT ce projet — notes

Établi le 2026-09-03. Deux corpus, adressables par `seek`, coût ~280 jetons la
consultation :

| corpus | contenu | chemin |
| --- | --- | --- |
| code | 16 ouvrages, 2 231 symboles **avec implémentation complète** | `references/livres/code/` |
| livres | 201 ouvrages, 119 977 fragments, 25 thèmes | `D:\Bibliotheque_Ultime_KOS_IA_Qwen_Parse\_index\` |

**Règle qui gouverne ces notes** : les livres sont le PLANCHER, jamais le
plafond (contrat §0.8). Ce qui suit est ancré sur du texte réellement lu ; ce
qui n'est qu'une piste est dit tel quel.

---

## 1. Le livre qui NOMME nos défauts — et que je n'avais jamais ouvert

**Matt Bishop, *Computer Security: Art and Science*, 2ᵉ éd.**
`D:\...\NOYAU TCB\Computer-security-art-and-science-2nd-edition-Matt-Bishop`

Son **chapitre 14, « Principles of Secure Design »**, donne un nom canonique à
quatre des huit défauts trouvés cette nuit — trouvés empiriquement, sans savoir
qu'ils portaient déjà un nom depuis quarante ans.

Texte lu, définition 14-5 :

> *The principle of **complete mediation** requires that **all** accesses to
> objects be checked to ensure that they are allowed.*

| principe (Bishop, ch. 14) | notre défaut |
| --- | --- |
| 14.2.4 **Complete Mediation** | la garde de production médie `Edit`/`Write`, **pas `Bash`** — §35 |
| 14.2.2 **Fail-Safe Defaults** | le refus de suppression qui rendait **code 0** — §31.6 |
| 14.2.8 **Least Astonishment** | « Violations détectées » suivi de « All checks passed! » — §29.2 |
| 14.2.3 **Economy of Mechanism** | deux gardes aux périmètres qui ne se recouvrent pas — §35 |

**Ce que cela change concrètement.** Notre arbitrage sur la garde (§35) cherchait
à « distinguer l'écrivain sanctionné de l'ad hoc ». Bishop reformule le problème :
ce n'est pas une question d'écrivain, c'est que **la médiation est incomplète**.
Un chemin d'accès non médié n'est pas un cas particulier à traiter — c'est la
définition même de la faille.

Le corpus porte aussi *Trusted Computing Platforms* (Smith) et *TCPA technology
in context* (Balacheff) sur les frontières de TCB. **Non lus** ; à ouvrir quand
la question « qu'est-ce qui est dans la base de confiance ici ? » se posera.

---

## 2. Le thème qui vise notre problème central — les contrôles aveugles

`D:\...\Vérification formelle\` — trois ouvrages :

* **Clarke, Grumberg, Peled, *Model Checking*** (l'ouvrage fondateur)
* **Baier, Katoen, *Principles of Model Checking***
* Clarke *et al.*, seconde édition

**Pourquoi c'est notre sujet.** Huit mécanismes vérifient correctement une
propriété qui n'est pas celle qu'ils annoncent. C'est le décalage
*spécification / implémentation*, et c'est l'objet même de ce domaine.

**Piste, NON ANCRÉE.** La notion de *vacuity detection* — une propriété
satisfaite pour une raison qui la vide de sens, par exemple parce que sa
prémisse n'est jamais vraie — décrit exactement `if "[agent/" not in texte` face
à 45 branches nommées autrement. J'ai cherché « vacuously true » dans le
corpus : les occurrences trouvées concernent les automates temporisés, pas la
vacuité de spécification. **Le concept existe dans ce domaine ; je ne l'ai pas
trouvé ancré ici.** À chercher avec d'autres termes avant d'en tirer quoi que
ce soit.

---

## 3. Le fonds Packt — 27 ouvrages, dont sept sur notre architecture exacte

`D:\...\LIVRES_PACKT\`, et les mêmes présents en corpus **code** avec leurs
implémentations.

| ouvrage | ce qu'il apporte, et à quel problème |
| --- | --- |
| **Design Multi-Agent AI Systems Using MCP and A2A** | littéralement notre architecture : MCP, A2A. Le seul du fonds qui traite les deux protocoles ensemble |
| **30 Agents Every AI Engineer Must Build** | son **chapitre 4** porte le disjoncteur à seuil. Déjà employé cette nuit : un agent y a repris les états et transitions plutôt que de les inventer |
| **Building Agentic AI Systems** | boucle agentique, outils, reprise sur échec |
| **Agentic Architectural Patterns for Building Multi-Agent Systems** | patrons multi-agents, RAG, LLMOps, échelle |
| **Context Engineering for Multi-Agent Systems** | notre question du contexte de 1 M par MAP-REDUCE (§110) |
| **Agentic Coding with Claude Code** | l'outil que nous employons, décrit de l'extérieur |
| **Architecting AI Software Systems** | architecture de systèmes d'IA en production |
| **Machine Learning Model Serving Patterns** | déploiement, **surveillance**, accessibilité — notre passerelle LiteLLM |
| **Adversarial AI — Attacks, Mitigations, Defense** | MLSecOps, modélisation de menace. Un agent en a tiré cette nuit la provenance des modèles par empreinte |
| **Agentic AI for Offensive Cybersecurity** | le point de vue de l'attaquant sur un système d'agents — utile contre nos propres gardes |
| **Artificial Intelligence for Cybersecurity** | détection, classification |
| **50 Algorithms Every Programmer Should Know** | le sac à dos, pour la sélection de pool sous contrainte mémoire (§106.2) |

---

## 4. Les thèmes à ouvrir, avec la question qu'ils répondraient

| thème du corpus | notre question ouverte |
| --- | --- |
| `Calcul parallèle & GPU` — *Programming Massively Parallel Processors*, 3 éditions | l'essaim de petits modèles, et le futur GPU dédié (§0 : iGPU partagé aujourd'hui) |
| `Reinforcement learning` — dont *Deep RL Hands-On* | bandits et inférence adaptative pour le routage (§106.2, piste permanente du contrat) |
| `Optimisation`, `Recherche opérationnelle` | sélection de pool, température, ordonnancement — problèmes de recherche sous contrainte résolus à la main aujourd'hui |
| `Architecture logicielle, fiabilité & patterns ML` — *Clean Architecture* | frontières entre nos 46 fichiers de projet et 97 outils portables |
| `Théorie de l'information` | mesure de ce qu'un contexte porte réellement |

---

## 5. Ce que ces notes ne disent pas

Je n'ai lu **entièrement** aucun de ces ouvrages. Ce qui est ancré ci-dessus
tient à deux passages réellement extraits par `seek` : la table du chapitre 14
de Bishop et sa définition 14-5. Tout le reste est un **repérage** — un titre,
un thème, et la question qu'il paraît répondre.

C'est utile et c'est limité, et la différence doit rester visible : un titre
n'est pas une lecture, et le contrat interdit de traiter l'un pour l'autre.

**Le geste qui suit** : avant de concevoir un mécanisme, chercher dans l'index
le chapitre qui porte SON NOM. La nuit vient d'en donner la démonstration —
huit défauts trouvés à la main portaient déjà, pour la moitié, un nom dans un
livre du dépôt.
