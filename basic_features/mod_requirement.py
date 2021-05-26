# -*- encoding: utf-8 -*-

from __future__ import annotations

import fnmatch
import os
import pathlib
import types
from collections import defaultdict
from dataclasses import InitVar, dataclass, field
from typing import (
    Callable,
    Collection,
    Iterable,
    Mapping,
    NamedTuple,
    Optional,
    TypeVar,
    Union,
)

import mobase


class RequirementModFiles(NamedTuple):
    """A requirement and the associated mods with their files (relative to data folder).
    File dependencies without a mod origin are listed under ``mod_file_map[""]``.
    """

    requirement: ModRequirement
    mod_files: Mapping[str, list[str]]


class IWithModRequirements:
    """Mod requirement definitions (mixin) for a game (feature).

    Defines requirements in `requirements`,
    checks for missing requirements with
    `mods_with_missing_requirements`.
    """

    requirements: Collection[ModRequirement]
    """Mod requirements, in search order."""

    def __init__(self, requirements: Collection[ModRequirement] = None):
        if requirements is not None:
            self.requirements = requirements
        elif self.requirements is None:
            self.requirements = []
        super().__init__()

    def mods_with_missing_requirements(
        self, organizer: mobase.IOrganizer
    ) -> Iterable[RequirementModFiles]:
        """Returns missing requirements together with the mods and files depending on it.

        See also:
            `get_mod_file_map`
        """
        return (
            RequirementModFiles(req, get_mod_file_map(mod_files, organizer))
            for req, mod_files in self.files_with_missing_requirements(organizer)
        )

    def files_with_missing_requirements(
        self, organizer: mobase.IOrganizer
    ) -> Iterable[tuple[ModRequirement, Collection[str]]]:
        """Yields missing `(ModRequirement, [str])`."""
        return (
            (req, mod_files)
            for req in self.requirements
            if (mod_files := req.files_with_missing_requirements(organizer))
        )


def get_mod_file_map(
    abs_file_paths: Iterable[str], organizer: mobase.IOrganizer
) -> Mapping[str, list[str]]:
    """
    Args:
        abs_file_paths: absolute file paths, as returned by
            `mobase.IOrganizer.findFiles`.
        organizer: `mobase.IOrganizer`

    Returns:
        Mapping::

            {
                "mod name": ["mod files (relative paths)"],
                "": ["files without mod origin"]
            }
    """
    mod_map: defaultdict[str, list[str]] = defaultdict(list)
    for abs_file in abs_file_paths:
        rel_file = relative_to_data_folder(abs_file, organizer)
        if rel_file is None:
            continue
        mods = organizer.getFileOrigins(rel_file)
        if mods:
            for mod in mods:
                mod_map[mod].append(rel_file)
        else:
            mod_map[""].append(rel_file)
    return mod_map


def relative_to_data_folder(
    file_path: str, organizer: mobase.IOrganizer
) -> Optional[str]:
    """Get the file path relative to the data folder from the real absolute mod folder
    path.

    Args:
        file_path: The real absolute file path, as returned by `IOrganizer.findFiles`
        organizer: `mobase.IOrganizer` instance

    Returns:
        Path relative to the data folder or ``None`` if `file_path` could not be
        converted to a relative path.
    """
    try:
        # mods path
        path_rel_to_mods = pathlib.PurePath(file_path).relative_to(organizer.modsPath())
        return os.path.join(*path_rel_to_mods.parts[1:])
    except ValueError:
        try:
            # overwrite path
            return str(
                pathlib.PurePath(file_path).relative_to(organizer.overwritePath())
            )
        except ValueError:
            return None


SelfType = TypeVar("SelfType", bound="ModRequirement")


@dataclass
class ModRequirement:
    """A requirement definition for `IWithModRequirements`.

    Example:
        For files "folder/*.ext" the requirement is fullfilled, if the folder
        "install_folder" and file "install_file.ext" are installed::

            ModRequirement(
                "name",
                nexus_id=123,
                required_by=["folder/*.ext"],
                installs=["install_folder", "install_file.ext"]
            )

    """

    name: str

    required_by: Collection[str] = field(default_factory=list)
    """Patterns of the files depending on this requirement."""

    installs: Collection[str] = field(default_factory=list)
    """Files and folders installed by this requirement (all need to be present)."""

    nexus_id: int = 0

    url: str = ""
    """Custom url. For standard nexus url ("/game/mods/id"), use `nexus_id`."""

    problem_description: InitVar[
        Union[str, Callable[[ModRequirement, Optional[mobase.IOrganizer]], str]]
    ] = None
    """The problem description for an unfulfilled requirement.
    See `with_problem_description` for details.
    """

    _problem_description: Union[
        str, Callable[[Optional[mobase.IOrganizer]], str]
    ] = field(init=False)

    def __post_init__(self, problem_description):
        if problem_description is None:
            self.with_problem_description(type(self).default_problem_description)
        else:
            self.with_problem_description(problem_description)

    def with_problem_description(
        self: SelfType,
        problem_description: Union[
            str, Union[str, Callable[[SelfType, Optional[mobase.IOrganizer]], str]]
        ],
    ) -> SelfType:
        """Changes the problem description (for an unfulfilled requirement).

        Args:
            problem_description: A str or a callback, either::

                - str
                - function(self, mobase.IOrganizer) -> str
                - self.method(mobase.IOrganizer) -> str

        Returns:
            self reference.
        """
        if callable(problem_description):
            # Bind function to self.
            self._problem_description = types.MethodType(problem_description, self)
        else:
            self._problem_description = problem_description
        return self

    def default_problem_description(self, o: Optional[mobase.IOrganizer]) -> str:
        name = self.name
        if o is not None and (url := self.get_url(o.managedGame())):
            name = f'<a href="{url}">{name}</a>'
        return (
            "<p>You have one or more mods installed,"
            f" which require {name} to work.</p>"
        )

    def framework_description(self, o: Optional[mobase.IOrganizer]) -> str:
        """A problem description for frameworks, requiring a forced library.

        Set as problem_description with
        ``with_problem_description(framework_description)``.
        """
        if o is None:
            return ""
        return (
            self.default_problem_description(o)
            + f"<p>If you install {self.name} via Mod Organizer,"
            ' make sure "Force load libraries" under'
            f" Tools/Executables/{o.managedGame().gameName()} is enabled,"
            ' with the required libraries configured under "Configure Libraries"</p>'
        )

    def get_problem_description(
        self, organizer: Optional[mobase.IOrganizer] = None
    ) -> str:
        """Get the problem description (for an unfulfilled requirement)."""
        return (
            self._problem_description(organizer)
            if callable(self._problem_description)
            else self._problem_description
        )

    def get_url(self, game: mobase.IPluginGame) -> str:
        """Get url either from `url` or `nexus_id`."""
        if self.url:
            return self.url
        if self.nexus_id:
            return nexus_url(game, self.nexus_id)
        return ""

    def fulfilled(self, organizer: mobase.IOrganizer) -> bool:
        installed_files = (find(p, organizer) for p in self.installs)
        return all(installed_files)

    def files_with_missing_requirements(
        self, organizer: mobase.IOrganizer
    ) -> Collection[str]:
        """Returns the files, which are missing this requirement if any."""
        mod_files = set()
        if not self.fulfilled(organizer):
            for p in self.required_by:
                required_by_files = find(p, organizer)
                mod_files.update(required_by_files)
        return mod_files


def find(path: str, organizer: mobase.IOrganizer) -> list[str]:
    """Find files or folders matching path. Placeholder supported in tail / last path
    segment."""
    folder, file = os.path.split(path)
    if file:
        return organizer.findFiles(folder, file)
    path, folder = os.path.split(folder)
    return fnmatch.filter(organizer.listDirectories(path), folder)


def nexus_url(game: mobase.IPluginGame, nexus_id: int) -> str:
    return f"https://www.nexusmods.com/{game.gameNexusName()}/mods/{nexus_id}"
