import argparse
import sys

from repo import init, commit, restore, log, find_repo_root, GudgitError


def main():
    parser = argparse.ArgumentParser(prog="gudgit")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # gudgit init
    subparsers.add_parser("init", help="initialize a new repository")

    # gudgit commit -m "message"
    commit_parser = subparsers.add_parser("commit", help="create a new commit")
    commit_parser.add_argument("-m", "--message", required=True, help="commit message")

    # gudgit restore <commit>
    restore_parser = subparsers.add_parser("restore", help="restore a commit")
    restore_parser.add_argument("commit", help="commit SHA")

    # gudgit log
    subparsers.add_parser("log", help="show commit history")

    args = parser.parse_args()

    try:
        if args.command == "init":
            # init always works in the current directory.
            init(".")
            print("Initialized empty Gudgit repository.")

        elif args.command == "commit":
            repo_path = find_repo_root()
            sha = commit(args.message, repo_path)
            print(f"[{sha[:7]}] {args.message}")

        elif args.command == "restore":
            repo_path = find_repo_root()
            restore(args.commit, repo_path)
            print(f"Restored commit {args.commit[:7]}")

        elif args.command == "log":
            repo_path = find_repo_root()
            output = log(repo_path)
            output = output if len(output) else "No commits , yet"
            print(output)

    except GudgitError as exc:
        print(f"gudgit: {exc}", file=sys.stderr)
        return 1

    except OSError as exc:
        print(f"gudgit: filesystem error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())