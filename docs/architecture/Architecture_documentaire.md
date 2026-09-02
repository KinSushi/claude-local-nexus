Claude-Local-Nexus/
│
├── Claude.md
├── AGENTS.md
│
├── policies/
│   ├── execution-policy.yaml
│   ├── privacy-policy.yaml
│   ├── routing-policy.yaml
│   ├── security-policy.yaml
│   └── model-policy.yaml
│
├── registry/
│   ├── model-registry.yaml
│   ├── provider-registry.yaml
│   ├── capability-registry.yaml
│   └── tool-registry.yaml
│
├── profiles/
│   ├── coding.yaml
│   ├── reasoning.yaml
│   ├── research.yaml
│   ├── rag.yaml
│   ├── multimodal.yaml
│   └── autonomous-agent.yaml
│
├── evaluations/
│   ├── datasets/
│   ├── routing/
│   ├── models/
│   ├── agents/
│   └── regression/
│
├── scripts/
│   ├── validate_config.ps1
│   ├── validate_models.ps1
│   ├── validate_routing.ps1
│   ├── healthcheck.ps1
│   └── drift_check.ps1
│
└── docs/
    ├── ARCHITECTURE.md
    ├── ROUTING.md
    ├── SECURITY.md
    ├── MODEL_REGISTRY.md
    ├── RAG.md
    ├── OBSERVABILITY.md
    └── RUNBOOK.md

---
VERIFICATION (2026-09-02, agent d'audit, worktree agent-a268d2e8fe1dc957c)

Chaque chemin de cet arbre a ete controle contre l'etat reel du depot
(`ls`, execute a la racine du worktree, 2026-09-02) :

| chemin propose        | etat reel                                              | classement |
|------------------------|--------------------------------------------------------|------------|
| `Claude.md`             | ABSENT a la racine -- le fichier reel est `.claude/CLAUDE.md` | FAUX (emplacement) |
| `AGENTS.md`             | present a la racine                                     | VERIFIE |
| `policies/`             | absent                                                  | PLAN, non deploye |
| `registry/`             | absent                                                  | PLAN, non deploye |
| `profiles/`             | absent                                                  | PLAN, non deploye |
| `evaluations/`          | absent                                                  | PLAN, non deploye |
| `docs/ARCHITECTURE.md`, `ROUTING.md`, `SECURITY.md`, `MODEL_REGISTRY.md`, `RAG.md`, `OBSERVABILITY.md`, `RUNBOOK.md` | aucun de ces sept fichiers n'existe sous `docs/` | PLAN, non deploye |

L'absence de `policies/`, `registry/`, `profiles/`, `evaluations/` et des
sept fichiers `docs/*.md` n'est PAS une anomalie : `docs/architecture/
README.md` classe explicitement l'ensemble de ces notes comme "matiere
premiere du projet ... pas l'etat deploye", et cette page-ci les enumere
justement comme cible. Seule la ligne `Claude.md` est une affirmation
factuellement fausse independamment de ce statut de plan : le fichier de
contrat reel ne s'appelle pas ainsi et ne vit pas a la racine -- confondre
les deux egarerait quiconque cherche le contrat en le nommant "Claude.md"
a la racine.

NON VERIFIABLE : le contenu detaille des fichiers `policies/*.yaml`,
`registry/*.yaml` et `profiles/*.yaml` proposes ici n'a pas d'equivalent
existant a comparer -- ils n'existent nulle part dans le depot sous quelque
nom que ce soit.