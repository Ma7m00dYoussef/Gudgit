import os
import time

from objects import Blob , Tree, Commit 


class GudgitError(Exception):
    pass


def find_repo_root(start_path="."):
    current = os.path.abspath(start_path)

    while True:
        if os.path.isdir(os.path.join(current, GUDGIT_DIR)):
            return current

        parent = os.path.dirname(current)

        if parent == current:
            raise GudgitError("not a gudgit repository")

        current = parent

GUDGIT_DIR = ".gudgit"
def init(repo_path: str = "."):
    """Sets up the minimal .gudgit structure needed to start committing:
      .gudgit/objects/    -> where blobs/trees/commits get written
      .gudgit/refs/heads/ -> where branch pointers (commit shas) live
      .gudgit/HEAD        -> a pointer to the CURRENT branch (not acommit sha directly), so switching branches later only means rewriting this one line.
    Safe to call on an already-initialized repo -- won't overwrite
    HEAD if it already exists.
    """
    os.makedirs(os.path.join(repo_path, GUDGIT_DIR, "objects"), exist_ok=True)
    os.makedirs(os.path.join(repo_path, GUDGIT_DIR, "refs", "heads"), exist_ok=True)

    head_path = os.path.join(repo_path, GUDGIT_DIR, "HEAD")
    if not os.path.exists(head_path):
        with open(head_path, "w") as f:
            f.write("ref: refs/heads/main\n")


def _current_branch_ref_path(repo_path: str = ".") -> str:
    """Reads .gudgit/HEAD (e.g. "ref: refs/heads/main") and resolves it
    to the actual ref file path (.gudgit/refs/heads/main). This extra
    indirection (HEAD -> ref -> sha, instead of HEAD -> sha directly)
    is what lets HEAD just be rewritten when switching branches."""
    head_path = os.path.join(repo_path, GUDGIT_DIR, "HEAD")
    with open(head_path) as f:
        head_content = f.read().strip()  # "ref: refs/heads/main"

    _, ref = head_content.split(" ", 1)
    return os.path.join(repo_path, GUDGIT_DIR, ref)


def _read_head_commit(repo_path: str = "."):
    """Returns the sha of the commit the current branch points to, or
    None if there's no commit yet (first commit in the repo)."""
    ref_path = _current_branch_ref_path(repo_path)
    if not os.path.exists(ref_path):
        return None
    with open(ref_path) as f:
        sha = f.read().strip()
    return sha or None


def _update_head_commit(new_sha: str, repo_path: str = "."):
    """Makes the current branch point to the newly created commit."""
    ref_path = _current_branch_ref_path(repo_path)
    os.makedirs(os.path.dirname(ref_path), exist_ok=True)
    with open(ref_path, "w") as f:
        f.write(new_sha + "\n")


def commit(message: str, repo_path: str = ".", author: str = "You <you@example.com>") -> str:
    """Creates a commit from the CURRENT state of the working
    directory (no index -- every file present gets included, every
    time). Steps, in order:

      1. Build the whole tree straight from disk (DFS, bottom-up --
         see Tree.build_from_directory).
      2. Write that tree, get its sha.
      3. Find the current commit (if any) to use as this commit's
         parent -- read from the current branch's ref file.
      4. Build and write the Commit object itself.
      5. Point the current branch at the new commit sha.

    Returns the new commit's sha.
    """
    tree = Tree.build_from_directory(repo_path, repo_path)
    tree_sha = tree.write(repo_path)

    parent_sha = _read_head_commit(repo_path)
    parents = [parent_sha] if parent_sha else []

    timestamp = f"{int(time.time())} +0000"
    author_line = f"{author} {timestamp}"

    commit_obj = Commit(
        tree=tree_sha,
        parents=parents,
        author=author_line,
        committer=author_line,
        message=message,
    )
    commit_sha = commit_obj.write(repo_path)

    _update_head_commit(commit_sha, repo_path)
    return commit_sha

def restore(commit_sha: str, repo_path: str = "."):
    """Restores the working tree to the snapshot represented by commit_sha."""
    commit_obj = Commit.read(commit_sha, repo_path)
    tree = Tree.read(commit_obj.tree, repo_path)

    def restore_tree(tree_obj: Tree, current_path: str):
        for name, entry_type, sha in tree_obj.entries:
            path = os.path.join(current_path, name)

            if entry_type == "blob":
                blob = Blob.read(sha, repo_path)
                with open(path, "wb") as f:
                    f.write(blob.content)

            elif entry_type == "tree":
                os.makedirs(path, exist_ok=True)
                subtree = Tree.read(sha, repo_path)
                restore_tree(subtree, path)

    restore_tree(tree, repo_path)


def log(repo_path: str = "."):
    """Returns the commit history starting from the current commit."""
    sha = _read_head_commit(repo_path)
    lines = []

    while sha:
        commit_obj = Commit.read(sha, repo_path)

        lines.append(f"commit {sha}")
        lines.append(f"Author: {commit_obj.author}")
        lines.append("")
        lines.append(f"    {commit_obj.message}")
        lines.append("")

        sha = commit_obj.parents[0] if commit_obj.parents else None
    return "\n".join(lines)