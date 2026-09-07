import hashlib
import os
import zlib


class GudgitObjectError(Exception):
    """Base exception for object-related errors."""


class ObjectNotFoundError(GudgitObjectError):
    """Raised when an object does not exist."""


class CorruptObjectError(GudgitObjectError):
    """Raised when an object exists but is invalid/corrupted."""


class UnsupportedObjectError(GudgitObjectError):
    """Raised when an object has an unsupported type."""


class Object:
    """Base class for all Gudgit objects."""

    obj_type = None

    def __init__(self, content: bytes):
        self.content = content

    def serialize(self) -> bytes:
        return self.content

    def full_data(self) -> bytes:
        data = self.serialize()
        header = f"{self.obj_type} {len(data)}\0".encode()
        return header + data

    def hash(self) -> str:
        return hashlib.sha1(self.full_data()).hexdigest()

    def write(self, repo_path: str = ".") -> str:
        sha = self.hash()

        obj_dir = os.path.join(
            repo_path,
            ".gudgit",
            "objects",
            sha[:2],
        )

        os.makedirs(obj_dir, exist_ok=True)

        obj_path = os.path.join(obj_dir, sha[2:])

        if not os.path.exists(obj_path):
            compressed = zlib.compress(self.full_data())

            with open(obj_path, "wb") as f:
                f.write(compressed)

        return sha

    @staticmethod
    def read(sha: str, repo_path: str = "."):
        if not isinstance(sha, str) or len(sha) != 40:
            raise CorruptObjectError(
                f"invalid object id '{sha}'"
            )

        try:
            int(sha, 16)
        except ValueError:
            raise CorruptObjectError(
                f"invalid object id '{sha}'"
            )

        obj_path = os.path.join(
            repo_path,
            ".gudgit",
            "objects",
            sha[:2],
            sha[2:],
        )

        if not os.path.isfile(obj_path):
            raise ObjectNotFoundError(
                f"object '{sha}' not found"
            )

        try:
            with open(obj_path, "rb") as f:
                compressed = f.read()

            raw = zlib.decompress(compressed)

        except (OSError, zlib.error) as exc:
            raise CorruptObjectError(
                f"cannot read object '{sha}'"
            ) from exc

        try:
            header, content = raw.split(b"\0", 1)
            obj_type, size_text = header.decode().split(" ", 1)
            size = int(size_text)
        except (ValueError, UnicodeDecodeError):
            raise CorruptObjectError(
                f"invalid object header for '{sha}'"
            )

        if len(content) != size:
            raise CorruptObjectError(
                f"corrupted object '{sha}': size mismatch"
            )

        if obj_type == "blob":
            return Blob(content)

        if obj_type == "tree":
            return Tree.from_raw(content)

        if obj_type == "commit":
            return Commit.from_raw(content)

        raise UnsupportedObjectError(
            f"unsupported object type '{obj_type}'"
        )


class Blob(Object):
    """Stores the raw contents of a file."""

    obj_type = "blob"

    def __repr__(self):
        return f"Blob({len(self.content)} bytes)"


class Tree(Object):
    """
    Stores directory entries.

    Each entry is:

        <type> <name>\\0<20 raw SHA-1 bytes>

    where type is either 'blob' or 'tree'.
    """

    obj_type = "tree"

    def __init__(self, entries=None):
        self.entries = sorted(
            entries or [],
            key=self._sort_key,
        )

        super().__init__(self.serialize())

    @staticmethod
    def _sort_key(entry):
        name, entry_type, sha = entry
        return f"{name} {entry_type} {sha}"

    def serialize(self) -> bytes:
        data = bytearray()

        for name, entry_type, sha in self.entries:
            if entry_type not in ("blob", "tree"):
                raise CorruptObjectError(
                    f"invalid tree entry type '{entry_type}'"
                )

            try:
                sha_bytes = bytes.fromhex(sha)
            except ValueError:
                raise CorruptObjectError(
                    f"invalid SHA '{sha}' in tree"
                )

            if len(sha_bytes) != 20:
                raise CorruptObjectError(
                    f"invalid SHA '{sha}' in tree"
                )

            data.extend(
                f"{entry_type} {name}\0".encode()
            )
            data.extend(sha_bytes)

        return bytes(data)

    @classmethod
    def from_raw(cls, raw: bytes):
        entries = []
        i = 0

        while i < len(raw):
            try:
                null_idx = raw.index(b"\0", i)
            except ValueError as exc:
                raise CorruptObjectError(
                    "corrupted tree: missing null terminator"
                ) from exc

            try:
                header = raw[i:null_idx].decode()
                entry_type, name = header.split(" ", 1)
            except (UnicodeDecodeError, ValueError) as exc:
                raise CorruptObjectError(
                    "corrupted tree entry"
                ) from exc

            if entry_type not in ("blob", "tree"):
                raise CorruptObjectError(
                    f"invalid tree entry type '{entry_type}'"
                )

            sha_start = null_idx + 1
            sha_end = sha_start + 20

            if sha_end > len(raw):
                raise CorruptObjectError(
                    "corrupted tree: incomplete SHA"
                )

            sha = raw[sha_start:sha_end].hex()

            if not name:
                raise CorruptObjectError(
                    "corrupted tree: empty entry name"
                )

            entries.append(
                (name, entry_type, sha)
            )

            i = sha_end

        return cls(entries)

    @classmethod
    def build_from_directory(
        cls,
        dir_path: str,
        repo_path: str = ".",
    ):
        entries = []

        try:
            directory_entries = list(os.scandir(dir_path))
        except OSError as exc:
            raise GudgitObjectError(
                f"cannot read directory '{dir_path}'"
            ) from exc

        for entry in directory_entries:
            if entry.name == ".gudgit":
                continue

            if entry.is_file(follow_symlinks=False):
                try:
                    with open(entry.path, "rb") as f:
                        content = f.read()
                except OSError as exc:
                    raise GudgitObjectError(
                        f"cannot read file '{entry.path}'"
                    ) from exc

                blob = Blob(content)
                sha = blob.write(repo_path)

                entries.append(
                    (entry.name, "blob", sha)
                )

            elif entry.is_dir(follow_symlinks=False):
                subtree = cls.build_from_directory(
                    entry.path,
                    repo_path,
                )

                sha = subtree.write(repo_path)

                entries.append(
                    (entry.name, "tree", sha)
                )

        return cls(entries)

    def __repr__(self):
        return f"Tree({len(self.entries)} entries)"


class Commit(Object):
    """A commit points to a tree and zero or more parents."""

    obj_type = "commit"

    def __init__(
        self,
        tree: str,
        parents=None,
        author: str = "",
        committer: str = "",
        message: str = "",
    ):
        self.tree = tree
        self.parents = parents or []
        self.author = author
        self.committer = committer
        self.message = message

        super().__init__(self.serialize())

    def serialize(self) -> bytes:
        lines = [f"tree {self.tree}"]

        for parent in self.parents:
            lines.append(f"parent {parent}")

        lines.append(f"author {self.author}")
        lines.append(f"committer {self.committer}")
        lines.append("")
        lines.append(self.message)

        return "\n".join(lines).encode()

    @classmethod
    def from_raw(cls, raw: bytes):
        try:
            text = raw.decode()
            header_part, message = text.split("\n\n", 1)
        except (UnicodeDecodeError, ValueError) as exc:
            raise CorruptObjectError(
                "corrupted commit object"
            ) from exc

        tree = None
        parents = []
        author = ""
        committer = ""

        for line in header_part.split("\n"):
            if line.startswith("tree "):
                tree = line[5:]

            elif line.startswith("parent "):
                parents.append(line[7:])

            elif line.startswith("author "):
                author = line[7:]

            elif line.startswith("committer "):
                committer = line[10:]

        if not tree:
            raise CorruptObjectError(
                "corrupted commit: missing tree"
            )

        return cls(
            tree=tree,
            parents=parents,
            author=author,
            committer=committer,
            message=message,
        )

    def __repr__(self):
        return (
            f"Commit("
            f"tree={self.tree[:7]}, "
            f"parents={len(self.parents)}"
            f")"
        )