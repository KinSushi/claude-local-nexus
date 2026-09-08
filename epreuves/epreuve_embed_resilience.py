"""test_resilience_embed_texts.py

Cette épreuve statique garantit que la fonction ``embed_texts`` du script
``scripts/nexus_livres_semantique.py`` reste résiliente sous contention :

* elle doit appeler ``urllib.request.urlopen`` (ou ``urlopen``) avec un
  argument nommé ``timeout`` dont la valeur numérique est au moins 30 s,
  afin d’éviter un blocage indéfini du build ;
* elle doit contenir une structure de reprise bornée : au moins une boucle
  (``for`` ou ``while``) qui lève explicitement une exception (``raise``).

Si l’une de ces exigences disparaît, le build doit échouer rapidement.
"""

import os
import sys
import ast

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CIBLE = os.path.join(RACINE, "scripts", "nexus_livres_semantique.py")


def _load_source(path: str) -> str | None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return None


def _find_embed_func(tree: ast.AST) -> ast.FunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "embed_texts":
            return node
    return None


def _has_timeout_call(func_node: ast.FunctionDef) -> tuple[bool, int | None]:
    """Recherche un appel à urlopen avec un keyword ``timeout`` >= 30.

    Retourne (True, valeur) si trouvé, sinon (False, None).
    """
    for node in ast.walk(func_node):
        if isinstance(node, ast.Call):
            # fonction peut être urllib.request.urlopen ou simplement urlopen
            func = node.func
            is_urlopen = False
            if isinstance(func, ast.Attribute) and func.attr == "urlopen":
                # ex: urllib.request.urlopen
                # vérifier la chaîne d'attributs (urllib.request)
                value = func.value
                if isinstance(value, ast.Attribute) and value.attr == "request" and isinstance(value.value, ast.Name) and value.value.id == "urllib":
                    is_urlopen = True
            elif isinstance(func, ast.Name) and func.id == "urlopen":
                is_urlopen = True

            if not is_urlopen:
                continue

            for kw in node.keywords:
                if kw.arg == "timeout":
                    # ast.Constant (py>=3.8) ou ast.Num (legacy)
                    val_node = kw.value
                    if isinstance(val_node, ast.Constant) and isinstance(val_node.value, (int, float)):
                        timeout_val = int(val_node.value)
                    elif isinstance(val_node, ast.Num):
                        timeout_val = int(val_node.n)
                    else:
                        continue
                    if timeout_val >= 30:
                        return True, timeout_val
    return False, None


def _has_bounded_retry(func_node: ast.FunctionDef) -> bool:
    """Vérifie la présence d'au moins une boucle contenant un ``raise``."""
    for node in ast.walk(func_node):
        if isinstance(node, (ast.For, ast.While)):
            # recherche récursive d'un ast.Raise dans le corps de la boucle
            for inner in ast.walk(node):
                if isinstance(inner, ast.Raise):
                    return True
    return False


def main() -> None:
    source = _load_source(CIBLE)
    if source is None:
        print("[RATE] resilience embed_texts : fichier cible introuvable ou illisible")
        sys.exit(1)

    try:
        tree = ast.parse(source, filename=CIBLE)
    except Exception as e:
        print(f"[RATE] resilience embed_texts : impossible d'analyser le fichier ({e})")
        sys.exit(1)

    func = _find_embed_func(tree)
    if func is None:
        print("[RATE] resilience embed_texts : fonction embed_texts introuvable")
        sys.exit(1)

    timeout_ok, timeout_val = _has_timeout_call(func)
    retry_ok = _has_bounded_retry(func)

    missing = []
    if not timeout_ok:
        missing.append("timeout >= 30")
    if not retry_ok:
        missing.append("boucle avec raise")

    if not missing:
        print(f"[OK  ] resilience embed_texts : timeout={timeout_val}")
        sys.exit(0)
    else:
        print(f"[RATE] resilience embed_texts : manquant {' ; '.join(missing)}")
        sys.exit(1)


if __name__ == "__main__":
    main()