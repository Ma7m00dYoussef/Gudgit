# Gudgit

Gudgit is a minimal, educational implementation of Git's core object model, written in Python. It re-implements the fundamentals of how Git tracks history — content-addressed objects, trees, commits, and refs — in a small, readable codebase.

Unlike Git, Gudgit has **no staging area (index)**. It follows a simpler **two-tree model**:

```
Working Tree  --(commit)-->  Repository (.gudgit)
```

Every `commit` snapshots the entire working directory directly into the repository — there's no `git add` step to stage individual changes.

## Features

- `gudgit init` — initialize a new repository
- `gudgit commit -m "message"` — snapshot the working directory as a new commit
- `gudgit restore <commit>` — restore the working tree to a previous commit
- `gudgit log` — view commit history

## How it works

Gudgit stores three kinds of objects under `.gudgit/objects/`, each identified by the SHA-1 hash of its content (just like Git):

| Object   | Purpose                                              |
|----------|-------------------------------------------------------|
| `Blob`   | Raw contents of a single file                         |
| `Tree`   | A directory listing of blobs and sub-trees             |
| `Commit` | Points to a root tree, zero or more parent commits, an author, and a message |

Objects are serialized with a Git-style header (`<type> <size>\0<content>`) and compressed with `zlib` before being written to disk.

Branches live under `.gudgit/refs/heads/`, and `.gudgit/HEAD` points at the current branch (e.g. `ref: refs/heads/main`), so switching branches later only requires rewriting one line.

### Repository layout

```
.gudgit/
├── HEAD                # points to the current branch
├── objects/             # all blobs, trees, and commits (by SHA-1)
│   └── <first 2 chars>/<remaining 38 chars>
└── refs/
    └── heads/
        └── main          # commit SHA the branch currently points to
```

## Requirements

- Python 3.8+

## Installation

Gudgit uses a standard `pyproject.toml` with a console-script entry point, so installing it with `pip` (or `pipx`) automatically creates a global `gudgit` command on **both Windows and Linux** — no manual PATH editing needed.

### 1. Clone the repository

```bash
git clone https://github.com/Ma7m00dYoussef/Gudgit.git
cd Gudgit
```

### 2. Install globally

**Recommended (isolated, works the same on Windows and Linux):**

```bash
pip install --user pipx
pipx install .
```

If `gudgit` isn't found right after installing, run `pipx ensurepath` and open a new terminal.

**Alternative (plain pip):**

```bash
pip install .
```

- On **Linux**, this installs the `gudgit` script to your user `bin` directory (e.g. `~/.local/bin`). Make sure that folder is on your `PATH`.
- On **Windows**, this installs `gudgit.exe` to your Python `Scripts` folder (e.g. `%APPDATA%\Python\PythonXY\Scripts`). Make sure that folder is on your `PATH`.

You should see the `init`, `commit`, `restore`, and `log` subcommands listed.

## Usage

```bash
# Initialize a repository in the current directory
gudgit init

# Snapshot the current working directory as a commit
gudgit commit -m "Initial commit"

# View commit history
gudgit log

# Restore the working tree to a previous commit
gudgit restore <commit-sha>
```

## Development install

If you're working on Gudgit itself and want changes to `main.py` / `repo.py` / `objects.py` to be picked up immediately without reinstalling:

```bash
pip install -e .
```

## Project structure

```
Gudgit/
├── main.py          # CLI entry point (argparse)
├── repo.py          # init / commit / restore / log logic
├── objects.py        # Blob, Tree, and Commit object model
└── pyproject.toml    # packaging config (console script: gudgit)
```

## License

No license specified yet — add one (e.g. MIT) if you plan to share this publicly.
