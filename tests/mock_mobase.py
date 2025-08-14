from collections.abc import Iterable
from enum import Enum, auto
from pathlib import PurePath
from typing import Self
from unittest.mock import MagicMock


class FileTypes(Enum):
    FILE = auto()
    DIRECTORY = auto()
    FILE_OR_DIRECTORY = auto()


# mock mobase:
class MockFileTreeEntry:
    FileTypes = FileTypes

    FILE = FileTypes.FILE
    DIRECTORY = FileTypes.DIRECTORY
    FILE_OR_DIRECTORY = FileTypes.FILE_OR_DIRECTORY

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
        entry_type: FileTypes = FileTypes.FILE_OR_DIRECTORY,
    ) -> Self | MockFileTreeEntry | None:
        if not str_path:
            return None
        path = PurePath(str_path)
        entry: MockFileTreeEntry | None = self
        for part in path.parts:
            if not isinstance(entry, MockFileTree):
                return None
            entry = entry._entries.get(part, None)
        if entry is None or not is_type(entry, entry_type):
            return None
        return entry


def is_type(entry: MockFileTreeEntry, entry_type: FileTypes) -> bool:
    match entry_type:
        case FileTypes.FILE:
            return entry.isFile()
        case FileTypes.DIRECTORY:
            return entry.isDir()
        case FileTypes.FILE_OR_DIRECTORY:
            return True


mobase_mock = MagicMock()
mobase_mock.FileTreeEntry = MockFileTreeEntry
mobase_mock.IFileTree = MockFileTreeEntry
