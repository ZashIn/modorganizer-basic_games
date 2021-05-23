# -*- encoding: utf-8 -*-

from __future__ import annotations

import fnmatch
import functools
import os
import pathlib
from collections import deque
from dataclasses import dataclass, field
from reprlib import recursive_repr
from typing import (
    Any,
    Callable,
    Collection,
    Iterable,
    Mapping,
    MutableMapping,
    Optional,
    Protocol,
    Union,
)

import mobase

CheckReturn = mobase.ModDataChecker.CheckReturn
WalkReturn = mobase.IFileTree.WalkReturn

EntrySortFunction = Callable[[mobase.FileTreeEntry, mobase.IFileTree], bool]
"""Sorting `FileTreeEntry` into `IFileTree` via function."""

EntrySortDefinition = Union[None, str, EntrySortFunction]
"""Sorting file or folder into `IFileTree` via str (folder name) or function.
None = keep.
"""

EntrySortDefinitionMapping = MutableMapping[str, EntrySortDefinition]
"""Mapping of ``{"source path": "target path" or EntrySortFunction()}``."""


@dataclass
class ModDataMappingChecker(mobase.ModDataChecker):
    """`mobase.ModDataChecker`, which uses path patterns to check and fix data
    trees.

    Example:
        An instance with::

            ModDataMappingChecker(
                ignore_patterns=["*.md"],
                mappings={
                    "folder/*.ext": "",
                    "*.ext": "folder/"
                }
            )

        - ignores and removes "*.md" files from tree
        - accepts "folder/*.ext"
        - accepts "*.ext" files and moves them into "folder/"
    """

    ignore_patterns: Collection[str] = field(default_factory=list)
    """Files and folders to ignore & remove from file tree."""

    mappings: EntrySortDefinitionMapping = field(default_factory=dict)
    """File/folder mappings, ``{"source": "target"}``, with target as a str or a function:

    - ``{"source": "target"}``: path to move a folder/file to.
      If ending on "/" or "\\", it moves source into target folder.
    - ``{"source": function(FileTreeEntry, IFileTree)}``: custom opteration with entry.
    """

    def __post_init__(self):
        super().__init__()

    def dataLooksValid(
        self, filetree: mobase.IFileTree
    ) -> mobase.ModDataChecker.CheckReturn:
        if not self.ignore_patterns and not self.mappings:
            # Accept everything
            return self.VALID
        tree_walker = CheckTreeWalker(
            ignore_patterns=self.ignore_patterns,
            mappings=self.mappings,
        )

        return tree_walker.check(filetree)

    def fix(self, filetree: mobase.IFileTree) -> Optional[mobase.IFileTree]:
        if not self.ignore_patterns and not self.mappings:
            return None
        tree_walker = FixTreeWalker(
            ignore_patterns=self.ignore_patterns, mappings=self.mappings
        )
        return tree_walker.fix(filetree)


@dataclass
class TreeWalker:
    ignore_patterns: Iterable[str] = field(default_factory=list)
    mappings: Mapping[str, Any] = field(default_factory=dict)

    unknown_entries: list[Union[mobase.FileTreeEntry, mobase.IFileTree]] = field(
        init=False, default_factory=list
    )
    mapping_counter: int = field(init=False)
    ignore_counter: int = field(init=False)
    root_tree: Optional[mobase.IFileTree] = field(init=False)

    def __post_init__(self):
        self.reset()

    def reset(self):
        self.mapping_counter: int = 0
        self.ignore_counter: int = 0
        self.root_tree: Optional[mobase.IFileTree] = None
        self.unknown_entries.clear()

    def _change_root_tree(self, new_tree: mobase.IFileTree):
        self.reset()
        self.root_tree = new_tree

    def walk(self, filetree: mobase.IFileTree) -> Optional[mobase.IFileTree]:
        """Walk the filetree recursively, calling `visit_entry` on each entry.

        If only a single unknown folder (entry = file tree) and no mapping matches were
        found, the folder will be checked recursively as new root (effectively unfolding
        the contents).

        Returns:
            The filetree without `unknown_entries` or ``None``.
        """
        self._change_root_tree(filetree)
        filetree.walk(self.visit_entry, sep=os.path.sep)
        n_unknown_entries = len(self.unknown_entries)
        if n_unknown_entries == 0:
            return filetree
        if n_unknown_entries == 1 and self.mapping_counter == 0:
            unknown_entry = self.unknown_entries[0]
            # Recurse into a single unknown folder, with no entries to map present.
            tree = convert_entry_to_tree(unknown_entry)
            if tree:
                return self.walk(tree)
        print("unknown:", self.unknown_entries)
        return None

    def visit_entry(
        self, path: str, entry: mobase.FileTreeEntry
    ) -> mobase.IFileTree.WalkReturn:
        """Callback function for `IFileTree.walk`."""
        entry_path = os.path.join(path, entry.name())

        # Check ignore_patterns
        for pattern in (os.path.normpath(p) for p in self.ignore_patterns):
            # Full match
            if fnmatch.fnmatch(entry_path, pattern):
                return self.ignore_match(entry, entry_path, pattern)
            elif is_relative_to(pathlib.PurePath(pattern), entry_path):
                # Continue into subtree
                return WalkReturn.CONTINUE

        # Check mappings
        for pattern, target in self.mappings.items():
            pattern = os.path.normpath(pattern)
            target = normpath_with_slash(target)
            if fnmatch.fnmatch(entry_path, pattern):
                # VALID only if everything is valid.
                return self.mapping_match(entry, entry_path, pattern, target)
            elif is_relative_to(pathlib.PurePath(pattern), entry_path):
                # Continue into subtree
                return WalkReturn.CONTINUE

        # Unknown entry
        return self.visit_unmatched(entry, entry_path)

    def ignore_match(
        self, entry: mobase.FileTreeEntry, entry_path: str, pattern: str
    ) -> WalkReturn:
        """Called on ignore match.

        Args:
            entry: The matched `FileTreeEntry`.
            entry_path: The path to the entry (including it), from its root tree.
            pattern: The matched pattern of the ignore list.

        Returns:
            `IFileTree.WalkReturn.SKIP`
        """
        self.ignore_counter += 1
        return WalkReturn.SKIP

    def mapping_match(
        self,
        entry: mobase.FileTreeEntry,
        entry_path: str,
        pattern: str,
        target: EntrySortDefinition,
    ) -> WalkReturn:
        """Called on mapping match.

        Args:
            entry: The matched `FileTreeEntry`.
            entry_path: The path to the entry (including it), from its root tree.
            pattern: The matched pattern/key of the mapping.
            target: The target/value of the mapping.

        Returns:
            `IFileTree.WalkReturn.SKIP`
        """
        self.mapping_counter += 1
        return WalkReturn.SKIP

    def visit_unmatched(
        self, entry: mobase.FileTreeEntry, entry_path: str
    ) -> WalkReturn:
        """Called on unmatched entry. Stops the tree walk.

        Args:
            entry: Unmatched `FileTreeEntry`.
            entry_path: The path to the entry (including it), from its root tree.

        Returns:
            `IFileTree.WalkReturn.STOP`
        """
        self.unknown_entries.append(entry)
        if not entry.isDir() or len(self.unknown_entries) > 1:
            # Stop on invalid file or multiple dirs.
            return WalkReturn.STOP
        # Skip single invalid dir, check rest of tree first.
        return WalkReturn.SKIP


@dataclass
class CheckTreeWalker(TreeWalker):
    check_status: mobase.ModDataChecker.CheckReturn = field(init=False)

    def reset(self):
        super().reset()
        self.check_status = CheckReturn.VALID

    def check(self, filetree: mobase.IFileTree) -> mobase.ModDataChecker.CheckReturn:
        """Checks if the filetree is for (`mobase.ModDataChecker.dataLooksValid`):
        - `VALID`: all files in right position
        - `FIXABLE`: files match a mapping, can be moved to right position
        - `INVALID`: tree has unknown files
        """
        result_tree = self.walk(filetree)
        if result_tree is filetree:
            if self.unknown_entries:
                # Unknown file(s) or folders
                self.check_status = CheckReturn.INVALID
            elif self.ignore_counter > 0:
                self.check_status = CheckReturn.FIXABLE
        else:
            # Root tree change
            if self.unknown_entries:
                # Unresolved unknown entries.
                self.check_status = CheckReturn.INVALID
            else:
                # Ensure fixable status with root tree change
                self.check_status = CheckReturn.FIXABLE
        return self.check_status

    def mapping_match(
        self,
        entry: mobase.FileTreeEntry,
        entry_path: str,
        pattern: str,
        target: EntrySortDefinition,
    ) -> WalkReturn:
        # Keep VALID status unless the entry does not match the target.
        if self.check_status is CheckReturn.VALID and target not in ("", entry_path):
            self.check_status = CheckReturn.FIXABLE
        return super().mapping_match(entry, entry_path, pattern, target)


@dataclass
class FixTreeWalker(TreeWalker):
    _action_queue: deque[BoundFunction] = field(init=False, default_factory=deque)
    _changed_folders: set[mobase.IFileTree] = field(init=False, default_factory=set)

    def reset(self):
        super().reset()
        self._action_queue.clear()
        self._changed_folders.clear()

    def fix(self, filetree: mobase.IFileTree) -> Optional[mobase.IFileTree]:
        """For `mobase.ModDataChecker.fix`."""
        print("fixing", filetree, ":")
        return_tree = self.walk(filetree)

        while self._action_queue:
            action = self._action_queue.popleft()
            print("fix:", action)
            action()

        while self._changed_folders:
            top_removed_tree = remove_empty_tree_and_parents(
                self._changed_folders.pop()
            )
            if top_removed_tree is not None:
                print("removing emptry tree:", top_removed_tree)
        print("result tree:", return_tree)
        return return_tree

    def ignore_match(
        self, entry: mobase.FileTreeEntry, entry_path: str, pattern: str
    ) -> WalkReturn:
        print("skipping", entry.name())
        self._action_queue.append(BoundFunction(entry.detach))

        parent = entry.parent()
        assert parent is not None
        self._changed_folders.add(parent)

        return super().ignore_match(entry, entry_path, pattern)

    def mapping_match(
        self,
        entry: mobase.FileTreeEntry,
        entry_path: str,
        pattern: str,
        target: EntrySortDefinition,
    ) -> WalkReturn:
        assert self.root_tree is not None
        if target is not None:
            action = None

            if callable(target):
                action = BoundFunction(target, entry, self.root_tree)
            elif target not in ("", entry_path):
                action = BoundFunction(
                    self.root_tree.move,
                    entry,
                    target,
                    policy=mobase.IFileTree.InsertPolicy.MERGE,
                )

            if action is not None:
                self._action_queue.append(action)
                parent = entry.parent()
                assert parent is not None
                self._changed_folders.add(parent)
        return super().mapping_match(entry, entry_path, pattern, target)


# Utility


def convert_entry_to_tree(entry: mobase.FileTreeEntry) -> Optional[mobase.IFileTree]:
    if not entry.isDir():
        return None
    if isinstance(entry, mobase.IFileTree):
        return entry
    if (parent := entry.parent()) is None:
        return None
    converted_entry = parent.find(
        entry.name(), mobase.FileTreeEntry.FileTypes.DIRECTORY
    )
    if isinstance(converted_entry, mobase.IFileTree):
        return converted_entry
    return None


# Added in python 3.9
try:
    is_relative_to = pathlib.PurePath.is_relative_to  # type: ignore
except AttributeError:

    def is_relative_to(
        self: pathlib.PurePath, *other: Union[str, os.PathLike[str]]
    ) -> bool:
        """Return True if the path is relative to another path or False."""
        try:
            self.relative_to(*other)
            return True
        except ValueError:
            return False


class PathLib(Protocol):
    """Protocol for base operations from `os.path`, `posixpath`, `ntpath`."""

    def normpath(self, path: str) -> str:
        ...

    def join(self, path: str, *paths: str) -> str:
        ...

    def split(self, path: str) -> tuple[str, str]:
        ...


def normpath_with_slash(path: str, pathlib: PathLib = os.path) -> str:  # type: ignore
    r"""Normalize a path, like `os.path.normpath`, but keeps a normalized
    trailing slash and uses "" for an empty path instead of ".".

    Examples:
        >>> import ntpath
        >>> normpath_with_slash(r'a\b/', ntpath)
        'a\\b\\'
        >>> normpath_with_slash('a/b', ntpath)
        'a\\b'
        >>> normpath_with_slash('a/', ntpath)
        'a\\'
        >>> normpath_with_slash('a', ntpath)
        'a'
        >>> normpath_with_slash('', ntpath)
        ''
    """
    head, tail = pathlib.split(path)
    if head:
        return pathlib.join(pathlib.normpath(head), tail)
    return tail  # No "." for empty head.


class BoundFunction(functools.partial):
    """Bind (all) arguments to a function."""

    def __call__(self):
        return super().__call__()

    @recursive_repr()
    def __repr__(self):
        """``[repr(bound_obj).]func_name(args)``, ``[]`` = optional"""
        args = [repr(x) for x in self.args]
        args.extend(f"{k}={v!r}" for (k, v) in self.keywords.items())
        bound = f"{repr(self.func.__self__)}." if self.func.__self__ else ""
        return f"{bound}{self.func.__name__}({', '.join(args)})"


def remove_empty_tree_and_parents(
    tree: Optional[mobase.IFileTree],
) -> Optional[mobase.IFileTree]:
    """Removes the tree and its parents if empty.

    Returns:
        The last (highest) removed tree or None.
    """
    last_tree = None
    while tree is not None and not tree:
        parent = tree.parent()
        tree.detach()
        last_tree = tree
        tree = parent
    return last_tree
