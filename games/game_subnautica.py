from __future__ import annotations

import fnmatch
import os
from pathlib import Path

import mobase
from PyQt6.QtCore import QDir

from ..basic_features import BasicModDataChecker, GlobPatterns
from ..basic_features.basic_save_game_info import (
    BasicGameSaveGame,
    BasicGameSaveGameInfo,
)
from ..basic_features.utils import is_directory
from ..basic_game import BasicGame


class SubnauticaModDataChecker(BasicModDataChecker):
    use_qmods: bool = False

    def __init__(self, patterns: GlobPatterns | None = None, use_qmods: bool = False):
        super().__init__(
            GlobPatterns(
                unfold=["BepInExPack_Subnautica"],
                valid=[
                    "BepInEx",
                    "doorstop_libs",
                    "doorstop_config.ini",
                    "run_bepinex.sh",
                    "winhttp.dll",
                    "QMods",
                    ".doorstop_version",  # Added in Tobey's BepInEx Pack for Subnautica v5.4.23
                    "changelog.txt",
                    "libdoorstop.dylib",
                ],
                delete=[
                    "*.txt",
                    "*.md",
                    "icon.png",
                    "license",
                    "manifest.json",
                ],
                move={
                    "plugins": "BepInEx/",
                    "patchers": "BepInEx/",
                    "CustomCraft2SML": "QMods/" if use_qmods else "BepInEx/plugins/",
                    "CustomCraft3": "QMods/" if use_qmods else "BepInEx/plugins/",
                },
            ).merge(patterns or GlobPatterns()),
        )
        self.use_qmods = use_qmods

    def dataLooksValid(
        self, filetree: mobase.IFileTree
    ) -> mobase.ModDataChecker.CheckReturn:
        # fix: single root folders get traversed by Simple Installer
        parent = filetree.parent()
        if parent is not None and self.dataLooksValid(parent) is self.FIXABLE:
            return self.FIXABLE
        check_return = super().dataLooksValid(filetree)
        # A single unknown folder with a dll file in is to be moved to BepInEx/plugins/
        if (
            check_return is self.INVALID
            and len(filetree) == 1
            and is_directory(folder := filetree[0])
            and any(fnmatch.fnmatch(entry.name(), "*.dll") for entry in folder)
        ):
            return self.FIXABLE
        return check_return

    def fix(self, filetree: mobase.IFileTree) -> mobase.IFileTree:
        filetree = super().fix(filetree)
        if (
            self.dataLooksValid(filetree) is self.FIXABLE
            and len(filetree) == 1
            and is_directory(folder := filetree[0])
            and any(fnmatch.fnmatch(entry.name(), "*.dll") for entry in folder)
        ):
            filetree.move(folder, "QMods/" if self.use_qmods else "BepInEx/plugins/")
        return filetree


class SubnauticaGame(BasicGame, mobase.IPluginFileMapper):
    Name = "Subnautica Support Plugin"
    Author = "dekart811, Zash"
    Version = "2.3"

    GameName = "Subnautica"
    GameShortName = "subnautica"
    GameNexusName = "subnautica"
    GameSteamId = 264710
    GameEpicId = "Jaguar"
    GameBinary = "Subnautica.exe"
    GameDataPath = ""
    GameDocumentsDirectory = r"%GAME_PATH%"
    GameSupportURL = (
        r"https://github.com/ModOrganizer2/modorganizer-basic_games/wiki/"
        "Game:-Subnautica"
    )
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
        self._set_mod_data_checker()
        self._register_feature(
            BasicGameSaveGameInfo(lambda s: Path(s or "", "screenshot.jpg"))
        )

        organizer.onPluginSettingChanged(self._settings_change_callback)
        return True

    def _set_mod_data_checker(
        self, extra_patterns: GlobPatterns | None = None, use_qmod: bool | None = None
    ):
        self._register_feature(
            SubnauticaModDataChecker(
                patterns=(GlobPatterns() if extra_patterns is None else extra_patterns),
                use_qmods=(
                    bool(self._organizer.pluginSetting(self.name(), "use_qmods"))
                    if use_qmod is None
                    else use_qmod
                ),
            )
        )

    def _settings_change_callback(
        self,
        plugin_name: str,
        setting: str,
        old: mobase.MoVariant,
        new: mobase.MoVariant,
    ):
        if plugin_name == self.name() and setting == "use_qmods":
            self._set_mod_data_checker(use_qmod=bool(new))

    def settings(self) -> list[mobase.PluginSetting]:
        return [
            mobase.PluginSetting(
                "use_qmods",
                (
                    "Install */.dll mods in legacy QMods folder,"
                    " instead of BepInEx/plugins (default)."
                ),
                default_value=False,
            )
        ]

    def listSaves(self, folder: QDir) -> list[mobase.ISaveGame]:
        return [
            BasicGameSaveGame(folder)
            for save_path in (
                folder.absolutePath(),
                *(os.path.expandvars(p) for p in self._game_extra_save_paths),
            )
            for folder in Path(save_path).glob("slot*")
        ]

    def executables(self) -> list[mobase.ExecutableInfo]:
        binary = self.gameDirectory().absoluteFilePath(self.binaryName())
        return [
            mobase.ExecutableInfo(
                self.gameName(),
                binary,
            ).withArgument("-vrmode none"),
            mobase.ExecutableInfo(
                f"{self.gameName()} VR",
                self.gameDirectory().absoluteFilePath(self.binaryName()),
            ),
        ]

    def executableForcedLoads(self) -> list[mobase.ExecutableForcedLoadSetting]:
        return [
            mobase.ExecutableForcedLoadSetting(self.binaryName(), lib).withEnabled(True)
            for lib in self._forced_libraries
        ]

    def mappings(self) -> list[mobase.Mapping]:
        game_dir = self._organizer.managedGame().gameDirectory()

        # Save game file writes seem not compatible with USVFS:
        # exclude save folder from default root mappings (write back to game dir)
        return [
            mobase.Mapping(
                source=(source := game_dir.absoluteFilePath("SNAppData")),
                destination=source,
                is_directory=True,
                create_target=True,
            )
        ]
