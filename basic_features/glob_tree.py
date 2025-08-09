import fnmatch
import re
from collections.abc import Iterable
from pathlib import PurePath

import mobase

from .utils import is_directory

_glob_pattern_matcher = re.compile(r"[*?\[\]]")


def has_glob_pattern(test_str: str):
    return _glob_pattern_matcher.search(test_str)


def glob_tree(
    file_tree: mobase.IFileTree, pattern: str, path: str = ""
) -> Iterable[tuple[str, mobase.FileTreeEntry]]:
    pattern_path = PurePath(pattern)
    if not (parts := pattern_path.parts):
        raise ValueError("Unacceptable pattern: {!r}".format(pattern))
    only_dirs = pattern.endswith(("/", "\\"))
    yield from _glob_tree(file_tree, path, parts, only_dirs)


def _glob_tree(
    file_tree: mobase.IFileTree,
    path: str,
    parts: tuple[str, ...],
    only_dirs: bool = False,
) -> Iterable[tuple[str, mobase.FileTreeEntry]]:
    i = 0
    for part in parts:
        if has_glob_pattern(part):
            break
        i += 1
    len_parts = len(parts)
    if i == len_parts:
        # No glob patterns
        str_path = "/".join(parts)
        if (
            entry := file_tree.find(
                str_path,
                mobase.FileTreeEntry.DIRECTORY
                if only_dirs
                else mobase.FileTreeEntry.FILE_OR_DIRECTORY,
            )
        ) is not None:
            yield f"{path}/{str_path}", entry
        return
    if i > 0:
        # Get non pattern part directly
        str_path = "/".join(parts[:i])
        entry = file_tree.find("/".join(str_path), mobase.FileTreeEntry.DIRECTORY)
        if entry is None or not is_directory(entry):
            return
        file_tree = entry
        path = f"{path}/{str_path}"
    part = parts[i]
    rest = parts[i + 1 :]

    pattern = re.compile(fnmatch.translate(part)) if part == "*" else None
    for entry in file_tree:
        name = entry.name()
        if pattern and not pattern.match(name):
            continue
        str_path = f"{path}/{name}"
        if rest:
            if is_directory(entry):
                yield from _glob_tree(entry, str_path, rest, only_dirs)
        elif not (only_dirs and is_directory(entry)):
            yield str_path, entry
