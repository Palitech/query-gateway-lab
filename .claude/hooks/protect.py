"""PreToolUse hook: block access to secrets and risky git commands.

Claude Code sends the pending tool call as JSON on stdin.
Exit code 2 blocks the call, and the message on stderr goes back to Claude.
Exit code 0 allows the call.

This is a guardrail, not a security boundary. It catches mistakes.
The permissions "deny" list in settings.json is a second layer.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import PurePosixPath

# Claude Code sets this to the project root, even if Claude has run `cd`.
PROJECT_DIR = os.environ.get("CLAUDE_PROJECT_DIR") or None

FILE_TOOLS = {"Read", "Edit", "Write", "MultiEdit", "NotebookEdit", "Grep"}
SHELL_TOOLS = {"Bash", "PowerShell"}

# (pattern, message) pairs for shell commands.
GIT_RULES = [
    (
        r"\bgit\s+push\b.*(--force\b|--force-with-lease\b|\s-f\b)",
        "Force push is blocked.",
    ),
    (
        r"\bgit\s+push\b.*\bmain\b",
        "Push to main is blocked. Push a feature branch and open a pull request.",
    ),
    (r"\bgit\s+reset\s+--hard\b", "git reset --hard is blocked. Ask TJ first."),
    (r"\bgit\s+clean\b.*\s-[a-zA-Z]*f", "git clean -f is blocked. Ask TJ first."),
    (r"--no-verify\b", "Skipping git hooks with --no-verify is blocked."),
]


def is_secret_path(text: str) -> bool:
    """Return True if a path looks like a secret file."""
    path = PurePosixPath(text.replace("\\", "/"))
    name = path.name.lower()
    parts = {p.lower() for p in path.parts}

    if name == ".env":
        return True
    if name.startswith(".env.") and not name.endswith(".example"):
        return True
    if name.endswith((".pem", ".key", ".pfx", ".p12")):
        return True
    if name.startswith(("id_rsa", "id_ed25519", "id_ecdsa")):
        return True
    return ".ssh" in parts


def current_branch() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            check=False,  # Outside a repo, stdout is empty and we return "".
            capture_output=True,
            text=True,
            timeout=5,
            cwd=PROJECT_DIR,
        )
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def block(message: str) -> None:
    print(f"BLOCKED by .claude/hooks/protect.py: {message}", file=sys.stderr)
    sys.exit(2)


def check_shell(command: str) -> None:
    # Split on whitespace and shell punctuation, then check each piece as a path.
    for token in re.split(r"[\s'\"=<>|;&()]+", command):
        if token and is_secret_path(token):
            block(f"The command touches a secret file ({token}).")

    for pattern, message in GIT_RULES:
        if re.search(pattern, command):
            block(message)

    if re.search(r"\bgit\s+push\b", command) and current_branch() == "main":
        block("You are on main. Create a feature branch before you push.")


def check_file_tool(tool_input: dict) -> None:
    for key in ("file_path", "path", "notebook_path"):
        value = tool_input.get(key)
        if isinstance(value, str) and is_secret_path(value):
            block(f"Access to secret file {value} is not allowed.")


def main() -> None:
    data = json.loads(sys.stdin.buffer.read() or b"{}")
    tool = data.get("tool_name", "")
    tool_input = data.get("tool_input") or {}

    if tool in SHELL_TOOLS:
        check_shell(tool_input.get("command", ""))
    elif tool in FILE_TOOLS:
        check_file_tool(tool_input)

    sys.exit(0)


if __name__ == "__main__":
    main()
