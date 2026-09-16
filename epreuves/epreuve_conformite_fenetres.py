import sys
from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path

def main():
    racine = Path(__file__).resolve().parents[1]
    spec = spec_from_file_location(
        "_epreuve_conf_fenetres",
        racine / "scripts" / "nexus_conformite.py"
    )
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    texte_config = """  - model_name: qwen3-coder-30b-local
      model: ollama_chat/qwen3-coder:30b
      api_base: http://host.docker.internal:11434
      num_ctx: 8192
  - model_name: glm-4.7-flash-local
      model: ollama_chat/glm-4.7-flash
      api_base: http://host.docker.internal:11434
      num_ctx: 65536
  - model_name: gpt-oss-120b-cloud
      model: ollama_chat/gpt-oss:120b
      api_base: https://ollama.com
      num_ctx: 8192
# >>> AUTOGEN:LOCAL_MODELS_EXTRA
  - model_name: phi-local
      model: ollama_chat/phi
      api_base: http://host.docker.internal:11434
      num_ctx: 2048
# <<< AUTOGEN:LOCAL_MODELS_EXTRA
"""

    cas = [
        ("C0", lambda: hasattr(module, "fenetres_declarees_sous_derivee")),
        ("F1", lambda: module.fenetres_declarees_sous_derivee(
            texte_config, lambda base: 65536) == [("qwen3-coder-30b-local", 8192, 65536)]),
        ("F2", lambda: module.fenetres_declarees_sous_derivee(
            texte_config, lambda base: 262144) == [
                ("glm-4.7-flash-local", 65536, 262144),
                ("qwen3-coder-30b-local", 8192, 262144)
            ]),
        ("F3", lambda: module.fenetres_declarees_sous_derivee(
            texte_config, lambda base: 99999 if base == "qwen3-coder:30b" else None) == [
                ("qwen3-coder-30b-local", 8192, 99999)
            ]),
        ("R1", lambda: module.fenetres_declarees_sous_derivee(
            texte_config, lambda base: None) == []),
        ("R2", lambda: module.fenetres_declarees_sous_derivee(
            texte_config, lambda base: 4096) == []),
        ("R3", lambda: module.fenetres_declarees_sous_derivee(
            texte_config, lambda base: exec("raise RuntimeError")) == []),
        ("L1", lambda: all(
            alias not in ["phi-local", "gpt-oss-120b-cloud"]
            for alias, _, _ in module.fenetres_declarees_sous_derivee(
                texte_config, lambda base: 999999)
        ))
    ]

    rates = 0
    for nom, test in cas:
        try:
            resultat = test()
            if resultat:
                print(f"[OK  ] {nom} : conforme")
            else:
                print(f"[RATE] {nom} : observe {resultat!r}")
                rates += 1
        except Exception as exc:
            print(f"[RATE] {nom} : {type(exc).__name__} {exc}")
            rates += 1

    print(f"{len(cas)} cas, {rates} RATE")
    return 1 if rates > 0 else 0

if __name__ == "__main__":
    sys.exit(main())
