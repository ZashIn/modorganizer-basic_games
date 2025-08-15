import fnmatch
import re
from collections.abc import Iterable, Sequence
from pathlib import PurePath
from typing import Literal, cast

import mobase

from .utils import is_directory

_glob_pattern_matcher = re.compile(r"[*?\[\]]")

PatternPart = str | re.Pattern[str] | Literal["*", "**"]


def glob_tree(
    file_tree: mobase.IFileTree, pattern: str, path: str = ""
) -> Iterable[tuple[str, mobase.FileTreeEntry]]:
    """Find paths/entries matching a unix style glob pattern.

    If `glob_pattern` ends with a slash ('/' or '\\'), only directories are yielded.

    Args:
        file_tree: `IFileTree`
        _pattern: Glob pattern to match the entries path.
        path (optional): Root path for the given file tree. Defaults to "".

    Yields:
        (path, entry)
    """
    parts = parse_glob_pattern(pattern)
    if path and not path.endswith("/"):
        path += "/"
    if pattern.endswith(("/", "\\")):
        for res_path, entry in _glob_tree_parts(file_tree, parts, path):
            if is_directory(entry):
                yield res_path, entry
    else:
        yield from _glob_tree_parts(file_tree, parts, path)


def parse_glob_pattern(pattern: str) -> list[PatternPart]:
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
                raise ValueError("Invalid pattern: '**/**' is not supported!")
            res.append(part)
        elif "**" in part:
            raise ValueError(
                "Invalid pattern: '**' can only be an entire path component"
            )
        elif ".." in part:
            raise ValueError(f".. parent selector not supported: {pattern}")
        elif has_wildcards(part):
            res.append(re.compile(fnmatch.translate(part)))
        else:
            res.append(part)
    return res


def has_wildcards(test_str: str):
    return _glob_pattern_matcher.search(test_str)


def _glob_tree_parts(
    file_tree: mobase.IFileTree,
    pattern_parts: Sequence[PatternPart],
    path: str = "",
    recursive: bool = False,
) -> Iterable[tuple[str, mobase.FileTreeEntry]]:
    """Glob the tree with a sequence of pattern parts, consisting of a regex pattern,
    `"*"`, `"**"` or a literal file tree entry name, as returned by `parse_glob_pattern`.

    Args:
        file_tree: `IFileTree` test Args
        pattern_parts: List of the path parts: regex,  `"*"`, `"**"` or name.
        path (optional): Path to the file tree,
            **must end with a slash ".../"**. Defaults to "".
        recursive (optional): Search for the pattern sequence recursive in the subtree, too.
            Same as preceding `pattern_parts` with "**". Defaults to False.

    Yields:
        (path, entry)

    See Also:
        parse_glob_pattern
    """
    simple_parts = 0
    re_pattern: re.Pattern[str] | None = None
    doublestar_part = False
    for part in pattern_parts:
        match part:
            case "*":
                break
            case "**":
                doublestar_part = True
                break
            case re.Pattern():
                re_pattern = part
                break
            case _:
                simple_parts += 1
    else:
        # No wildcards
        sub_path = "/".join(cast(Sequence[str], pattern_parts))
        if (entry := file_tree.find(sub_path)) is not None:
            yield path + sub_path, entry
        return

    if simple_parts:
        # Get non pattern part directly
        sub_path = "/".join(cast(Sequence[str], pattern_parts[:simple_parts]))
        entry = file_tree.find(sub_path, mobase.FileTreeEntry.DIRECTORY)
        if entry is None or not is_directory(entry):
            return
        file_tree = entry
        path = f"{path}{sub_path}/"
    rest = pattern_parts[simple_parts + 1 :]

    if doublestar_part:
        if rest:
            # **/...
            yield from _glob_tree_parts(file_tree, rest, path, True)
        else:
            # .../**
            yield from all_tree_entries(file_tree, path)
        return

    for entry in file_tree:
        name = entry.name()

        sub_path = path + name
        if not re_pattern or re_pattern.match(name):
            # match or "*" part"
            if not rest:
                yield sub_path, entry
            elif is_directory(entry):
                yield from _glob_tree_parts(entry, rest, sub_path + "/", recursive)
        if recursive and is_directory(entry):
            yield from _glob_tree_parts(entry, pattern_parts, sub_path + "/", recursive)


def all_tree_entries(
    file_tree: mobase.IFileTree, path_prefix: str = ""
) -> Iterable[tuple[str, mobase.FileTreeEntry]]:
    """Get all tree entries recursively.

    Args:
        file_tree: `IFileTree`
        path_prefix (optional): Prepend to each returned path. Defaults to "".

    Yields:
        (path, entry)
    """
    for entry in file_tree:
        sub_path = path_prefix + entry.name()
        yield sub_path, entry
        if is_directory(entry):
            yield from all_tree_entries(entry, sub_path + "/")
