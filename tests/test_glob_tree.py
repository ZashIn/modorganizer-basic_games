import unittest
from collections.abc import Sized
from enum import Enum, auto
from pathlib import PurePath
from typing import (
    Any,
    Iterable,
    Mapping,
    Self,
)
from unittest.mock import MagicMock, patch


# mock mobase:
class MockFileTreeEntryTypes(Enum):
    FILE = auto()
    DIRECTORY = auto()
    FILE_OR_DIRECTORY = auto()


class MockFileTreeEntry:
    FILE = MockFileTreeEntryTypes.FILE
    DIRECTORY = MockFileTreeEntryTypes.DIRECTORY
    FILE_OR_DIRECTORY = MockFileTreeEntryTypes.FILE_OR_DIRECTORY

    def __init__(self, name: str) -> None:
        self._name = name

    def name(self) -> str:
        return self._name

    def isFile(self):
        return not self.isDir()

    def isDir(self):
        return isinstance(self, MockFileTree)


class MockFileTree(MockFileTreeEntry):
    _entries: dict[str, MockFileTreeEntry]

    def __init__(self, name: str, *entries_list: MockFileTreeEntry) -> None:
        super().__init__(name)
        self._entries = {entry.name(): entry for entry in entries_list}

    def __hash__(self) -> int:
        return hash(self._name)

    def __iter__(self) -> Iterable[MockFileTreeEntry]:
        yield from self._entries.values()

    def find(
        self,
        str_path: str,
        entry_type: MockFileTreeEntryTypes = MockFileTreeEntryTypes.FILE_OR_DIRECTORY,
    ) -> Self | MockFileTreeEntry | None:
        if not str_path:
            return None
        path = PurePath(str_path)
        entry = self
        for part in path.parts:
            if not isinstance(entry, MockFileTree):
                return None
            entry = entry._entries.get(part, None)
        if entry is None or not is_type(entry, entry_type):
            return None
        return entry


def is_type(entry: MockFileTreeEntry, entry_type: MockFileTreeEntryTypes) -> bool:
    match entry_type:
        case MockFileTreeEntryTypes.FILE:
            return entry.isFile()
        case MockFileTreeEntryTypes.DIRECTORY:
            return entry.isDir()
        case MockFileTreeEntryTypes.FILE_OR_DIRECTORY:
            return True


def ilen(iter: Iterable[Any]):
    if isinstance(iter, Sized):
        return len(iter)
    return sum(1 for _ in iter)


mobase_mock = MagicMock()
mobase_mock.FileTreeEntry = MockFileTreeEntry
mobase_mock.IFileTree = MockFileTree


@patch.dict("sys.modules", mobase=mobase_mock)
class TestGlobTree(unittest.TestCase):
    def setUp(self) -> None:
        self.tree: Any = MockFileTree(
            "",
            MockFileTree(
                "folder1",
                MockFileTreeEntry("file1.foo"),
                MockFileTreeEntry("file2.dll"),
            ),
            MockFileTree(
                "folder2",
                MockFileTreeEntry("file1.foo"),
                MockFileTreeEntry("file2.bar"),
            ),
            MockFileTreeEntry("file1.dll"),
            MockFileTreeEntry("file2.foo"),
            MockFileTree(
                "folder3",
                MockFileTree(
                    "folder4",
                    MockFileTreeEntry("file3.dll"),
                ),
            ),
        )

    def assertGlobEqual(
        self, pattern_res_list: Mapping[str, list[str]], pre_text: str = ""
    ):
        from basic_features.glob_tree import glob_tree

        for pattern, paths in pattern_res_list.items():
            with self.subTest(f"{pre_text}{pattern} = {paths}"):
                self.assertListEqual(
                    [p for p, _ in glob_tree(self.tree, pattern)], paths
                )

    def test_no_globbing(self):
        from basic_features.glob_tree import glob_tree

        self.assertListEqual(
            [
                (path, entry.name())
                for path, entry in glob_tree(self.tree, "folder1/file2.dll")
            ],
            [("folder1/file2.dll", "file2.dll")],
        )
        self.assertGlobEqual({"file1.dll/": []}, "folder only")

    def test_simple_globbing(self):
        from basic_features.glob_tree import glob_tree

        self.assertEqual(ilen(glob_tree(self.tree, "*")), 5)
        self.assertEqual(ilen(glob_tree(self.tree, "*.*")), 2)
        self.assertEqual(ilen(glob_tree(self.tree, "*/")), 3)
        self.assertGlobEqual(
            {
                "*.dll": ["file1.dll"],
                "*/*.dll": ["folder1/file2.dll"],
                "folder*/*.dll": ["folder1/file2.dll"],
            },
        )

    def test_unsupported_features(self):
        from basic_features.glob_tree import glob_tree

        for pattern in ["", "/", "folder1/../*.dll", "**.dll", "**/**/*.dll"]:
            with self.subTest(pattern=pattern):
                with self.assertRaises(ValueError):
                    any(glob_tree(self.tree, pattern))

    def test_recursive_globbing(self):
        from basic_features.glob_tree import glob_tree

        with self.subTest("** = all"):
            self.assertEqual(
                len(res := [p for p, _ in glob_tree(self.tree, "**")]), 11, res
            )
        self.assertGlobEqual(
            {
                "**/*.dll": [
                    "folder1/file2.dll",
                    "file1.dll",
                    "folder3/folder4/file3.dll",
                ],
                "folder1/**": [
                    "folder1/file1.foo",
                    "folder1/file2.dll",
                ],
            },
        )
