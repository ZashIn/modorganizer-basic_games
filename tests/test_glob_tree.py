import unittest
from collections.abc import Iterable, Mapping, Sized
from typing import Any
from unittest.mock import patch

from .mock_mobase import MockFileTree, MockFileTreeEntry, mobase_mock


def ilen(iter: Iterable[Any]):
    if isinstance(iter, Sized):
        return len(iter)
    return sum(1 for _ in iter)


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
