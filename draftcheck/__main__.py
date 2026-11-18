import argparse
import json
import sys
from pathlib import Path

from .model import ModelUnavailable, install_model
from .review import KINDS, load_profile, review_draft
from .server import serve


def main():
    parser = argparse.ArgumentParser(prog="draftcheck", description="Review writing locally.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("setup", help="Download and verify the model once.")
    commands.add_parser("profile", help="Print the writing voice guide as JSON.")
    review = commands.add_parser("review", help="Review a UTF-8 file or standard input and print JSON.")
    review.add_argument("file", nargs="?", type=Path)
    review.add_argument("--kind", choices=KINDS, default="general")
    browser = commands.add_parser("serve", help="Open the local browser workspace.")
    browser.add_argument("--port", default=8765, type=int)
    browser.add_argument("--open", action="store_true", help="Open the default browser.")
    arguments = parser.parse_args()

    try:
        if arguments.command == "setup":
            install_model(lambda message: print(message, flush=True))
            print("Local detector ready.")
        elif arguments.command == "profile":
            profile = load_profile()
            if profile is None:
                raise ValueError("This copy of Draftcheck has no local voice guide.")
            print(json.dumps(profile, indent=2, ensure_ascii=False))
        elif arguments.command == "review":
            draft = arguments.file.read_text(encoding="utf-8") if arguments.file else sys.stdin.read()
            print(json.dumps(review_draft(draft, arguments.kind), indent=2, ensure_ascii=False))
        elif arguments.command == "serve":
            if not 1 <= arguments.port <= 65535:
                raise ValueError("Choose a port between 1 and 65535.")
            serve(arguments.port, arguments.open)
    except (ModelUnavailable, OSError, UnicodeError, ValueError) as error:
        parser.exit(1, f"Draftcheck: {error}\n")


if __name__ == "__main__":
    main()
