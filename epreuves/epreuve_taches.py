# -*- coding: utf-8 -*-
"""Épreuve fonctionnelle du module ``outillage/nexus_taches.py``.
Chaque cas écrit sur STDOUT une ligne commençant exactement par
`[OK  ] ` (OK suivi de deux espaces) ou `[RATE] `, puis le nom du cas,
un deux‑points et un détail optionnel.
Le code de sortie du processus est 0 si tous les cas réussissent,
1 sinon.

Utilisation :
    python epreuves/epreuve_taches.py
"""

import importlib.util
import json
import os
import pathlib
import shutil
import sys
import tempfile

# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _load_module():
    """Charge ``outillage/nexus_taches.py`` depuis la racine du dépôt."""
    base_dir = pathlib.Path(__file__).resolve().parents[1]   # repository root
    module_path = base_dir / "outillage" / "nexus_taches.py"
    spec = importlib.util.spec_from_file_location("_epreuve_nexus_taches", module_path)
    if spec is None or spec.loader is None:
        raise ImportError("Impossible de charger le module nexus_taches")
    module = importlib.util.module_from_spec(spec)
    # Inscrire le module dans sys.modules pour que dataclasses puisse accéder à son __module__
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)  # see dataclasses.py line 814
    except Exception:
        sys.modules.pop(spec.name, None)
        raise
    return module, base_dir

def check(nom, condition, detail=""):
    """Affiche le résultat d’un cas de test et renvoie le booléen."""
    if condition:
        print(f"[OK  ] {nom} : {detail}")
    else:
        print(f"[RATE] {nom} : {detail}")
    return condition

# ----------------------------------------------------------------------
# Fake exécutors / lecteurs de sortie
# ----------------------------------------------------------------------
class FakeExecuter:
    """Enregistre les appels et renvoie des codes configurables."""
    def __init__(self):
        self.calls = []          # liste de (argv, delai)
        self.mapping = {}        # famille -> code (int|None)

    def set(self, famille, code):
        """Assigne *code* (int ou None) à la *famille* donnée."""
        self.mapping[famille] = code

    def __call__(self, argv, delai=None):
        self.calls.append((tuple(argv), delai))
        # le module passe la famille comme dernier argument
        famille = argv[-1] if argv else None
        return self.mapping.get(famille, None)

class FakeLireSortie:
    """Simule les réponses de ``git``."""
    def __init__(self):
        self.head = None
        self.commit_map = {}     # id -> sha

    def set_head(self, head):
        self.head = head

    def set_commit(self, tache_id, sha):
        self.commit_map[tache_id] = sha

    def __call__(self, argv, delai=None):
        # git rev-parse HEAD
        if argv[:3] == ["git", "rev-parse", "HEAD"]:
            if self.head is None:
                return None
            return (0, self.head + "\n")
        # git log --grep=Tache:<id>
        if argv and argv[0] == "git" and any("--grep=Tache:" in a for a in argv):
            for a in argv:
                if a.startswith("--grep=Tache:"):
                    t_id = a.split(":", 1)[1].strip()
                    sha = self.commit_map.get(t_id, "")
                    return (0, sha + ("\n" if sha else ""))
        # fallback
        return (0, "")

# ----------------------------------------------------------------------
# Test harness
# ----------------------------------------------------------------------
def main():
    ok = True
    mod, repo_root = _load_module()

    # ------------------------------------------------------------------
    # Préparer un répertoire temporaire
    # ------------------------------------------------------------------
    temp_dir = tempfile.mkdtemp()
    temp_path = pathlib.Path(temp_dir)
    try:
        # ------------------------------------------------------------------
        # 0. Préparer la fuite (enregistrement des mtimes réelles)
        # ------------------------------------------------------------------
        real_registre = pathlib.Path(mod.REGISTRE)
        real_cache = pathlib.Path(mod.CACHE)
        real_reg_mtime = real_registre.stat().st_mtime if real_registre.exists() else None
        real_cache_mtime = real_cache.stat().st_mtime if real_cache.exists() else None

        # ------------------------------------------------------------------
        # 0.b Créer le script temporaire outillage/nexus_test.py
        # ------------------------------------------------------------------
        script_path = temp_path / "outillage" / "nexus_test.py"
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text(
            "import argparse, sys\n"
            "def main():\n"
            "    p = argparse.ArgumentParser()\n"
            "    p.add_argument('--only')\n"
            "    args = p.parse_args()\n"
            "    if args.only in (None, \"fam-ok\"):\n"
            "        sys.exit(0)\n"
            "    sys.exit(1)\n"
            "if __name__ == '__main__':\n"
            "    main()\n",
            encoding="utf-8"
        )

        # ------------------------------------------------------------------
        # Rediriger les constantes du module vers le répertoire temporaire
        # ------------------------------------------------------------------
        mod.REGISTRE = temp_path / "outillage" / "rituels" / "taches.jsonl"
        mod.CACHE = temp_path / ".nexus" / "taches_verdicts.json"
        (temp_path / "outillage" / "rituels").mkdir(parents=True, exist_ok=True)
        (temp_path / ".nexus").mkdir(parents=True, exist_ok=True)

        # ------------------------------------------------------------------
        # 1. Cas L* – validation du registre
        # ------------------------------------------------------------------
        try:
            # L1 – registre valide de 4 tâches
            valid_tasks = [
                {"id":"T-20230101-001","titre":"T1","origine":"o1","preuve":{"type":"famille","cible":"fam-ok"},"cree_le":"2023-01-01"},
                {"id":"T-20230101-002","titre":"T2","origine":"o2","preuve":{"type":"commit"},"cree_le":"2023-01-02"},
                {"id":"T-20230101-003","titre":"T3","origine":"o3","preuve":{"type":"commande","cible":"cmd1"},"cree_le":"2023-01-03"},
                {"id":"T-20230101-004","titre":"T4","origine":"o4","non_mecanisable":"raison","cree_le":"2023-01-04"},
            ]
            with open(mod.REGISTRE, "w", encoding="utf-8") as f:
                for t in valid_tasks:
                    f.write(json.dumps(t, ensure_ascii=False) + "\n")
            tasks = mod.lire_registre(mod.REGISTRE)
            ok &= check("L1", isinstance(tasks, list) and len(tasks) == 4,
                        f"{len(tasks)} tâches lues")
        except Exception as e:
            ok &= check("L1", False, f"exception {e}")

        try:
            # L2 – JSON invalide à la ligne 2
            with open(mod.REGISTRE, "w", encoding="utf-8") as f:
                f.write(json.dumps(valid_tasks[0]) + "\n")
                f.write("{invalid json\n")
                f.write(json.dumps(valid_tasks[1]) + "\n")
            mod.lire_registre(mod.REGISTRE)
            ok &= check("L2", False, "pas d'exception")
        except mod.RegistreInvalide as err:
            ok &= check("L2", err.ligne == 2, f"ligne {err.ligne}")

        try:
            # L3 – id dupliqué
            dup = valid_tasks[0].copy()
            dup["titre"] = "dup"
            with open(mod.REGISTRE, "w", encoding="utf-8") as f:
                for t in (valid_tasks[0], dup, valid_tasks[2]):
                    f.write(json.dumps(t) + "\n")
            mod.lire_registre(mod.REGISTRE)
            ok &= check("L3", False, "pas d'exception")
        except mod.RegistreInvalide:
            ok &= check("L3", True, "détecté")

        try:
            # L4 – champ inconnu 'etat'
            bad = valid_tasks[0].copy()
            bad["etat"] = "quelquechose"
            with open(mod.REGISTRE, "w", encoding="utf-8") as f:
                f.write(json.dumps(bad) + "\n")
            mod.lire_registre(mod.REGISTRE)
            ok &= check("L4", False, "pas d'exception")
        except mod.RegistreInvalide:
            ok &= check("L4", True, "détecté")

        try:
            # L5 – non_mecanisable ET preuve
            bad = valid_tasks[0].copy()
            bad["non_mecanisable"] = "raison"
            with open(mod.REGISTRE, "w", encoding="utf-8") as f:
                f.write(json.dumps(bad) + "\n")
            mod.lire_registre(mod.REGISTRE)
            ok &= check("L5", False, "pas d'exception")
        except mod.RegistreInvalide:
            ok &= check("L5", True, "détecté")

        try:
            # L6 – id hors motif
            bad = valid_tasks[0].copy()
            bad["id"] = "BADID"
            with open(mod.REGISTRE, "w", encoding="utf-8") as f:
                f.write(json.dumps(bad) + "\n")
            mod.lire_registre(mod.REGISTRE)
            ok &= check("L6", False, "pas d'exception")
        except mod.RegistreInvalide:
            ok &= check("L6", True, "détecté")

        try:
            # L7 – registre absent
            os.remove(mod.REGISTRE)
            mod.lire_registre(mod.REGISTRE)
            ok &= check("L7", False, "pas d'exception")
        except mod.RegistreInvalide:
            ok &= check("L7", True, "détecté")
        except Exception as exc:
            ok &= check(
                "L7",
                False,
                f"exception inattendue {type(exc).__name__}"
            )

        # ------------------------------------------------------------------
        # 2. Cas D* – dérivation d’une tâche
        # ------------------------------------------------------------------
        exec_fake = FakeExecuter()
        lire_sortie_fake = FakeLireSortie()
        familles = {"fam-ok"}

        # tâche de type famille, cible connue
        t_fam = mod.Tache(
            id="T-20230101-010",
            titre="Famille OK",
            origine="o",
            preuve={"type":"famille","cible":"fam-ok"},
            cree_le="2023-01-10",
            non_mecanisable=None,
        )
        # D1 – exécuter rend 0 → FAIT
        exec_fake.set("fam-ok", 0)
        etat, _ = mod.deriver(t_fam, familles=familles,
                              executer=exec_fake, lire_sortie=lire_sortie_fake)
        ok &= check("D1", etat == "FAIT", etat)

        # D2 – exécuter rend 1 → A_FAIRE
        exec_fake.calls.clear()
        exec_fake.set("fam-ok", 1)
        etat, _ = mod.deriver(t_fam, familles=familles,
                              executer=exec_fake, lire_sortie=lire_sortie_fake)
        ok &= check("D2", etat == "A_FAIRE", etat)

        # D3 – exécuter rend None → INCONNU
        exec_fake.calls.clear()
        exec_fake.set("fam-ok", None)
        etat, _ = mod.deriver(t_fam, familles=familles,
                              executer=exec_fake, lire_sortie=lire_sortie_fake)
        ok &= check("D3", etat == "INCONNU", etat)

        # D4 – famille inconnue → INCONNU, aucune exécution
        exec_fake.calls.clear()
        t_fam_unknown = mod.Tache(
            id="T-20230101-011",
            titre="Famille inconnue",
            origine="o",
            preuve={"type":"famille","cible":"fam-absente"},
            cree_le="2023-01-11",
            non_mecanisable=None,
        )
        etat, _ = mod.deriver(t_fam_unknown, familles=familles,
                              executer=exec_fake, lire_sortie=lire_sortie_fake)
        ok &= check("D4", etat == "INCONNU" and len(exec_fake.calls) == 0,
                    f"{etat}, calls={len(exec_fake.calls)}")

        # D5 – commit, git log rend un sha → FAIT
        exec_fake.calls.clear()
        t_commit = mod.Tache(
            id="T-20230101-012",
            titre="Commit OK",
            origine="o",
            preuve={"type":"commit"},
            cree_le="2023-01-12",
            non_mecanisable=None,
        )
        lire_sortie_fake.set_commit(t_commit.id, "sha123")
        etat, _ = mod.deriver(t_commit, familles=familles,
                              executer=exec_fake, lire_sortie=lire_sortie_fake)
        ok &= check("D5", etat == "FAIT", etat)

        # D6 – commit, git log vide → A_FAIRE
        exec_fake.calls.clear()
        t_commit2 = mod.Tache(
            id="T-20230101-013",
            titre="Commit absent",
            origine="o",
            preuve={"type":"commit"},
            cree_le="2023-01-13",
            non_mecanisable=None,
        )
        lire_sortie_fake.set_commit(t_commit2.id, "")
        etat, _ = mod.deriver(t_commit2, familles=familles,
                              executer=exec_fake, lire_sortie=lire_sortie_fake)
        ok &= check("D6", etat == "A_FAIRE", etat)

        # D7 – commande, clé absente de LISTE_BLANCHE → INCONNU, aucune exécution
        exec_fake.calls.clear()
        t_cmd = mod.Tache(
            id="T-20230101-014",
            titre="Commande inconnue",
            origine="o",
            preuve={"type":"commande","cible":"cle-inconnue"},
            cree_le="2023-01-14",
            non_mecanisable=None,
        )
        if "cle-inconnue" in getattr(mod, "LISTE_BLANCHE", {}):
            del mod.LISTE_BLANCHE["cle-inconnue"]
        etat, _ = mod.deriver(t_cmd, familles=familles,
                              executer=exec_fake, lire_sortie=lire_sortie_fake)
        ok &= check("D7", etat == "INCONNU" and len(exec_fake.calls) == 0,
                    f"{etat}, calls={len(exec_fake.calls)}")

        # D8 – non_mecanisable → NON_MECANISABLE, aucune exécution
        exec_fake.calls.clear()
        t_nm = mod.Tache(
            id="T-20230101-015",
            titre="Non mecanisable",
            origine="o",
            preuve=None,
            cree_le="2023-01-15",
            non_mecanisable="raison",
        )
        etat, _ = mod.deriver(t_nm, familles=familles,
                              executer=exec_fake, lire_sortie=lire_sortie_fake)
        ok &= check("D8", etat == "NON_MECANISABLE" and len(exec_fake.calls) == 0,
                    etat)

        # ------------------------------------------------------------------
        # 3. Cas H* – head_courant
        # ------------------------------------------------------------------
        lire_sortie_fake.set_head("abc")
        head = mod.head_courant(lire_sortie_fake)
        ok &= check("H1_present", head == "abc", head)

        lire_sortie_fake.set_head(None)
        head_none = mod.head_courant(lire_sortie_fake)
        ok &= check("H1_absent", head_none is None, str(head_none))

        # ------------------------------------------------------------------
        # 4. Cas C* – mesure et cache
        # ------------------------------------------------------------------
        simple_task = {
            "id":"T-20230101-020",
            "titre":"Simple",
            "origine":"o",
            "preuve":{"type":"famille","cible":"fam-ok"},
            "cree_le":"2023-01-20"
        }
        with open(mod.REGISTRE, "w", encoding="utf-8") as f:
            f.write(json.dumps(simple_task) + "\n")

        exec_fake.calls.clear()
        exec_fake.set("fam-ok", 0)
        lire_sortie_fake.set_head("head1")
        res1 = mod.mesurer(
            chemin_registre=mod.REGISTRE,
            chemin_cache=mod.CACHE,
            executer=exec_fake,
            lire_sortie=lire_sortie_fake,
            racine=temp_path,
        )
        mesures1 = res1.get("mesures", 0)
        ok &= check(
            "C1_first",
            mesures1 == 1 and len(exec_fake.calls) == 1,
            f"mesures={mesures1}, calls={len(exec_fake.calls)}"
        )

        exec_fake.calls.clear()
        lire_sortie_fake.set_head("head1")  # même head
        res2 = mod.mesurer(
            chemin_registre=mod.REGISTRE,
            chemin_cache=mod.CACHE,
            executer=exec_fake,
            lire_sortie=lire_sortie_fake,
            racine=temp_path,
        )
        mesures2 = res2.get("mesures", 0)
        ok &= check("C1_second", mesures2 == 0 and len(exec_fake.calls) == 0,
                    f"mesures={mesures2}, calls={len(exec_fake.calls)}")

        # C2 – changement de head entre deux mesures
        lire_sortie_fake.set_head("head2")
        exec_fake.calls.clear()
        exec_fake.set("fam-ok", 0)
        res3 = mod.mesurer(
            chemin_registre=mod.REGISTRE,
            chemin_cache=mod.CACHE,
            executer=exec_fake,
            lire_sortie=lire_sortie_fake,
            racine=temp_path,
        )
        mesures3 = res3.get("mesures", 0)
        ok &= check("C2_head_change", mesures3 >= 1 and len(exec_fake.calls) > 0,
                    f"mesures={mesures3}, calls={len(exec_fake.calls)}")

        # C3 – écriture / lecture du cache
        data = {"clé":"valeur"}
        mod.ecrire_cache(mod.CACHE, data)
        read_back = mod.lire_cache(mod.CACHE)
        ok &= check("C3_roundtrip", read_back == data, f"{read_back}")

        with open(mod.CACHE, "w", encoding="utf-8") as f:
            f.write("{corrompu")
        corrupted = mod.lire_cache(mod.CACHE)
        ok &= check("C3_corrupt", corrupted == {}, "attendu {}")

        tmp_files = list(temp_path.rglob("*.tmp"))
        ok &= check("C3_no_tmp", len(tmp_files) == 0,
                    f"{len(tmp_files)} .tmp files")

        # ------------------------------------------------------------------
        # 5. Cas R* – états pour rendu avec head différent du cache
        # ------------------------------------------------------------------
        old_head = "oldhead"
        verdicts = {
            "T-20230101-020": {
                "etat":"FAIT",
                "raison":"",
                "type":"famille",
                "cible":"fam-ok",
                "mesure_le":"2023-01-01T00:00:00"
            }
        }
        mod.ecrire_cache(mod.CACHE, {"head": old_head, "verdicts": verdicts})
        new_head = "newhead"
        etats = mod.etats_pour_rendu(mod.REGISTRE, mod.CACHE, new_head)
        all_non_mesure = all(v == "NON_MESURE" for _, v, _ in etats)
        ok &= check("R1", all_non_mesure, f"{etats}")

        # ------------------------------------------------------------------
        # 6. Cas M* – fonction main()
        # ------------------------------------------------------------------
        # M1 : registre invalide → code 2
        with open(mod.REGISTRE, "w", encoding="utf-8") as f:
            f.write("{invalid")
        rc = mod.main(['--verifier'])
        ok &= check("M1", rc == 2, f"rc={rc}")

        # M2 : appel sans argument → code 2
        rc = mod.main([])
        ok &= check("M2", rc == 2, f"rc={rc}")

        # M3 : registre absent → code 2, pas d'exception
        if mod.REGISTRE.exists():
            mod.REGISTRE.unlink()
        rc = mod.main(['--verifier'])
        ok &= check("M3", rc == 2, f"rc={rc}")

        # ------------------------------------------------------------------
        # 7. Fuite – aucun fichier supplémentaire dans le répertoire temporaire
        # ------------------------------------------------------------------
        expected = {
            mod.REGISTRE,
            mod.CACHE,
            script_path,
        }
        present = {p for p in temp_path.rglob("*") if p.is_file()}
        extra = present - expected
        ok &= check("F1", len(extra) == 0,
                    f"extra files: {extra}")

        # ------------------------------------------------------------------
        # 8. Vérifier qu'aucun fichier réel n'a été modifié (fuite)
        # ------------------------------------------------------------------
        # Vérification du registre
        ok &= check(
            "Fuite_registre_existence",
            real_registre.exists() == (real_reg_mtime is not None),
            "registre créé ou supprimé par l'épreuve"
        )
        if real_registre.exists():
            ok &= check(
                "Fuite_registre_mtime",
                real_registre.stat().st_mtime == real_reg_mtime,
                "registre modifié"
            )
        # Vérification du cache
        ok &= check(
            "Fuite_cache_existence",
            real_cache.exists() == (real_cache_mtime is not None),
            "cache créé ou supprimé par l'épreuve"
        )
        if real_cache.exists():
            ok &= check(
                "Fuite_cache_mtime",
                real_cache.stat().st_mtime == real_cache_mtime,
                "cache modifié"
            )

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
