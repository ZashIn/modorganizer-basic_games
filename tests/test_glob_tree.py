import unittest
from enum import Enum, auto
from pathlib import PurePath
from typing import Iterable, Self
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


def is_type(entry: MockFileTreeEntry, entry_type: MockFileTreeEntryTypes):
    match entry_type:
        case MockFileTreeEntryTypes.FILE:
            return entry.isFile()
        case MockFileTreeEntryTypes.DIRECTORY:
            return entry.isDir()
        case MockFileTreeEntryTypes.FILE_OR_DIRECTORY:
            return True


class MockFileTree(MockFileTreeEntry):
    def __init__(self, name: str, *entries_list: MockFileTreeEntry) -> None:
        super().__init__(name)
        self._entries: dict[str, MockFileTreeEntry] = {}
        for entry in entries_list:
            self._entries[entry._name] = entry

    def __hash__(self) -> int:
        return hash(self._name)

    def __iter__(self) -> Iterable[MockFileTreeEntry]:
        yield from self._entries.values()

    def find(
        self,
        str_path: str,
        entry_type: MockFileTreeEntryTypes = MockFileTreeEntryTypes.FILE_OR_DIRECTORY,
    ) -> Self | MockFileTreeEntry | None:
        path = PurePath(str_path)
        entry: MockFileTreeEntry | None = self
        for part in path.parts:
            entry = entry._entries.get(part, None)
            if entry is None or not is_type(entry, entry_type):
                return None
        return entry


mobase_mock = MagicMock()
# TODO: valid mock?
mobase_mock.FileTreeEntry = MockFileTreeEntry
# import mobase  # type: ignore # noqa: E402, F401, I001
# from basic_features.glob_tree import glob_tree  # noqa: E402

# def tearDownModule():
#     if mobase_patch:
#         mobase_patch.stop()


@patch.dict("sys.modules", mobase=mobase_mock)
class TestGlobTree(unittest.TestCase):
    def setUp(self) -> None:
        self.test_tree = MockFileTree(
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
        )

    def test_no_globbing(self):
        from basic_features.glob_tree import glob_tree

        self.assertEqual(
            len(res := list(glob_tree(self.test_tree, "folder1/file2.dll"))), 1
        )
        path, entry = res[0]
        self.assertEqual(path, "folder1/file2.dll")
        self.assertEqual(entry.name(), "file2.dll")

    def test_simple_globbing(self):
        from basic_features.glob_tree import glob_tree

        self.assertEqual(len(res := list(glob_tree(self.test_tree, "*/*.dll"))), 1)
        path, entry = res[0]
        self.assertEqual(path, "folder1/file2.dll")
        self.assertEqual(entry.name(), "file2.dll")

        self.assertEqual(
            len(res := list(glob_tree(self.test_tree, "folder*/*.dll"))), 1
        )
        path, entry = res[0]
        self.assertEqual(path, "folder1/file2.dll")
        self.assertEqual(entry.name(), "file2.dll")


if __name__ == "__main__":
    unittest.main()
