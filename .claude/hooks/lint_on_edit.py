"""PostToolUse hook: format and lint each Python file right after Claude edits it.

The edit has already happened, so this hook cannot block it.
Exit code 2 sends ruff's findings back to Claude so it fixes them next.
"""

import json
import subprocess
import sys


def run_ruff(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "ruff", *args],
        check=False,  # main() reads returncode itself.
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def main() -> None:
    data = json.loads(sys.stdin.buffer.read() or b"{}")
    path = (data.get("tool_input") or {}).get("file_path", "")

    if not path.endswith(".py"):
        sys.exit(0)

    run_ruff("format", path)
    result = run_ruff("check", "--fix", path)

    if "No module named ruff" in result.stderr:
        sys.exit(0)  # ruff is not installed yet; stay quiet during setup.

    if result.returncode != 0:
        print(
            f"ruff found problems in {path}. Fix them:\n{result.stdout}",
            file=sys.stderr,
        )
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
