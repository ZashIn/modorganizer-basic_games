from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from PyQt5.QtCore import QDir, qWarning

import mobase

from ..basic_features import BasicModDataChecker
from ..basic_features.basic_save_game_info import (
    BasicGameSaveGame,
    BasicGameSaveGameInfo,
)
from ..basic_game import BasicGame


class SubnauticaModDataChecker(BasicModDataChecker):
    default_file_patterns = {
        "unfold": ["BepInExPack_Subnautica"],
        "valid": ["winhttp.dll", "doorstop_config.ini", "BepInEx", "QMods"],
        "delete": [
            "*.txt",
            "*.md",
            "icon.png",
            "license",
            "manifest.json",
        ],
        "move": {"plugins": "BepInEx/", "patchers": "BepInEx/", "*": "QMods/"},
    }


class SubnauticaGame(BasicGame, mobase.IPluginFileMapper):

    Name = "Subnautica Support Plugin"
    Author = "dekart811, Zash"
    Version = "2.0"

    GameName = "Subnautica"
    GameShortName = "subnautica"
    GameNexusName = "subnautica"
    GameSteamId = 264710
    GameBinary = "Subnautica.exe"
    GameDataPath = "_ROOT"  # Custom mappings to actual root folders below.
    GameDocumentsDirectory = r"%GAME_PATH%"
    GameSavesDirectory = r"%GAME_PATH%\SNAppData\SavedGames"
    _game_extra_save_paths = [
        r"%USERPROFILE%\Appdata\LocalLow\Unknown Worlds"
        r"\Subnautica\Subnautica\SavedGames"
    ]

    _forced_libraries = ["winhttp.dll"]

    def __init__(self):
        super().__init__()
        mobase.IPluginFileMapper.__init__(self)

    def init(self, organizer: mobase.IOrganizer) -> bool:
        super().init(organizer)
        self._featureMap[mobase.ModDataChecker] = SubnauticaModDataChecker()
        self._featureMap[mobase.SaveGameInfo] = BasicGameSaveGameInfo(
            lambda s: os.path.join(s, "screenshot.jpg")
        )
        return True

    def listSaves(self, folder: QDir) -> list[mobase.ISaveGame]:
        return [
            BasicGameSaveGame(folder)
            for save_path in (
                folder.absolutePath(),
                *(os.path.expandvars(p) for p in self._game_extra_save_paths),
            )
            for folder in Path(save_path).glob("slot*")
        ]

    def executableForcedLoads(self) -> list[mobase.ExecutableForcedLoadSetting]:
        return [
            mobase.ExecutableForcedLoadSetting(self.binaryName(), lib).withEnabled(True)
            for lib in self._forced_libraries
        ]

    def mappings(self) -> list[mobase.Mapping]:
        return list(self._root_mappings())

    def _root_mappings(self):
        game_dir = Path(self.gameDirectory().absolutePath())
        overwrite_path = Path(self._organizer.overwritePath())
        for mod_paths in self._active_mod_paths():
            for child in mod_paths.iterdir():
                destination = game_dir / child.name
                if destination.exists():
                    qWarning(
                        "Overwriting existing game files/folders:"
                        f" {destination.as_posix()}"
                    )
                yield mobase.Mapping(
                    source=child.as_posix(),
                    destination=destination.as_posix(),
                    is_directory=child.is_dir(),
                    create_target=False,
                )
                if child.is_dir():
                    overwrite_subdir = overwrite_path / child.name
                    overwrite_subdir.mkdir(parents=True, exist_ok=True)
                    yield mobase.Mapping(
                        source=overwrite_subdir.as_posix(),
                        destination=destination.as_posix(),
                        is_directory=True,
                        create_target=True,
                    )

    def _active_mod_paths(self) -> Iterable[Path]:
        modlist = self._organizer.modList().allModsByProfilePriority()
        mods_parent_path = Path(self._organizer.modsPath())
        for mod in modlist:
            if self._organizer.modList().state(mod) & mobase.ModState.ACTIVE:
                yield mods_parent_path / mod
