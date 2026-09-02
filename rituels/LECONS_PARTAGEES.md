# Leçons partagées — les trois dépôts, mesurées le 2026-09-02

> **Fichier destiné aux trois sessions**, à lire directement :
> `C:\local-llm-docker\rituels\LECONS_PARTAGEES.md`
>
> Chaque entrée porte **la mesure qui l'a établie**, jamais le seul remède. Règle née d'un
> incident du jour : un remède transmis sans sa mesure a failli être appliqué là où il n'avait
> rien à réparer — et *un correctif qui ne casse rien et ne répare rien est le plus difficile à
> détecter de tous : il se coche.*

---

## 1. LES CLASSES D'ERREUR — prendre les classes, jamais la liste

Le dépôt EA MT5 tient **148 incidents gravés**. Une liste de 148 ne se relit pas avant chaque
geste ; **la poignée de classes dont ils sont les instances, si.**

| classe | ce qui se produit | ce qui la fait tomber |
| --- | --- | --- |
| **★ Instrument répondant à la question VOISINE** | chiffre exact, rapide, sans erreur — et faux | **énoncer la question à laquelle il répond RÉELLEMENT, la comparer mot pour mot à celle voulue** |
| **Affirmer un état DÉDUIT** | « c'est fait » sans l'avoir mesuré dans le tour | la commande d'état AVANT la phrase |
| **Frontière donnée / commande** | le shell exécute ou mutile un texte technique | entrée par FICHIER, jamais par argument shell |
| **Garde au mauvais niveau** | la règle ne couvre que le périmètre où on a pensé à la mettre | la poser au **point de passage obligé** |
| **Défaut fail-open** | une branche non prévue passe car le défaut est « autoriser » | **refuser en bas de fonction** |
| **Test qui ENCODE le bug** | une suite verte prouve que le défaut est intentionnel | à chaque correction de garde, relire le test qui la déclarait correcte |
| **Composant vérifié, EFFET non vérifié** | le code existe, le bloc n'est jamais atteint | preuve = **effet final observable** |
| **Témoin inexistant à l'exécution** | `6 passed, 20 errors` lu comme « 6 verts » | **un test qui ERREUR n'échoue pas : il n'existe pas** |
| **Vide lu comme panne** | un silence et un succès s'écrivent pareil | contre-épreuve obligatoire |

★ **La première classe a produit à elle seule cinq incidents entre deux dépôts en une journée.**
C'est de loin la plus rentable à intérioriser.

    l'instrument répondait à                    la question était
    « une RÈGLE correspond-elle ? »             « ce FICHIER est-il ignoré ? »
    « quels paramètres la doc MENTIONNE ? »     « lesquels la fonction ACCEPTE ? »
    « le module est-il TROUVABLE ? »            « s'IMPORTE-t-il ? »
    « le paquet s'importe-t-il ? »              « le sous-module appelé marche-t-il ? »
    « y a-t-il eu 0 citation ? »                « y a-t-il eu 0 invention ? »

⇒ **Le signal qui l'attrape** : *une contradiction avec un document connu est un signal
d'INSTRUMENT, pas de document.* Mesuré — l'annonce « 0 module documenté sur 194 » n'a été
arrêtée que par sa contradiction avec le contrat.

---

## 2. LA TÉTRADE — quatre niveaux, jamais trois *(origine : EA MT5)*

    DOCUMENTÉ / INSTALLÉ / IMPORTABLE (1er niveau) / UTILISABLE (le chemin réellement appelé)
    + INTERPRÉTEUR + DATE, dans le document, jamais dans un en-tête qu'on oublie de lire

**Confirmée quatre fois le même jour, sur quatre matières indépendantes :**

    import arch          OK  ->  arch.univariate.GARCH      OSError          (EA MT5)
    find_spec('curses')  OK  ->  import_module('curses')    ModuleNotFound   (Nexus)
    fragment indexé      OK  ->  champ `texte` vide, contenu dans `implementation`  (Nexus)
    signature(run)       OK  ->  27 paramètres derrière `**kwargs`           (Nexus)

⚠️ **La quatrième mord sur l'introspection elle-même**, qui était le remède proposé pour la
deuxième. **Aucun instrument n'est exempt : chacun répond au niveau où on l'interroge.**

---

## 3. DEUX QUESTIONS AVANT DE FAIRE CONFIANCE À UNE EXTRACTION

1. **Cette page DÉCRIT-elle l'objet, ou le RACONTE-t-elle ?** *(EA MT5)* — scrapée du web,
   `inspect` est obligatoire ; générée par introspection, la regex relit déjà l'objet.
   ⇒ **Une fiche qui ne déclare pas sa provenance ne permet pas de savoir si on peut lui
   appliquer une regex.**
2. **L'objet RELAIE-t-il ?** *(Nexus)* — `**kwargs`, `*args`, décorateur, `functools.wraps`,
   héritage. **Si oui, aucune lecture de premier niveau ne suffit, quelle que soit la
   provenance.**

    inspect.signature(subprocess.run)                  6 paramètres
    | inspect.signature(subprocess.Popen.__init__)    33 paramètres

★ **Et les deux sources ne se remplacent pas** : *`inspect` ne rend que ce que le CODE porte en
lui ; tout ce qui vit HORS du code lui échappe par construction* — guides, tutoriels, exemples.
Même leçon que regex-vs-`inspect`, un étage plus haut.

---

## 4. LE PYTHON PUR LIT LE TEXTE, LA BIBLIOTHÈQUE INTERROGE L'OBJET

    parier sur la FORME du texte              = une hypothèse
    ast / inspect / importlib.metadata        = une mesure

**Ce n'est pas la bibliothèque qui fait mieux la même chose : elle répond à une question que le
texte ne peut pas atteindre.** ⇒ Partout où un dépôt extrait du sens par `re`, demander si une
introspection répond exactement.

★ **Corriger la MATIÈRE bat corriger l'instrument** *(EA MT5)* : régénérer les fiches par
introspection répare à la source pour tous les outils — y compris ceux qui ne sont pas écrits.

---

## 5. LE VIDE LU COMME UNE PANNE, ET L'ÉCHEC QUI REND ZÉRO

| forme | ce qui trompe | remède |
| --- | --- | --- |
| `if` sans `else` | **aucun signal**, ni erreur ni message | un silence ne se diagnostique pas en cherchant une erreur |
| `cmd \| tail` | le pipe rend le code du DERNIER élément | `cmd; echo EXIT=$?` |
| garde derrière `tail` | le `REFUS` s'imprime en TÊTE | lire la sortie d'une garde **entière** |
| backtick mangé par le shell | fragment **vide, sans erreur** *(EA MT5)* | entrée par FICHIER + **fail-close** : une extraction vide LÈVE |
| erreur de syntaxe en fin de commande | **le début ne s'exécute pas non plus** — bash parse tout d'abord | un geste par commande ; ne jamais chaîner écriture et commit |

---

## 6. UN BANC QUI CONFOND INFRASTRUCTURE ET MODÈLE *(origine : EA MT5)*

> **Un banc qui ne distingue pas l'échec d'INFRASTRUCTURE de l'échec de MODÈLE accuse les
> modèles des fautes de l'orchestrateur.**

Colonnes séparées et obligatoires : **A RENDU / N'A PAS RENDU / RENDU HORS FORMAT**, et
**INVENTION ≠ COMPLÉTUDE** — *un modèle à zéro invention qui ne cite qu'un paramètre n'invente
rien et ne sert à rien.*

**Causes d'infrastructure mesurées** : verrou d'inférence **exclusif — il refuse, il n'attend
pas** · troncature silencieuse à 3 372 jetons · rendu hors format.

⚠️ **Mémoire et verrou sont deux ressources distinctes.** « 3,4 Go pour dix modèles sur 22,3 Go
libres » prouve la première et ne dit rien de la seconde. **La preuve du parallélisme est la
FORME DES DURÉES** : dix appels de 104 à 245 s pour un mur de 245 s — sérialisés, le mur aurait
valu leur somme, 1 614 s.

---

## 7. LES CORPUS — ce que chacun ouvre, et ce qu'il DÉCLARE OMETTRE

| dépôt | matière | à prendre chez lui |
| --- | --- | --- |
| **Nexus** | 24 livres, 20 304 fragments, dont **7 sur les agents IA** (2 590) · 63 paquets · stdlib 267 | un chapitre à **2 914 octets sur 26 M**, sans modèle |
| **EA MT5** | ~102 ouvrages pré-mâchés · 2 181 fichiers de doc **introspectés** · 148 erreurs gravées | `unites_atomiques.tsv` portant **le numéro de page PDF** |
| **Sovereign** | 86 corpus, 216 213 symboles | l'en-tête **`RECOUVRE:`** — appariement code↔littérature **à l'ingestion** |

★ **Un pointeur qui énumère ce qu'il CONTIENT sans déclarer ce qu'il OMET transforme une liste
en promesse.** ⇒ Tout corpus porte un `_POINTEUR_CORPUS.md` avec une section **« Ce que ce
corpus NE couvre PAS »**, et **ce pointeur doit être suivi par git** — mesuré : les trois
l'ignoraient, pour trois raisons différentes.

⚠️ **Deux pièges à prendre avec la ressource** : **deux schémas de fragment** (`texte` vs
`implementation`) — un lecteur naïf déclare un rayon entier illisible. Et **aucune numérotation
stable pour citer** : mesuré **0 ligne sur 30**, dans deux dépôts indépendamment. ⇒ **Numéroter
1..N à l'assemblage, faire renvoyer le NUMÉRO.**

---

## 8. LE PROTOCOLE D'ÉCHANGE ENTRE LES TROIS

1. **Transmettre LA MESURE, jamais le remède seul.** *Payé le jour même : un remède juste chez
   l'un n'avait rien à réparer chez l'autre — même symptôme, causes sans rapport.*
2. **Un accord compte pour TROIS observations** seulement si chacun a mesuré **sur ses propres
   données** ; pour UNE s'ils n'ont fait que raisonner. La décorrélation vient des DÉPÔTS.
3. **Un écart entre deux mesures est un progrès, pas un désaccord** — s'il s'explique par une
   variable nommée. *Mesuré : 6 vs 33 chez l'un, 5 vs 5 chez l'autre ; une seule variable les
   sépare.*
4. **Citer les chemins** dans toute commande partagée : espaces et parenthèses cassent toute
   boucle shell non citée.

---

## 9. CE QUE CE FICHIER NE FAIT PAS

⛔ **Il ne mécanise rien.** EA MT5 mesure **10 remèdes mécanisés sur 82 sections** au
2026-08-22 — la fiche en porte **148** aujourd'hui, donc **le ratio réel est pire et personne ne
le connaît**. Soit **~88 % des leçons ne sont tenues par aucun script.**

> Face à toute leçon nouvelle, la question n'est pas « vais-je m'en souvenir ? » mais
> **« QUEL SCRIPT la fait tomber ? »** — un paragraphe documente, seul un contrôle protège.

⚠️ **Trou de garde signalé, non exploité** *(EA MT5)* : `cp` et `Copy-Item` refusés,
**`shutil.copy` passe** — même geste, même fichier, même destination. **La garde protège ceux
qui passent par `cp`, pas la ressource.** Un sous-processus Python est le chemin par lequel on
ne doit jamais élargir ses droits. À tester dans chaque dépôt.


---

## 10. J'AI FAILLI DÉCLARER UNE GARDE AVEUGLE — le test envoyait le mauvais nom

**Mesuré le 2026-09-02, et c'est la sixième occurrence de la classe 1 dans la journée.**

    tool_name: "Task"    ->  EXIT=0, aucun message   « la garde est aveugle ! »
    tool_name: "Agent"   ->  EXIT=2, refus explicite  la garde va très bien

`Task` est le nom **historique** de l'outil ; la garde juge `Agent`, le nom **actuel**.
⇒ **J'allais alerter deux sessions sur un trou qui n'existe pas**, exactement comme un pair a
failli relayer mon faux positif sur `git check-ignore` quelques heures plus tôt.

★ **Ce qui m'a arrêté : la contre-épreuve.** Avant de crier au trou, j'ai demandé *« cette garde
refuse-t-elle QUOI QUE CE SOIT ? »*. Un `exit 0` partout ne dit pas « la garde est aveugle » —
il dit **« ou la garde est aveugle, ou mon invocation est fausse »**, et ces deux-là ne se
distinguent pas sans un cas positif.

> **Une garde muette sur tous les cas est un signal d'INVOCATION avant d'être un signal de
> GARDE.** Le test négatif seul ne sépare jamais les deux.

⚠️ **Et j'ai commis dans le même geste la faute que j'avais inscrite une heure plus tôt** :
`python garde.py | head -3; echo EXIT=$?` — le `$?` est celui de `head`. **Il a fallu refaire
sans pipe pour voir les vrais codes.** Une leçon écrite ne protège pas son auteur le jour même.

---

## 11. L'ÉCART DOC↔CODE SE MESURE DANS LES DEUX SENS *(origine : EA MT5)*

**On parlait tous de « 60 bibliothèques manquantes ». Mesuré par AST sur les imports réels :**

| | EA MT5 | Nexus |
| --- | --- | --- |
| modules externes réellement importés | 26 | **2** (`yaml`, `console_tools`) |
| **[MANQUE_DOC]** appelé, non documenté | **3** | **2** |
| **[DOC_ORPHELINE]** documenté, jamais appelé | 40 | **63 sur 63** |

★ **Trois questions opposées étaient confondues sous un seul mot :**

    « documentée mais absente de l'interpréteur »  ->  de la doc POUR RIEN
    « appelée mais non documentée »                ->  le VRAI manque, et il est PETIT
    « documentée et jamais appelée »               ->  ni l'un ni l'autre

⇒ **Mon « 92 % de bibliothèques absentes » ne mesurait pas une dette — il mesurait une doc
EXCÉDENTAIRE.** Le vrai manque de ce dépôt tient en deux modules. **Un chiffre alarmant qui
répond à la question voisine est plus coûteux qu'une absence de chiffre** : il oriente le
travail vers un chantier qui n'existe pas.


---

## 12. LE DIFFÉRENTIEL — la moitié mécanisable de la classe 1 *(origine : EA MT5)*

**On ne mécanise pas la comparaison de deux ÉNONCÉS — un énoncé n'est pas une valeur.** Mais on
mécanise sa **conséquence observable** : *un instrument qui répond à la question voisine
DISCRIMINE mal.* Et cela, un `==` le voit.

    assert instrument(cas_positif) != instrument(cas_négatif)

> **Tout instrument porte deux témoins : un cas qui DOIT déclencher, un cas qui NE DOIT PAS. Si
> les deux rendent le même verdict, l'instrument ne mesure rien — quel que soit son chiffre.**

**Trois occurrences mesurées le même jour, sur trois matières :**

| instrument | sans témoin on lisait | le différentiel a montré |
| --- | --- | --- |
| `nexus_garde_agent` | « aveugle sur le fork » | **refuse 3 sur 3** — c'était l'invocation |
| sonde de périmètre *(EA MT5)* | « il y a un trou » | **tout passait, témoins compris** |
| banc de petits modèles *(EA MT5)* | « 0 invention partout » | **5 zéros étaient de l'infrastructure** |

★ **Ce qui le rend mécanisable : il teste la DISCRIMINATION, pas la SÉMANTIQUE.** Nul besoin de
savoir ce que l'instrument mesure pour le réfuter.

⚠️ **Limite déclarée par son auteur, et elle est décisive** : le différentiel **ne voit pas un
instrument qui discrimine BIEN sur la mauvaise grandeur**. `git check-ignore` discriminait
parfaitement — entre « une règle correspond » et « aucune ne correspond ». **Il aurait passé ce
test.** ⇒ **Le différentiel élimine la moitié aveugle de la classe, jamais la moitié voisine.**
Celle-là reste au **forward-test** : confronter le verdict à la source par un chemin indépendant.

### 12.1 Et j'ai raté cette mécanisation à mon premier essai

Voulant compter mes épreuves à deux témoins, j'ai écrit une **regex sur le texte** des fonctions.
Verdict : **27 sur 37 non discriminantes, 73 %**.

**Le chiffre est faux, et je l'ai arrêté avant publication** en lisant deux épreuves à la source :
`test_perte_index` porte explicitement *« L'ANTI-CONTRÔLE QUI COMPTE LE PLUS est le cas
ILLISIBLE »* — un témoin positif, formulé hors de mes motifs.

    ma regex répondait à   « ces motifs textuels sont-ils présents ? »
    la question était      « cette épreuve DISCRIMINE-t-elle ? »

★ **Huitième occurrence de la classe 1 en une journée — commise en essayant de la mécaniser.**
⇒ **Le différentiel ne se lit pas dans le TEXTE, il s'EXÉCUTE** : faire tourner l'épreuve contre
une version délibérément cassée du code et vérifier qu'elle rougit. Plus coûteux, et seule
mesure honnête. *Le contrat le disait déjà — « la contre-épreuve est le livrable, pas un
supplément » — et je l'ai réappris en l'enfreignant.*


---

## 13. NE JAMAIS DEMANDER À UN PRODUCTEUR D'ATTESTER CE QU'IL NE PEUT PAS OBSERVER *(EA MT5)*

**Mesuré le 2026-09-02.** Une consigne demandait au modèle d'écrire, en dernière ligne, le plan
et le modèle sur lesquels il avait tourné — pour satisfaire la traçabilité LOI 1.

    en-tête imprimé par le HARNAIS :  servi : ollama_chat/gpt-oss:120b [cloud] https://ollama.com
    dernière ligne écrite par le MODÈLE : « Plan exécuté : default — Modèle : gpt-4o »

**`gpt-4o` n'existe dans aucun banc et le modèle n'y a jamais tourné.**

★ **Et ce n'est pas une hallucination de difficulté** : le même rendu citait **15 identifiants,
15 présents dans la pièce jointe, 0 invention**, vérifié par script. **Le seul champ faux était
celui qui portait sur LUI-MÊME.**

> **Un modèle ne sait pas de façon fiable sous quel alias il a été servi.** Le lui demander, c'est
> lui demander ce que la consigne ne lui donne pas — et un champ ainsi construit ne produit pas
> une vérification : **il produit une invention bien formatée, qui a l'air d'une preuve.**

⇒ **Le remède est un déplacement, pas un durcissement** : le plan ne se DEMANDE pas, il
s'**IMPRIME par le harnais**, qui le connaît. La traçabilité devient **passive** — elle ne dépend
plus de la coopération du producteur.

⚠️ **Conséquence pour tout banc de mesure** : si l'on demande aux modèles de déclarer quoi que ce
soit **sur eux-mêmes** — modèle, durée, troncature — **ces champs seront les moins fiables de
tout leur rendu**, pendant que le reste sera bon. **Ne pas les compter dans un taux de
fiabilité : ils mesurent la consigne, pas le modèle.**

### 13.1 Et le vérificateur a validé le mensonge

Son auteur le déclare : le script cherchait `(cloud|local|Ollama|plan)` dans la fin du rendu et a
conclu **« déclare son PLAN : OUI »**.

    il répondait à   « une déclaration est-elle PRÉSENTE ? »
    la question       « la déclaration est-elle VRAIE ? »

**Neuvième occurrence de la classe 1 dans la journée — sur l'instrument même qui devait faire
respecter la règle, dans le tour où elle était écrite.** ⇒ *Une leçon écrite ne protège pas son
auteur le jour même* : constaté le matin dans un dépôt, vérifié le soir dans l'autre, une heure
après avoir été citée.
