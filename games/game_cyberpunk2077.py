from __future__ import annotations

from pathlib import Path

try:
    from PyQt6.QtCore import QDir, QFileInfo, qInfo
except ImportError:
    from PyQt5.QtCore import QDir, QFileInfo, qInfo  # type: ignore

import mobase

from ..basic_features import BasicModDataChecker
from ..basic_features.basic_save_game_info import (
    BasicGameSaveGame,
    BasicGameSaveGameInfo,
)
from ..basic_game import BasicGame


class CyberpunkModDataChecker(BasicModDataChecker):
    default_file_patterns = {
        "valid": ["archive", "bin", "engine", "r6", "red4ext", "mods"]
    }


# class CyberpunkModDataChecker(BasicModDataChecker):
#     default_file_patterns = {
#         "valid": ["root", "archive", "engine", "r6"],
#         "move": {
#             "bin": "root/",
#             "red4ext": "root/",
#             "engine": "root/",
#         },
#     }
#     _extra_root_mapping = {
#         "r6/scripts": "root/r6/",
#         "engine/tools": "root/engine/",
#     }

#     def dataLooksValid(
#         self, filetree: mobase.IFileTree
#     ) -> mobase.ModDataChecker.CheckReturn:
#         res = super().dataLooksValid(filetree)
#         if res is mobase.ModDataChecker.VALID and any(
#             filetree.exists(path) for path in self._extra_root_mapping
#         ):
#             return mobase.ModDataChecker.FIXABLE
#         return res

#     def fix(self, filetree: mobase.IFileTree) -> mobase.IFileTree | None:
#         new_filetree = super().fix(filetree)
#         if new_filetree is None:
#             return None
#         for source, target in self._extra_root_mapping.items():
#             if entry := new_filetree.find(source):
#                 parent = entry.parent()
#                 new_filetree.move(entry, target)
#                 # Remove empty folder
#                 if parent is not None and not bool(parent):
#                     parent.detach()
#         return new_filetree


class Cyberpunk2077Game(BasicGame):
    Name = "Cyberpunk 2077 Support Plugin"
    Author = "6788, Zash"
    Version = "2.0"

    GameName = "Cyberpunk 2077"
    GameShortName = "cyberpunk2077"
    GameBinary = "bin/x64/Cyberpunk2077.exe"
    # GameLauncher = "REDprelauncher.exe"
    GameDataPath = "%GAME_PATH%"
    GameDocumentsDirectory = "%USERPROFILE%/AppData/Local/CD Projekt Red/Cyberpunk 2077"
    GameSavesDirectory = "%USERPROFILE%/Saved Games/CD Projekt Red/Cyberpunk 2077"
    GameSaveExtension = "dat"
    GameSteamId = 1091500
    GameGogId = 1423049311
    GameSupportURL = (
        r"https://github.com/ModOrganizer2/modorganizer-basic_games/wiki/"
        "Game:-Cyberpunk-2077"
    )

    _root_builder_config: dict[str, mobase.MoVariant] = {
        "usvfsmode": True,
        "linkmode": True,
        "backup": True,
        "cache": True,
        "autobuild": True,
        "redirect": True,
        "installer": False,
        "exclusions": "archive,*.archive,BonusContent,setup_redlauncher.exe,tools",
        "linkextensions": "asi,bin,dll,exe,ini,json,kark,lua,redscript",
    }

    def init(self, organizer: mobase.IOrganizer) -> bool:
        super().init(organizer)
        self._featureMap[mobase.SaveGameInfo] = BasicGameSaveGameInfo(
            lambda p: Path(p or "", "screenshot.png"),
        )
        self._featureMap[mobase.ModDataChecker] = CyberpunkModDataChecker()

        return True

    def settings(self) -> list[mobase.PluginSetting]:
        return [
            mobase.PluginSetting(
                "skipStartScreen",
                'Skips the "Breaching..." start screen on game launch.',
                True,
            )
        ]

    def primaryPlugins(self):
        return ["RootBuilder"]

    def executables(self) -> list[mobase.ExecutableInfo]:
        # TODO: run args = --skip-launcher -skipStartScreen / -modded
        game_dir = self.gameDirectory()
        bin_path = QFileInfo(game_dir.absoluteFilePath(self.binaryName()))
        without_redmod = mobase.ExecutableInfo(self.gameName(), bin_path).withArgument(
            "--launcher-skip"
        )
        with_redmod = mobase.ExecutableInfo(
            f"{self.gameName()} + REDmod",
            bin_path,
        ).withArgument("-modded")
        if self._organizer.pluginSetting(self.name(), "skipStartScreen"):
            without_redmod = without_redmod.withArgument("-skipStartScreen")
            with_redmod = with_redmod.withArgument("-skipStartScreen")

        # BUG: redmod + redscript
        # def run_callback(path: str):
        #     # TODO: callback with args?
        #     qInfo(f"run {path} == {bin_path.absoluteFilePath()}")
        #     if path == bin_path.absoluteFilePath():
        #         app = self._organizer.startApplication("REDmod deploy only")
        #         qInfo("run before: " + str(app))
        #         self._organizer.waitForApplication(app)
        #     return True

        # self._organizer.onAboutToRun(run_callback)

        return [
            without_redmod,
            with_redmod,
            mobase.ExecutableInfo(
                "REDmod deploy only",
                QFileInfo(game_dir.absoluteFilePath("tools/redmod/bin/redMod.exe")),
            ).withArgument(
                f'deploy -root= "{game_dir.absolutePath()}"'
                " -rttiSchemaPath="
                f' "{game_dir.absoluteFilePath("tools/redmod/bin/../metadata.json")}"'
                " -reportProgress"
            )
            # .withArgument("deploy")
            # .withArgument("-root=")
            # .withArgument(f'"{game_dir.absolutePath()}"')
            # .withArgument("-rttiSchemaPath= ")
            # .withArgument(
            #     f'"{game_dir.absoluteFilePath("tools/redmod/bin/../metadata.json")}"'
            # )
            # .withArgument("-reportProgress")
        ]

    def executableForcedLoads(self) -> list[mobase.ExecutableForcedLoadSetting]:
        return [
            mobase.ExecutableForcedLoadSetting(self.binaryName(), lib).withEnabled(True)
            for lib in [
                "bin/x64/version.dll",  # CET
                "bin/x64/d3d11.dll",  # Red4ext
                "red4ext/RED4ext.dll",
                "bin/x64/nvngx.dll",  # FidelityFx Super Resolution
            ]
        ]

    def listSaves(self, folder: QDir) -> list[mobase.ISaveGame]:
        ext = self._mappings.savegameExtension.get()
        return [
            BasicGameSaveGame(path.parent)
            for path in Path(folder.absolutePath()).glob(f"**/*.{ext}")
        ]

    def initializeProfile(self, path: QDir, settings: mobase.ProfileSetting):
        super().initializeProfile(path, settings)
        qInfo("RootBuilder on? " + str(self._organizer.isPluginEnabled("RootBuilder")))

        # Default settings
        # qInfo(
        #     "exclusions: "
        #     + str(self._organizer.pluginSetting("RootBuilder", "exclusions"))
        # )
        try:
            for setting, value in self._root_builder_config.items():
                self._organizer.setPluginSetting("RootBuilder", setting, value)
        except RuntimeError:
            # TODO: show message to install RootBuilder
            qInfo("ERROR RootBuilder not installed")
        # TODO: set settings only once

    def iniFiles(self):
        return ["UserSettings.json"]
