import fnmatch
import re
from collections.abc import Iterable, Sequence
from pathlib import PurePath

import mobase

from .utils import is_directory

_glob_pattern_matcher = re.compile(r"[*?\[\]]")

PatternPart = str | re.Pattern[str]


def parse_pattern(pattern: str) -> list[PatternPart]:
    pattern_path = PurePath(pattern)
    parts = pattern_path.parts
    if not parts:
        raise ValueError(f"Unacceptable pattern: {pattern}")
    res: list[str | re.Pattern[str]] = []
    for i, part in enumerate(parts):
        if "**" in part:
            # TODO: **
            raise ValueError(f"** recursive pattern not supported: {pattern}")
            # raise ValueError("Invalid pattern: '**' can only be an entire path component")
        elif ".." in part:
            raise ValueError(f".. parent selector not supported: {pattern}")
        elif not part == "*" and has_glob_pattern(part):
            res[i] = re.compile(fnmatch.translate(part))
        res[i] = part
    return res


def has_glob_pattern(test_str: str):
    return _glob_pattern_matcher.search(test_str)


def glob_tree(
    file_tree: mobase.IFileTree, pattern: str, path: str = ""
) -> Iterable[tuple[str, mobase.FileTreeEntry]]:
    parts = parse_pattern(pattern)
    only_dirs = pattern.endswith(("/", "\\"))
    yield from _glob_tree(file_tree, path, parts, only_dirs)


def _glob_tree(
    file_tree: mobase.IFileTree,
    path: str,
    parts: Sequence[str | re.Pattern[str]],
    only_dirs: bool = False,
) -> Iterable[tuple[str, mobase.FileTreeEntry]]:
    i = 0
    str_parts: list[str] = []
    for part in parts:
        if part == "*" or isinstance(part, re.Pattern):
            pattern = part
            break
        str_parts.append(part)
        i += 1
    else:
        # No glob patterns
        str_path = "/".join(str_parts)
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
    # Get non pattern part directly
    str_path = "/".join(str_parts)
    entry = file_tree.find("/".join(str_path), mobase.FileTreeEntry.DIRECTORY)
    if entry is None or not is_directory(entry):
        return
    file_tree = entry
    path = f"{path}/{str_path}"
    rest = parts[i + 1 :]

    for entry in file_tree:
        name = entry.name()

        if pattern != "*" and not pattern.match(name):
            continue
        str_path = f"{path}/{name}"
        if rest:
            if is_directory(entry):
                yield from _glob_tree(entry, str_path, rest, only_dirs)
        elif not (only_dirs and is_directory(entry)):
            yield str_path, entry
