import sys, os, subprocess, tempfile

def make_file(path, content):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

def run_tool(file_path, extra_args=None):
    cmd = [sys.executable, os.path.join('scripts', 'nexus_verifie_rendu.py'), file_path]
    if extra_args:
        cmd.extend(extra_args)
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return proc.returncode, proc.stdout, proc.stderr

def main():
    with tempfile.TemporaryDirectory() as td:
        results = []
        # UN : écrit puis exit non nul, l'outil ne doit pas alerter
        un_path = os.path.join(td, 'un.py')
        make_file(un_path, "import sys\nprint('msg')\nsys.exit(1)\n")
        rc, out, err = run_tool(un_path)
        results.append((rc == 0, 'UN'))
        # DEUX : dépasse le timeout interne
        deux_path = os.path.join(td, 'deux.py')
        make_file(deux_path, "import time\ntime.sleep(20)\n")
        rc, out, err = run_tool(deux_path)
        results.append((rc != 0, 'DEUX'))
        # TROIS : fichier sain
        trois_path = os.path.join(td, 'trois.py')
        make_file(trois_path, "a = 1\n")
        rc, out, err = run_tool(trois_path)
        results.append((rc == 0, 'TROIS'))
        # QUATRE : exit non nul sans sortie, doit être noté mais pas alerter
        quatre_path = os.path.join(td, 'quatre.py')
        make_file(quatre_path, "import sys\nsys.exit(2)\n")
        rc, out, err = run_tool(quatre_path)
        results.append((rc == 0, 'QUATRE'))
        # CINQ : slice start 8 alors que référence de longueur 7
        cinq_path = os.path.join(td, 'cinq.py')
        make_file(cinq_path, "x = 'abcdefghij'[8:]\n")
        rc, out, err = run_tool(cinq_path, ['--refs=' + 'ABCDEFG'])
        results.append((rc != 0, 'CINQ'))
        # SIX : classe avec antislash simple (mutilation)
        six_path = os.path.join(td, 'six.py')
        bs = chr(92)
        pattern = "[" + bs + "a]"
        make_file(six_path, "r = " + repr(pattern) + "\n")
        rc, out, err = run_tool(six_path)
        results.append((rc != 0, 'SIX'))
        # SEPT : classe avec double antislash (correct)
        sept_path = os.path.join(td, 'sept.py')
        pattern2 = "[" + bs + bs + "a]"
        make_file(sept_path, "r = " + repr(pattern2) + "\n")
        rc, out, err = run_tool(sept_path)
        results.append((rc == 0, 'SEPT'))

        any_fail = False
        for ok, name in results:
            prefix = '[OK  ]' if ok else '[FAIL]'
            print(f"{prefix} {name}")
            if not ok:
                any_fail = True
        sys.exit(1 if any_fail else 0)

if __name__ == '__main__':
    main()
