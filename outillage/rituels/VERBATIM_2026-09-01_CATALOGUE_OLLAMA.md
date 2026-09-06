# VERBATIM — catalogue Ollama local et cloud, 2026-09-01

> Recopié **verbatim** sur consigne de l'opérateur : *« tu fais recopier verbatim
> sans brûler ton contexte, c'est pour ta checklist »*.
>
> **Ce document est une SOURCE, pas une doctrine.** Rien ici n'a été vérifié par
> ce dépôt au moment de la recopie, à l'exception de ce qui est explicitement
> marqué comme sortie de terminal de l'opérateur. Les identifiants CLI doivent
> être éprouvés avant d'entrer dans `litellm_config.yaml` (§5, §39 du contrat :
> ne jamais inventer un modèle, et la configuration déployée fait foi).
>
> Ce qui a valeur de **mesure** ici : les deux sorties de terminal de l'opérateur
> (`ollama cloud search` qui échoue, et `ollama list`). Le reste est une analyse
> tierce, à traiter comme un signal (§112.4).

---

## 1. Question de l'opérateur

> on ne doit pas être bridé : ollama cloud search — quelle est la bonne commande
> avec ollama list pour le local ?

---

## 2. Réponse reçue — verbatim

Oui. Si tu veux voir uniquement les modèles installés localement avec Ollama, la commande standard est :

    ollama list

Elle liste les modèles présents dans ton stockage Ollama local.

### Pour distinguer local et Cloud

Les modèles Cloud portent généralement un suffixe `:cloud`, par exemple :

    qwen3-coder
    gpt-oss:20b
    glm-4.7-flash

→ local

et :

    qwen3-coder:cloud
    gpt-oss:120b-cloud
    glm-4.7:cloud

→ Cloud. Ollama documente explicitement cette distinction dans les noms de modèles.

Donc, pour ton architecture Claude Local Nexus, je ferais simplement :

    ollama list

Puis, pour savoir ce qui est réellement chargé en mémoire / en cours d'exécution :

    ollama ps

`ollama ps` est plus intéressant pour ton routeur adaptatif, car il permet notamment de voir le modèle actuellement chargé et son placement CPU/GPU.

### Si tu veux uniquement filtrer les locaux sous PowerShell

    ollama list | Select-String -NotMatch ":cloud"

Et uniquement les Cloud :

    ollama list | Select-String ":cloud"

### Verdict pour ton projet

    ollama list    → inventaire des modèles disponibles localement
    ollama ps      → modèles actuellement actifs/chargés
    :cloud         → modèle Ollama Cloud

Attention : `ollama list` est avant tout l'inventaire du daemon Ollama local ; pour ton inventaire Cloud complet, il vaut mieux interroger le catalogue Ollama Cloud plutôt que considérer `ollama list` comme un catalogue exhaustif du Cloud. Les modèles Cloud peuvent être utilisés via Ollama et sont automatiquement déportés vers l'infrastructure Cloud.

---

## 3. Catalogue Cloud auquel l'opérateur a accès — verbatim

    qwen3.5:397b                262 requests
    mistral-large-3:675b        248 requests
    nemotron-3-ultra            182 requests
    nemotron-3-super            196 requests
    nemotron-3-nano:30b         152 requests
    gemma4:31b                  228 requests
    kimi-k3                     227 requests
    kimi-k2.7-code              262 requests
    kimi-k2.6                   194 requests
    glm-5.3                     244 requests
    glm-5.3-flash               277 requests
    glm-5.1                     188 requests
    glm-5.2                     176 requests
    deepseek-v4-pro:0813        270 requests
    deepseek-v4-flash:0731      206 requests
    minimax-m3                  213 requests
    minimax-m2.7                208 requests
    gpt-oss:120b               3765 requests
    gpt-oss:20b                 187 requests

> Note de recopie : la colonne « requests » était collée au nom dans la source
> (`qwen3.5:397b262 requests`). Elle a été **séparée** ici parce que la réponse
> citée plus bas établit qu'il s'agit d'une métrique d'usage et non d'une partie
> de l'identifiant. C'est la seule modification de forme apportée au verbatim, et
> elle est signalée.

---

## 4. Sorties de terminal de l'opérateur — MESURE, pas analyse

    PowerShell 7.6.5
    PS C:\Users\dibac> ollama cloud search
    Error: unknown command "cloud" for "ollama"

    PS C:\Users\dibac> ollama list | Select-String ":cloud"

    glm-5.3-flash:cloud        3e780905abc0    -         5 days ago
    glm-5.2:cloud              09d3ded00dd7    -         5 days ago
    glm-5.1:cloud              7aea7667808a    -         5 days ago

### `ollama list` complet — verbatim

    NAME                       ID              SIZE      MODIFIED
    llama3.2:1b                baf6a787fdff    1.3 GB    15 hours ago
    qwen3-coder:30b            06c1097efce0    18 GB     15 hours ago
    llama3.2:3b                a80c4f17acd5    2.0 GB    15 hours ago
    nomic-embed-text:latest    0a109f422b47    274 MB    15 hours ago
    qwen2.5-coder:14b          9ec8897f747e    9.0 GB    15 hours ago
    llava:7b                   8dd30f6b0cb1    4.7 GB    15 hours ago
    gemma4:12b                 4eb23ef187e2    7.6 GB    15 hours ago
    phi3:mini                  4f2222927938    2.2 GB    15 hours ago
    mistral:7b                 6577803aa9a0    4.4 GB    15 hours ago
    deepseek-coder:6.7b        ce298d984115    3.8 GB    15 hours ago
    qwen2.5-coder:7b           dae161e27b0e    4.7 GB    15 hours ago
    qwen3-embedding:8b         64b933495768    4.7 GB    15 hours ago
    llama3.1:8b                46e0c10c039e    4.9 GB    15 hours ago
    qwen3:8b                   500a1f067a9f    5.2 GB    15 hours ago
    qwen3.5:9b                 6488c96fa5fa    6.6 GB    15 hours ago
    qwen3-vl:8b                901cae732162    6.1 GB    15 hours ago
    llama3.2-vision:11b        6f2f9757ae97    7.8 GB    15 hours ago
    phi3:medium                cf611a26b048    7.9 GB    15 hours ago
    llava:13b                  0d0eb4d7f485    8.0 GB    15 hours ago
    qwen3:14b                  bdbd181c33f2    9.3 GB    15 hours ago
    glm-4.7-flash:latest       4475827791a2    19 GB     15 hours ago
    gemma4:31b                 6316f0629137    19 GB     15 hours ago
    qwen2.5-coder:32b          b92d6a0bd47e    19 GB     15 hours ago
    codestral:latest           0898a8b286d5    12 GB     15 hours ago
    deepseek-coder:33b         acec7c0b0fd9    18 GB     15 hours ago
    qwen2.5:32b                9f13ba1299af    19 GB     15 hours ago
    llava:34b                  3d2d24f46674    20 GB     15 hours ago
    gpt-oss:20b                17052f91a42e    13 GB     15 hours ago
    codestral:22b              0898a8b286d5    12 GB     15 hours ago
    qwen3:32b                  030ee887880f    20 GB     15 hours ago
    gemma4:26b                 08ae7ec1744b    18 GB     15 hours ago
    qwen3.6:27b                9d5803d493a9    17 GB     15 hours ago
    mixtral:8x7b               a3b6bef0f836    26 GB     15 hours ago
    qwen3-vl:32b               ff2e46876908    20 GB     15 hours ago
    gemma4:latest              c6eb396dbd59    9.6 GB    15 hours ago
    bge-m3:latest              790764642607    1.2 GB    15 hours ago
    granite3.3:8b              fd429f23b909    4.9 GB    15 hours ago
    command-r:latest           7d96360d357f    18 GB     15 hours ago
    sqlcoder:latest            77ac14348387    4.1 GB    15 hours ago
    codegemma:7b               0c96700aaada    5.0 GB    15 hours ago
    phi3.5:latest              61819fb370a3    2.2 GB    15 hours ago
    qwen2.5:1.5b               65ec06548149    986 MB    15 hours ago
    qwen2.5:0.5b               a8b0c5157701    397 MB    15 hours ago
    gemma3:1b                  8648f39daa8f    815 MB    15 hours ago
    smollm2:1.7b               cef4a1e09247    1.8 GB    15 hours ago
    smollm2:360m               297281b699fc    725 MB    15 hours ago
    tinyllama:latest           2644915ede35    637 MB    15 hours ago
    qwen3:0.6b                 7df6b6e09427    522 MB    15 hours ago
    qwen3:1.7b                 8f68893c685c    1.4 GB    15 hours ago
    deepseek-ocr:latest        0e7b018b8a22    6.7 GB    15 hours ago
    granite3.1-moe:1b          3269ce3e31ea    1.4 GB    15 hours ago
    all-minilm:latest          1b226e2802db    45 MB     15 hours ago
    glm-5.3-flash:cloud        3e780905abc0    -         5 days ago
    glm-5.2:cloud              09d3ded00dd7    -         5 days ago
    glm-5.1:cloud              7aea7667808a    -         5 days ago

> **53 modèles locaux résidents sur disque, 3 références cloud** dans
> l'inventaire du daemon.

---

## 5. Analyse reçue — première passe, verbatim

### Diagnostic de la stack actuelle

Tu as déjà une très grosse couverture locale :

    petits modèles généralistes : Llama, Phi, Qwen, Gemma, SmolLM
    coding : Qwen2.5-Coder, Qwen3-Coder, DeepSeek-Coder, Codestral, CodeGemma
    reasoning : Qwen3, Gemma4, GPT-OSS
    multimodal : LLaVA, Qwen3-VL, Llama Vision, DeepSeek-OCR
    embeddings : Nomic, Qwen3-Embedding, BGE-M3
    SQL : SQLCoder
    modèles 20–34B : Qwen, Gemma, LLaVA, Mixtral, etc.

Donc le problème n'est absolument pas le manque de modèles locaux.

Le vrai manque est au niveau frontier / long-context / agentic / multimodal / MoE géants.

### Les 6 modèles qui changent réellement ta couverture

**① Kimi K3** — le plus gros trou actuel de ta stack. Modèle multimodal agentique de 2,8T paramètres, 1M tokens de contexte, vision, outils, coding longue durée.

    ollama run kimi-k3:cloud

**② GLM-5.3** — tu as `glm-5.3-flash:cloud`, `glm-5.2:cloud`, `glm-5.1:cloud` mais pas `glm-5.3:cloud`. Modèle open-weight le plus puissant pour le coding, 1M de contexte, orientation agentique longue. Améliorations rapportées sur Terminal-Bench, DeepSWE et SWE-Marathon.

    glm-5.3-flash → fast / economical agent
    glm-5.2       → strong agent
    glm-5.3       → frontier coding agent

**③ DeepSeek V4 Flash** — MoE, ~304B paramètres, ~13B actifs, 1M tokens, reasoning, tools, Cloud.

    ollama run deepseek-v4-flash:cloud

**④ DeepSeek V4 Pro** — catégorie HEAVY_REASONING, DEEP_RESEARCH, COMPLEX_CODE, MATHEMATICAL_REASONING. Seconde capacité de raisonnement indépendante.

**⑤ Mistral Large 3** — MoE multimodal généraliste, production et workloads enterprise : vision, tools, function calling, JSON, multilingue, 256K contexte, 675B paramètres.

    ollama run mistral-large-3:675b-cloud

**⑥ Qwen3.5 397B** — tu as `qwen3.5:9b` en local ; le Cloud donne `qwen3.5:397b`. Passage d'un modèle de routage courant à un worker frontier.

### Nemotron — pour l'architecture multi-agents

**Nemotron-3 Super** : 120B total / 12B actifs, 256K contexte, tools + thinking, conçu pour les applications multi-agents complexes. Candidat ORCHESTRATOR / SUPERVISOR / DELEGATOR / AGENT_COORDINATOR.

**Nemotron-3 Ultra** : 550B total / 55B actifs, 256K affiché, 1M revendiqué. Positionné pour long-running agents, agent orchestration, coding agents, deep research, workflows à centaines d'étapes. À tester, mais pas en modèle par défaut.

### MiniMax M3 — sous-estimé

Coding, agentic, native multimodality, long context, jusqu'à 1M tokens, fenêtre garantie d'au moins 512K.

    M2.7 → legacy / fallback
    M3   → nouvelle génération

### GPT-OSS déjà bien placé

    LOCAL  gpt-oss:20b
             ↓
    CLOUD  gpt-oss:120b

Tool calling, structured outputs, raisonnement configurable, capacités agentiques, reasoning effort configurable. Excellente paire pour tester l'adaptive escalation.

### Gemma4:31b — déjà local, ne pas retélécharger

Classé vision, tools, thinking, audio, cloud, tailles 12B / 26B / 31B. Candidat LOCAL_MULTIMODAL_REASONING.

### Ce qu'il ne faut PAS télécharger maintenant

    nemotron-3-nano
    minimax-m2.7
    kimi-k2.6
    glm-5.1
    glm-5.2
    gpt-oss:20b
    gemma4:31b

Capacités équivalentes ou supérieures déjà présentes.

### Point très important

    CATALOGUE OLLAMA PUBLIC
              ≠
    MODÈLES AUTORISÉS PAR TON COMPTE

Le catalogue utilisateur est un sous-ensemble de ce que le service expose globalement.

---

## 6. Seconde passe après vérification — verbatim, avec ses AUTOCORRECTIONS

> Cette section est la plus importante du document : la source s'y **rétracte**
> sur un point qu'elle avait affirmé. C'est ce qui la rend utilisable.

Vérification faite. Ma réponse précédente était partiellement correcte, mais trop affirmative sur certains noms et surtout sur l'idée de "modèles manquants".

### Ce qui est vérifié

1. **`kimi-k3:cloud` existe bien** — `ollama run kimi-k3:cloud`. Multimodal, agentique, 1M de contexte, 2,81T de paramètres. → Il manque réellement à `ollama list`.
2. **`glm-5.3:cloud` existe bien** — `ollama run glm-5.3:cloud`. 753B, 1M contexte, coding + agentic long-horizon. → ajout pertinent.
3. **`deepseek-v4-pro:cloud` existe bien** — 1,65T paramètres, 1M contexte, tools + thinking, usage extra high. → Il manque.
4. **`deepseek-v4-flash:cloud` existe bien** — 304B total / 13B actifs, 1M contexte, reasoning efficace. → Il manque.
5. **Mistral Large 3 : le nom exact importe.** La référence Cloud officielle n'est pas `mistral-large-3:675b` mais **`mistral-large-3:675b-cloud`**. 675B, vision, tools, 256K contexte. → Il manque.
6. **`nemotron-3-ultra:cloud` existe** — 550B, raisonnement, long-running agents, orchestration, deep research. 256K dans les métadonnées, jusqu'à 1M dans le texte du modèle. → Il manque.
7. **`nemotron-3-super:cloud` existe** — *correction importante de la réponse précédente : tu ne l'as pas localement.* 120B total / 12B actifs, 256K, outils + thinking, multi-agent. → Il manque.
8. **`minimax-m3:cloud` existe** — 512K de contexte garanti, jusqu'à 1M, multimodal, coding, agentic. → Il manque.

### Correction majeure : Qwen 3.5

C'est ici que la réponse précédente était incorrecte.

Je t'avais affirmé `qwen3.5:397b` comme modèle Cloud Ollama vérifié. **Je ne retrouve pas cette référence sur le catalogue Ollama officiel actuel.** La page officielle Qwen3.5 liste actuellement 0.8B, 2B, 4B, 9B, 27B, 35B, 122B avec support Cloud, **mais pas de variante officielle 397b**.

Donc la ligne `qwen3.5:397b 262 requests` vient manifestement du catalogue/console Cloud, et **je ne dois pas la transformer automatiquement en `ollama run qwen3.5:397b-cloud` sans preuve**. Pour celui-là : je ne sais pas encore quel identifiant CLI exact ton compte Ollama utilise.

### Tableau final — verbatim

| Modèle | Cloud officiel Ollama | Capacité distinctive | Manquant |
| --- | --- | --- | --- |
| Kimi K3 | `kimi-k3:cloud` | multimodal + agentic + 1M | Oui |
| GLM-5.3 | `glm-5.3:cloud` | coding + agentic + 1M | Oui |
| DeepSeek V4 Pro | `deepseek-v4-pro:cloud` | frontier reasoning + tools + 1M | Oui |
| DeepSeek V4 Flash | `deepseek-v4-flash:cloud` | reasoning efficace + 1M | Oui |
| Mistral Large 3 | `mistral-large-3:675b-cloud` | multimodal enterprise + vision | Oui |
| Nemotron 3 Ultra | `nemotron-3-ultra:cloud` | long-running agents | Oui |
| Nemotron 3 Super | `nemotron-3-super:cloud` | multi-agent | Oui |
| MiniMax M3 | `minimax-m3:cloud` | coding + agentic + multimodal | Oui |
| Gemma 4 31B | `gemma4:31b-cloud` | reasoning + multimodal | Local déjà présent |
| GPT-OSS 120B | `gpt-oss:120b-cloud` | reasoning + tools | Oui |
| Kimi K2.7 Code | `kimi-k2.7-code:cloud` | coding agentique | Oui |
| Kimi K2.6 | `kimi-k2.6:cloud` | multimodal + swarm agents | Oui |

### Classement final après vérification

**P0** — `kimi-k3:cloud`, `glm-5.3:cloud`, `deepseek-v4-pro:cloud`, `deepseek-v4-flash:cloud`, `mistral-large-3:675b-cloud`, `nemotron-3-ultra:cloud`, `minimax-m3:cloud`

**P1** — `nemotron-3-super:cloud`, `gpt-oss:120b-cloud`, `kimi-k2.7-code:cloud`, `kimi-k2.6:cloud`

**Pas prioritaire** — `gemma4:31b-cloud` (déjà local), `nemotron-3-nano:30b-cloud`

### Conclusion — verbatim

La bonne conclusion n'est donc pas « il faut installer tous les modèles Cloud qui manquent dans `ollama list` ». C'est : **`ollama list` ne représente pas ton catalogue Cloud complet.**

Et surtout, les noms du catalogue (`qwen3.5:397b`, `mistral-large-3:675b`, `nemotron-3-ultra`) semblent être une vue de catalogue avec métriques de requêtes, tandis que les références CLI officielles peuvent être `mistral-large-3:675b-cloud`, `nemotron-3-ultra:cloud`, `kimi-k3:cloud`, `glm-5.3:cloud`. C'est précisément pourquoi `ollama cloud search` n'est pas la bonne approche dans cette version de CLI.

La prochaine étape utile est de construire la matrice capacité complète Local × Ollama Cloud × Claude, avec coding / reasoning / vision / audio / OCR / tool-use / agentic / long-context / orchestration / speed / usage-cost, puis de déterminer quels modèles sont réellement redondants.

---

## 7. Ce que ce dépôt en retient — ARBITRAGE, distinct du verbatim

Cette section n'est pas dans la source. Elle dit ce que le dépôt fait de ce qui précède.

| Point | Statut ici |
| --- | --- |
| `ollama cloud search` n'existe pas | **MESURÉ** par l'opérateur, exploitable tel quel |
| 53 modèles locaux, 3 références cloud dans `ollama list` | **MESURÉ**, exploitable tel quel |
| `ollama list` ≠ catalogue Cloud | **RETENU** — c'est le fond du sujet, et §6.1/6.2/6.3 du contrat disait déjà *installé ≠ déclaré ≠ exposé*. Le catalogue cloud est un **quatrième** état que le contrat ne nommait pas. |
| identifiants `*:cloud` de la seconde passe | **À ÉPROUVER UN PAR UN** avant toute écriture dans `litellm_config.yaml` (§39 : ne jamais inventer un modèle). La source elle-même s'est trompée une fois. |
| `qwen3.5:397b` | **SUSPENDU** — la source se rétracte. Le dépôt déclare pourtant `qwen3.5-397b-cloud` dans `litellm_config.yaml:984`. Contradiction à trancher par une requête réelle, pas par lecture. |
| classement P0/P1 | **SIGNAL, PAS PREUVE** (§112.4). Un classement de capacités non mesuré ici ne décide d'aucune promotion : §76 impose DISCOVERED → REGISTERED → HEALTHY → BENCHMARKED → CANARY → PRODUCTION. |

**La contradiction `qwen3.5-397b-cloud` est le point le plus actionnable de tout
ce document** : le dépôt déclare et route vers un alias dont la source doute de
l'existence. Soit l'alias répond — et la source a tort —, soit il ne répond pas,
et un routeur pointe dans le vide depuis un temps inconnu. Une seule requête
réelle tranche. Elle est inscrite comme tâche.
