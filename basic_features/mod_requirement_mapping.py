# -*- encoding: utf-8 -*-

from __future__ import annotations

import os
import pathlib
from dataclasses import dataclass, field
from typing import Collection, Optional, Union

from .mod_data_mapping_checker import (
    EntrySortDefinitionMapping,
    ModDataMappingChecker,
    normpath_with_slash,
)
from .mod_requirement import IWithModRequirements, ModRequirement


@dataclass
class ModDataAndRequirementChecker(IWithModRequirements, ModDataMappingChecker):
    """`mobase.ModDataChecker`, which checks data trees using both
    `mappings` and/or `requirements` definitions
    (`ModRequirement`).

    If using a `ModRequirementMapping`, the patterns
    defined in each `ModRequirementMapping` are added to the `mappings`.

    Example:
        A definition::

            ModDataAndRequirementChecker(
                ignore_patterns=["*.md"],
                requirements=[
                    ModRequirementMapping(
                        "name",
                        nexus_id=123,
                        required_by=["folder/*.ext"].
                        installs=["install_folder", "some_file.ext"]
                    )
                ]
            )

        - ignores: "*.md" files
        - results in a mapping (by default)::

            mappings = {
                "install_folder": "", # valid
                "some_file.ext": "",  # valid
                "folder/*.ext": "",   # valid
                "*.ext": "folder/"    # mapped/moved to "folder/"
            }
    """

    requirements: Collection[Union[ModRequirement, ModRequirementMapping]] = field(
        default_factory=list
    )
    """Mod requirements, in search order. Use `ModRequirementMapping` to include
    the requirements in the mappings.
    """

    ignore_patterns: Collection[str] = field(default_factory=list)
    """files and folders to ignore & remove from file tree."""

    mappings: EntrySortDefinitionMapping = field(default_factory=dict)
    """File/folder mappings, ``{"source": "target"}``, with target as a str or a function:

    - ``{"source": "target"}``: path to move a folder/file to.
      If ending on "/" or "\\", it moves source into target folder.
    - ``{"source": function(FileTreeEntry, IFileTree)}``: custom opteration with entry.
    """

    def __post_init__(self):
        super().__post_init__()
        self.add_requriements_to_mappings()
        print("mappings:", self.mappings)

    def add_requriements_to_mappings(self):
        for req in self.requirements:
            if isinstance(req, ModRequirementMapping):
                self.mappings.update(req.archive_mapping)


@dataclass
class ModRequirementMapping(ModRequirement):
    """A requirement and mapping definition for mods used by
    `ModDataAndRequirementChecker`.

    Use `update_mapping` after a change to `custom_mapping`,
    `installs` and `required_by` (called on init).

    Example:
        An instance::

            ModRequirementMapping(
                "name",
                nexus_id=123,
                required_by=["folder/*.ext"],
                installs=["install_folder", "some_file.ext"]
            )

       results in a mapping (by default)::

            archive_mapping = {
                "install_folder": "", # valid
                "some_file.ext": "",  # valid
                "folder/*.ext": "",   # valid
                "*.ext": "folder/"    # mapped/moved to "folder/"
            }
    """

    required_by_add_to_mapping: bool = True
    """Add `reqired_by` patterns to `archive_mapping` (default)."""

    required_by_mapping_optional_folders: bool = True
    """Add mappings for each subfolder from `reqired_by`,
    making root folders optional. See `subfolder_mappings()` for details.
    """

    installs_add_to_mapping: bool = True
    """Add `installs` patterns to `archive_mapping` (default)."""

    custom_mapping: Optional[EntrySortDefinitionMapping] = None
    """File/folder mappings, ``{"source": "target"}``, with target as a str or a function:

    - ``{"source": "target"}``: path to move a folder/file to.
      If ending on "/" or "\\", it moves source into target folder.
    - ``{"source": function(FileTreeEntry, IFileTree)}``: custom opteration with entry.
    Use also for optional installed files.
    """

    _archive_mapping: EntrySortDefinitionMapping = field(init=False)

    def __post_init__(self, *args, **kwargs):
        super().__post_init__(*args, *kwargs)
        self.update_mapping()

    @property
    def archive_mapping(self) -> EntrySortDefinitionMapping:
        """Returns the folder/file mapping for archives.

        See also:
            `update_mapping()` for included mappings.
        """
        return self._archive_mapping

    def update_mapping(self):
        """Updates `archive_mapping` with:

        - `custom_mapping`
        - `installs` if `installs_add_to_mapping`
        - `required_by` if `required_by_add_to_mapping`,
            including `subfolder_mappings` with
            ``required_by_mapping_optional_folders = True``

        See also:
            `subfolder_mappings`
        """
        self._archive_mapping = {}
        if self.custom_mapping:
            self._archive_mapping.update(self.custom_mapping)
        if self.installs_add_to_mapping:
            self._add_to_mappings(self.installs, False)
        if self.required_by_add_to_mapping:
            self._add_to_mappings(
                self.required_by, self.required_by_mapping_optional_folders
            )

    def _add_to_mappings(
        self,
        patterns: Union[str, Collection[str]],
        add_subfolder_mappings: bool = False,
    ):
        """Add `patterns` to `archive_mapping`."""
        if isinstance(patterns, str):
            patterns = [patterns]
        for pattern in patterns:
            if add_subfolder_mappings:
                subfolder_mappings(pattern, mapping=self._archive_mapping)
            else:
                self._archive_mapping[os.path.normpath(pattern)] = ""


def subfolder_mappings(
    source_pattern: str,
    target_folder: Optional[str] = None,
    mapping: Optional[EntrySortDefinitionMapping] = None,
) -> EntrySortDefinitionMapping:
    r"""Add a mapping for each subfolder (makes root folders optional).

    For a pattern ending in a ``*`` placeholder, like ``"folder/*"``, the file pattern
    ``"*"`` will not be added seperately, since it would include all files and folders.

    Placeholders are only supported at the tail (last part)!

    Paths are normalized, while keeping trailing slashes.

    Args:
        source_pattern: The source folder / file pattern.
        target_folder (optional): The target folder to map to. Defaults to the
            folder path specified by source_pattern (e.g. ``"path_to/folder/*.ext"``).
        mapping (optional): The mapping to add to. Defaults to a new dict/mapping.

    Returns:
        Folder/file mapping.

    Examples:
        >>> print(subfolder_mappings('sub/folder/*.ext'))
        {'sub\\folder\\*.ext': '', 'folder\\*.ext': 'sub\\folder\\', '*.ext': 'sub\\folder\\'}
        >>> subfolder_mappings('sub/folder/')
        {'sub\\folder': '', 'folder': 'sub\\'}
        >>> subfolder_mappings('sub/folder/*')
        {'sub\\folder\\*': '', 'folder\\*': 'sub\\folder\\'}
        >>> subfolder_mappings('*.ext')
        {'*.ext': ''}
        >>> subfolder_mappings('*')
        {'*': ''}
    """  # noqa E501
    if mapping is None:
        mapping = {}
    # Trailing slashes are removed, optional for source pattern.
    source_pattern = os.path.normpath(source_pattern)
    source_folder, file_pattern = os.path.split(source_pattern)

    # Source already in right place.
    mapping[source_pattern] = ""

    # Add a mapping for each subfolder (optional root folders)
    if target_folder is None:
        # Ensure trailing slash on target folder. Important for IFileTree.move!
        target_folder = os.path.join(source_folder, "")
    else:
        target_folder = normpath_with_slash(target_folder)
    parts = pathlib.PurePath(source_folder).parts
    for i in range(1, len(parts)):
        mapping[os.path.join(*parts[i:], file_pattern)] = target_folder
    # Add file_pattern only if not matching everything.
    if file_pattern and file_pattern != "*":
        mapping[file_pattern] = target_folder
    return mapping
