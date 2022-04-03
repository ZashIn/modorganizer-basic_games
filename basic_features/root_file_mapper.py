from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from PyQt5.QtCore import qInfo, qWarning

import mobase


class RootFileMapper(mobase.IPluginFileMapper):
    """Adding virtual file links for mod files to the game root folder.

    If you use the entire mod folder as root (by default with `mod_root_folder=""`),
    set the games data path (`IPluginGame.dataDirectory` / `BasicGame.GameDataPath`)
    to an unused folder.

    Args:
        root_mod_folder (optional): The subfolder from each mod to map to root
            (entire folder by default).
        root_extra_overwrite_files (optional): Extra files to be mapped to overwrite.
            E.g. files usually not installed by mods, but created after game launch
            in the game root.
        root_blacklist (optional): Folder & files not to map. Use lowercase / casefold.
        root_blacklist_existing (optional): blacklist existing files & folders.
            Defaults to True.
    """

    root_mod_folder: str = ""
    root_extra_overwrite_files = None  # type: Iterable[str]
    root_blacklist = None  # type: set[str]
    root_blacklist_existing: bool = True

    _organizer: mobase.IOrganizer

    def __init__(self):
        super().__init__()
        self.root_extra_overwrite_files = self.root_extra_overwrite_files or []
        self.root_blacklist = {s.casefold() for s in (self.root_blacklist or "")}

    def init(self, organizer: mobase.IOrganizer):
        self._organizer = organizer
        super().init(organizer)

    def mappings(self) -> list[mobase.Mapping]:
        game = self._organizer.managedGame()
        game_path = Path(game.gameDirectory().absolutePath())
        overwrite_path = Path(self._organizer.overwritePath())

        # Add data path to blacklist
        data_dir = Path(game.dataDirectory().absolutePath()).relative_to(game_path).name
        assert data_dir != ""  # data folder == root => conflicting mappings!
        self.root_blacklist.add(data_dir)

        return [
            *self._extra_overwrite_mappings(game_path, overwrite_path),
            *self._root_mappings(game_path, overwrite_path),
        ]

    def _extra_overwrite_mappings(
        self, game_path: Path, overwrite_path: Path
    ) -> Iterable[mobase.Mapping]:
        # Extra mappings: overwrite <-> root
        for file in self.root_extra_overwrite_files:
            if not (file_path := game_path / file).exists():
                yield self._overwrite_mapping(
                    overwrite_path / file, file_path, is_dir=False
                )

    def _root_mappings(
        self, game_path: Path, overwrite_path: Path
    ) -> Iterable[mobase.Mapping]:
        for mod_path in self._active_mod_paths():
            mod_name = mod_path.name
            if self.root_mod_folder:
                # Use mod_root_folder as root instead
                mod_path = mod_path / self.root_mod_folder
            if not mod_path.exists():
                continue

            for child in mod_path.iterdir():
                # Check blacklist
                if child.name.casefold() in self.root_blacklist:
                    qInfo(f"Skipping {child.name} ({mod_name})")
                    continue
                destination = game_path / child.name
                # Check existing
                if self.root_blacklist_existing and destination.exists():
                    qWarning(
                        f"Existing game files/folders are not linked: "
                        f"{destination.as_posix()} ({mod_name})"
                    )
                # Mapping: mod -> root
                yield self._mod_mapping(child, destination)
                if child.is_dir():
                    # Mapping: overwrite <-> root
                    yield self._overwrite_mapping(
                        overwrite_path / child.name, destination, is_dir=True
                    )

    def _active_mod_paths(self) -> Iterable[Path]:
        modlist = self._organizer.modList().allModsByProfilePriority()
        mods_parent_path = Path(self._organizer.modsPath())

        for mod in modlist:
            if self._organizer.modList().state(mod) & mobase.ModState.ACTIVE:
                yield mods_parent_path / mod

    def _mod_mapping(self, source: Path, destination: Path) -> mobase.Mapping:
        """Mapping: mod -> root"""
        return mobase.Mapping(
            source=source.as_posix(),
            destination=destination.as_posix(),
            is_directory=source.is_dir(),
            create_target=False,
        )

    def _overwrite_mapping(
        self, overwrite_source: Path, destination: Path, is_dir: bool
    ) -> mobase.Mapping:
        """Mapping: overwrite <-> root"""
        if is_dir:
            # Root folders in overwrite need to exits.
            overwrite_source.mkdir(parents=True, exist_ok=True)
        return mobase.Mapping(
            source=overwrite_source.as_posix(),
            destination=destination.as_posix(),
            is_directory=is_dir,
            create_target=True,
        )
