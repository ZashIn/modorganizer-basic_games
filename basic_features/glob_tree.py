import fnmatch
import re
from collections.abc import Iterable, Sequence
from pathlib import PurePath
from typing import cast

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
    for part in parts:
        if "**" in part:
            # TODO: implement **, including children **/**/
            raise ValueError(f"** recursive pattern not supported: {pattern}")
            # raise ValueError("Invalid pattern: '**' can only be an entire path component")
        elif ".." in part:
            raise ValueError(f".. parent selector not supported: {pattern}")
        elif not part == "*" and has_glob_pattern(part):
            res.append(re.compile(fnmatch.translate(part)))
        else:
            res.append(part)
    return res


def has_glob_pattern(test_str: str):
    return _glob_pattern_matcher.search(test_str)


def glob_tree(
    file_tree: mobase.IFileTree, pattern: str, path: str = ""
) -> Iterable[tuple[str, mobase.FileTreeEntry]]:
    parts = parse_pattern(pattern)
    if path and not path.endswith("/"):
        path += "/"
    if pattern.endswith(("/", "\\")):
        for res_path, entry in _glob_tree(file_tree, path, parts):
            if is_directory(entry):
                yield res_path, entry
    else:
        yield from _glob_tree(file_tree, path, parts)


def _glob_tree(
    file_tree: mobase.IFileTree,
    path: str,
    parts: Sequence[str | re.Pattern[str]],
) -> Iterable[tuple[str, mobase.FileTreeEntry]]:
    # path ends with /
    i = 0
    pattern: re.Pattern[str] | None = None
    for part in parts:
        if part == "*":
            break
        if isinstance(part, re.Pattern):
            pattern = part
            break
        i += 1
    else:
        str_parts = cast(Sequence[str], parts)
        # No glob patterns
        sub_path = "/".join(str_parts)
        if (entry := file_tree.find(sub_path)) is not None:
            yield path + sub_path, entry
        return
    if i > 0:
        # Get non pattern part directly
        str_parts = cast(Sequence[str], parts[:i])
        sub_path = "/".join(str_parts)
        entry = file_tree.find(sub_path, mobase.FileTreeEntry.DIRECTORY)
        if entry is None or not is_directory(entry):
            return
        file_tree = entry
        path = f"{path}{sub_path}/"
    rest = parts[i + 1 :]

    for entry in file_tree:
        name = entry.name()

        if pattern and not pattern.match(name):
            continue
        sub_path = path + name
        if not rest:
            yield sub_path, entry
        elif is_directory(entry):
            yield from _glob_tree(entry, sub_path + "/", rest)
