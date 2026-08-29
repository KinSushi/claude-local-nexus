# Rituels

Quatre fichiers pour qu'aucune information importante ne dépende d'une
mémoire de session : ce que la plateforme **est**, ce qu'il reste **à
faire**, ce qui a **été décidé**, et **où trouver** chaque fichier.

| Fichier | Contenu | Origine |
|---|---|---|
| [`STATE.md`](STATE.md) | Services, moteur d'inférence, budget matériel, inventaire exposé, empreintes | **généré** — ne pas éditer |
| [`CHECKLIST_COCKPIT.MD`](CHECKLIST_COCKPIT.MD) | Sujets ouverts, avec leur statut et la prochaine action | tenu à la main |
| [`PROGRESS.md`](PROGRESS.md) | Décisions, mesures qui les ont motivées, et erreurs commises | tenu à la main |
| [`BOUSSOLE.md`](BOUSSOLE.md) | Index du dépôt : rôle, taille, date et empreinte de chaque fichier | **généré** |

## Reprendre le fil

```powershell
.\rituels\RESUME.ps1          # régénère l'état mesuré, puis liste les sujets ouverts
.\rituels\RESUME.ps1 -Full    # ajoute le contrôle d'intégrité et le smoke test
```

`STATE.md` et `BOUSSOLE.md` sont **reconstruits par mesure**, jamais saisis.
Un fichier d'état écrit à la main décrit ce qu'on croyait au moment de
l'écrire ; celui-ci décrit ce qui est. Le régénérer vaut donc toujours mieux
que le corriger.

## Pourquoi des empreintes

Chaque entrée de la boussole porte une empreinte SHA-256, tronquée à
128 bits pour rester lisible. Elle permet de répondre sans commande jetable
à une question qui revient souvent : *ce fichier est-il encore celui que
l'état décrit ?*

L'historique git complète le dispositif — il est lui-même un rituel de
sauvegarde, et [`nexus_preserve.py`](../scripts/nexus_preserve.py) le
classe parmi les artefacts **irremplaçables** tant que des commits ne sont
pas poussés.
