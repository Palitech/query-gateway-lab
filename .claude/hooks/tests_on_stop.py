"""Stop hook: run the fast tests when Claude says it is done.

If tests fail, exit code 2 tells Claude to keep working instead of stopping.
Tests marked @pytest.mark.integration (they need Postgres) are skipped here.
CI runs the full suite.
"""

import json
import os
import subprocess
import sys

NO_TESTS_COLLECTED = 5

# Claude Code sets this to the project root, even if Claude has run `cd`.
PROJECT_DIR = os.environ.get("CLAUDE_PROJECT_DIR") or None


def main() -> None:
    data = json.loads(sys.stdin.buffer.read() or b"{}")

    # Prevent a loop: if Claude is already continuing because of this hook, let it stop.
    if data.get("stop_hook_active"):
        sys.exit(0)

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-x", "--no-header", "-m", "not integration"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=280,
        cwd=PROJECT_DIR,
    )

    if "No module named pytest" in result.stderr:
        sys.exit(0)  # pytest is not installed yet; stay quiet during setup.

    if result.returncode in (0, NO_TESTS_COLLECTED):
        sys.exit(0)

    print(
        "Tests are failing. Fix them, or explain to TJ why they fail:\n" + result.stdout[-3000:],
        file=sys.stderr,
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
