# -*- coding: utf-8 -*-
"""
Détection des processus orphelins « llama‑server.exe » (ou nom fourni).

Contexte : l’incident du 14 septembre 2026 montre que des processus
*llama‑server.exe* restent vivants après la mort de leur parent
(ollama.exe). Ils consomment plusieurs dizaines de gigaoctets d’engagement
(PagefileUsage) et provoquent l’épuisement de la mémoire d’engagement,
déclenchant à son tour des plantages de pwsh.

Cet outil permet :
* d’énumérer les processus Windows sans effet de bord à l’import,
* de repérer les orphelins, y compris les cas où le PID du parent a été
  réattribué (parent plus récent que l’enfant),
* de fournir un résumé JSON structuré,
* de terminer les orphelins de façon sécurisée.

Aucune dépendance externe ; uniquement la bibliothèque standard.
"""

import argparse
import ctypes
import json
import os
import sys
from typing import List, Dict, Any

# --------------------------------------------------------------------------- #
# Constantes Windows (définies ici mais utilisées uniquement dans les fonctions
# qui les chargent dynamiquement)
# --------------------------------------------------------------------------- #
TH32CS_SNAPPROCESS = 0x00000002
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
MAX_PATH = 260

# Droits d’accès minimalistes
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_VM_READ = 0x0010
PROCESS_TERMINATE = 0x0001

# --------------------------------------------------------------------------- #
# Helpers Windows – chargement paresseux
# --------------------------------------------------------------------------- #
def _load_kernel32():
    """Charge kernel32.dll et expose les fonctions nécessaires."""
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)

    # CreateToolhelp32Snapshot
    k32.CreateToolhelp32Snapshot.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
    k32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p

    # Process32FirstW / Process32NextW
    k32.Process32FirstW.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    k32.Process32FirstW.restype = ctypes.c_int
    k32.Process32NextW.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    k32.Process32NextW.restype = ctypes.c_int

    # OpenProcess
    k32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    k32.OpenProcess.restype = ctypes.c_void_p

    # GetProcessTimes
    k32.GetProcessTimes.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_uint64),  # creation
        ctypes.POINTER(ctypes.c_uint64),  # exit
        ctypes.POINTER(ctypes.c_uint64),  # kernel
        ctypes.POINTER(ctypes.c_uint64),  # user
    ]
    k32.GetProcessTimes.restype = ctypes.c_int

    # TerminateProcess
    k32.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    k32.TerminateProcess.restype = ctypes.c_int

    # CloseHandle
    k32.CloseHandle.argtypes = [ctypes.c_void_p]
    k32.CloseHandle.restype = ctypes.c_int

    return k32


def _load_psapi():
    """Charge psapi.dll et expose GetProcessMemoryInfo."""
    ps = ctypes.WinDLL("psapi", use_last_error=True)
    ps.GetProcessMemoryInfo.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_uint32,
    ]
    ps.GetProcessMemoryInfo.restype = ctypes.c_int
    return ps


# --------------------------------------------------------------------------- #
# Structures Windows
# --------------------------------------------------------------------------- #
class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", ctypes.c_uint32),
        ("cntUsage", ctypes.c_uint32),
        ("th32ProcessID", ctypes.c_uint32),
        ("th32DefaultHeapID", ctypes.c_void_p),
        ("th32ModuleID", ctypes.c_uint32),
        ("cntThreads", ctypes.c_uint32),
        ("th32ParentProcessID", ctypes.c_uint32),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", ctypes.c_uint32),
        ("szExeFile", ctypes.c_wchar * MAX_PATH),
    ]


class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_uint32),
        ("PageFaultCount", ctypes.c_uint32),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),          # <-- valeur d’engagement recherchée
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


# --------------------------------------------------------------------------- #
# API publiques
# --------------------------------------------------------------------------- #
def enumerer() -> List[Dict[str, Any]]:
    """
    Retourne la table des processus sous forme de liste de dictionnaires :

    {
        "pid": int,
        "ppid": int,
        "nom": str,
        "prive_octets": int,   # PagefileUsage
        "debut": int,           # FILETIME en 100‑ns depuis 1601, 0 si inaccessible
    }

    Aucun effet de bord à l’import ; toutes les liaisons DLL sont réalisées
    à l’intérieur de la fonction.
    """
    if os.name != "nt":
        # Sur les plateformes non‑Windows, on renvoie une table vide.
        return []

    k32 = _load_kernel32()
    psapi = _load_psapi()

    snapshot = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == INVALID_HANDLE_VALUE:
        raise OSError("Impossible de créer le snapshot de processus")

    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)

    processus: List[Dict[str, Any]] = []

    ok = k32.Process32FirstW(snapshot, ctypes.byref(entry))
    while ok:
        pid = entry.th32ProcessID
        ppid = entry.th32ParentProcessID
        nom = entry.szExeFile

        # Mémoire privée (PagefileUsage) – 0 si l’accès échoue
        prive = 0
        # Timestamp de création – 0 si l’accès échoue
        debut = 0

        hproc = k32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ,
            False,
            pid,
        )
        if hproc:
            # Mémoire
            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            if psapi.GetProcessMemoryInfo(
                hproc,
                ctypes.byref(counters),
                counters.cb,
            ):
                prive = counters.PagefileUsage

            # Temps de création
            ft_creation = ctypes.c_uint64()
            ft_exit = ctypes.c_uint64()
            ft_kernel = ctypes.c_uint64()
            ft_user = ctypes.c_uint64()
            if k32.GetProcessTimes(
                hproc,
                ctypes.byref(ft_creation),
                ctypes.byref(ft_exit),
                ctypes.byref(ft_kernel),
                ctypes.byref(ft_user),
            ):
                debut = ft_creation.value

            k32.CloseHandle(hproc)

        processus.append(
            {
                "pid": pid,
                "ppid": ppid,
                "nom": nom,
                "prive_octets": prive,
                "debut": debut,
            }
        )

        ok = k32.Process32NextW(snapshot, ctypes.byref(entry))

    k32.CloseHandle(snapshot)
    return processus


def _terminer(pid: int) -> bool:
    """
    Tente de terminer le processus indiqué.
    Retourne True si la terminaison a été demandée (pas forcément réussie).
    """
    k32 = _load_kernel32()
    hproc = k32.OpenProcess(PROCESS_TERMINATE, False, pid)
    if not hproc:
        return False
    try:
        k32.TerminateProcess(hproc, 1)
    finally:
        k32.CloseHandle(hproc)
    return True


def orphelins(table: List[Dict[str, Any]], cible: str) -> List[Dict[str, Any]]:
    """
    Détecte les processus dont ``nom`` correspond à *cible* et qui sont orphelins.

    Un processus est considéré orphelin si :
    * son PPID n’apparaît pas parmi les PID de la table, **ou**
    * le PPID existe mais le processus parent a été créé *après* l’enfant
      (cas de réutilisation de PID).

    Retourne la sous‑liste des orphelins (dictionnaires identiques à ceux de
    ``enumerer``). Fonction pure, testable sans Windows.
    """
    pids = {p["pid"] for p in table}
    debut_par_pid = {p["pid"]: p.get("debut", 0) for p in table}
    cible_lc = cible.lower()

    result = []
    for p in table:
        if p["nom"].lower() != cible_lc:
            continue
        parent_pid = p["ppid"]
        if parent_pid not in pids:
            result.append(p)
        else:
            # Parent présent : comparer les timestamps
            debut_parent = debut_par_pid.get(parent_pid, 0)
            if debut_parent > p.get("debut", 0):
                result.append(p)
    return result


def main(
    table: List[Dict[str, Any]] | None = None,
    argv: List[str] | None = None,
) -> int:
    """
    Point d’entrée du script.

    * ``table`` : si fourni, il est utilisé à la place de l’énumération réelle
      (utile pour les tests). Dans ce cas, la plateforme peut être non‑Windows.
    * ``argv`` : liste d’arguments à analyser à la place de ``sys.argv[1:]``.
    Retourne :
    * 1 si au moins un orphelin a été détecté,
    * 0 si aucun orphelin,
    * 2 si l’énumération a échoué (message d’erreur affiché).
    """
    # Si aucune table n’est fournie, on ne fonctionne que sous Windows.
    if table is None and os.name != "nt":
        print("Plateforme non Windows – aucun traitement effectué.")
        return 0

    parser = argparse.ArgumentParser(
        description="Détection des processus orphelins (llama-server.exe)."
    )
    parser.add_argument(
        "--nom",
        default="llama-server.exe",
        help="Nom du processus cible (exemple : llama-server.exe)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Émettre le résultat au format JSON structuré",
    )
    parser.add_argument(
        "--tuer",
        action="store_true",
        help="Terminer les processus orphelins détectés",
    )
    args = parser.parse_args(argv)

    # 1. Récupération de la table
    if table is None:
        try:
            table = enumerer()
        except Exception as exc:  # NON VERIFIE
            print(f"Erreur d’énumération : {exc}")
            return 2

    # 2. Détection
    liste_orphelins = orphelins(table, args.nom)

    # 3. Action éventuelle de terminaison
    tues: List[int] = []
    if args.tuer:
        for p in liste_orphelins:
            if _terminer(p["pid"]):
                tues.append(p["pid"])

    # 4. Construction du résultat JSON
    total_prive = sum(p["prive_octets"] for p in liste_orphelins)

    resultat = {
        "orphelins": liste_orphelins,
        "total_prive_octets": total_prive,
        "tues": tues,
    }

    # 5. Sortie
    if args.json:
        print(json.dumps(resultat, ensure_ascii=False, indent=2))
    else:
        if liste_orphelins:
            print(f"Orphelins détectés ({len(liste_orphelins)}) :")
            for p in liste_orphelins:
                print(
                    f"  PID={p['pid']} PPID={p['ppid']} NOM={p['nom']} "
                    f"PRIVE={p['prive_octets']} octets DEBUT={p['debut']}"
                )
        else:
            print("Aucun orphelin détecté.")
        if args.tuer:
            if tues:
                print(f"PIDs terminés : {', '.join(map(str, tues))}")
            else:
                print("Aucun PID n’a pu être terminé.")

    return 1 if liste_orphelins else 0


if __name__ == "__main__":
    sys.exit(main())
