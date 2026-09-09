import os
import sys
import contextlib

def _main():
    try:
        # Ensure the script directory is on sys.path for relative imports
        script_dir = os.path.abspath(os.path.dirname(__file__))
        if script_dir not in sys.path:
            sys.path.insert(0, script_dir)

        # Import nexus_verbatim after path adjustment
        try:
            import nexus_verbatim
        except Exception:
            sys.stderr.write("Failed to import nexus_verbatim\n")
            return

        # Parse arguments
        if len(sys.argv) < 4:
            sys.stderr.write("Insufficient arguments\n")
            return
        response_file = sys.argv[1]
        model = sys.argv[2]
        plan = sys.argv[3]
        task = sys.argv[4] if len(sys.argv) > 4 else ""

        # Read response content
        try:
            with open(response_file, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
        except Exception:
            sys.stderr.write("Failed to read response file\n")
            content = ""

        # Deposit verbatim only when there is something to trace
        if content:
            try:
                nexus_verbatim.deposer(content, model, task, plan)
            except Exception:
                sys.stderr.write("Failed to deposit verbatim\n")

        # Remove the response file
        with contextlib.suppress(OSError):
            os.remove(response_file)

    except Exception:
        sys.stderr.write("Unexpected error in nexus_deposer\n")
    finally:
        sys.exit(0)

if __name__ == '__main__':
    _main()