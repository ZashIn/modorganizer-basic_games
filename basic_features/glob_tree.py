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
    if not pattern:
        raise ValueError(f"Unacceptable pattern: {pattern}")
    if pattern.startswith(("/", "\\")):
        raise ValueError(f"Pattern must be relative: {pattern}")
    parts = PurePath(pattern).parts
    if not parts:
        raise ValueError(f"Unacceptable pattern: {pattern}")
    res: list[str | re.Pattern[str]] = []
    for i, part in enumerate(parts):
        if part == "*":
            res.append(part)
        elif part == "**":
            if i + 1 < len(parts) and parts[i + 1] == "**":
                raise ValueError("Invalid pattern: '**/**' not supported!")
            res.append(part)
        elif "**" in part:
            raise ValueError(
                "Invalid pattern: '**' can only be an entire path component"
            )
        elif ".." in part:
            raise ValueError(f".. parent selector not supported: {pattern}")
        elif has_glob_pattern(part):
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
    double_star: bool = False,
) -> Iterable[tuple[str, mobase.FileTreeEntry]]:
    # path ends with /
    simple_parts = 0
    re_pattern: re.Pattern[str] | None = None
    doublestar_part = False
    for part in parts:
        if part == "*":
            break
        if part == "**":
            doublestar_part = True
            break
        if isinstance(part, re.Pattern):
            re_pattern = part
            break
        simple_parts += 1
    else:
        # No glob patterns
        sub_path = "/".join(cast(Sequence[str], parts))
        if (entry := file_tree.find(sub_path)) is not None:
            yield path + sub_path, entry
        return

    if simple_parts:
        # Get non pattern part directly
        sub_path = "/".join(cast(Sequence[str], parts[:simple_parts]))
        entry = file_tree.find(sub_path, mobase.FileTreeEntry.DIRECTORY)
        if entry is None or not is_directory(entry):
            return
        file_tree = entry
        path = f"{path}{sub_path}/"
    rest = parts[simple_parts + 1 :]

    if doublestar_part:
        if rest:
            # **/...
            yield from _glob_tree(file_tree, path, rest, True)
        else:
            # .../**
            yield from _all_sub_entries(file_tree, path)
        return

    for entry in file_tree:
        name = entry.name()

        sub_path = path + name
        if not re_pattern or re_pattern.match(name):
            if not rest:
                yield sub_path, entry
            elif is_directory(entry):
                yield from _glob_tree(entry, sub_path + "/", rest, double_star)
        if double_star and is_directory(entry):
            yield from _glob_tree(entry, sub_path + "/", parts, double_star)


def _all_sub_entries(
    file_tree: mobase.IFileTree, path: str
) -> Iterable[tuple[str, mobase.FileTreeEntry]]:
    for entry in file_tree:
        sub_path = path + entry.name()
        yield sub_path, entry
        if is_directory(entry):
            yield from _all_sub_entries(entry, sub_path + "/")
