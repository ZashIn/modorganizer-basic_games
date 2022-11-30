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
        "valid": ["root", "archive", "engine", "mods", "r6", "red4ext"],
        "move": {
            "bin": "root/",
            # "red4ext": "root/",
            # "engine": "root/",
        },
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
    GameLauncher = "REDprelauncher.exe"
    GameDataPath = "mods"  # "%GAME_PATH%"
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
        "linkextensions": "asi,bin,dll,exe,ini,json,kark,lua,redscript,reds,toml,ts",
    }

    def init(self, organizer: mobase.IOrganizer) -> bool:
        super().init(organizer)
        self._featureMap[mobase.SaveGameInfo] = BasicGameSaveGameInfo(
            lambda p: Path(p or "", "screenshot.png"),
        )
        self._featureMap[mobase.ModDataChecker] = CyberpunkModDataChecker()

        self._organizer.onAboutToRun(self._pre_run_callback)

        # self._organizer.onUserInterfaceInitialized()
        self._set_root_builder_settings()
        return True

    def _set_root_builder_settings(self):
        # qInfo("RootBuilder on? " + str(self._organizer.isPluginEnabled("RootBuilder")))
        # TODO: warning about RootBuilder
        # TODO: set settings only once
        try:
            for setting, value in self._root_builder_config.items():
                self._organizer.setPluginSetting("RootBuilder", setting, value)
        except RuntimeError:
            # TODO: show message to install RootBuilder
            qInfo("ERROR RootBuilder not installed")

    def settings(self) -> list[mobase.PluginSetting]:
        return [
            mobase.PluginSetting(
                "skipStartScreen",
                'Skips the "Breaching..." start screen on game launch.',
                True,
            ),
            mobase.PluginSetting(
                "precompile_redscript",
                "Compiles redscript before game launch (better compatibility).",
                True,
            ),
            mobase.PluginSetting(
                "predeploy_redmod",
                "Deploys redmod before game launch (better compatibility with redscript)",
                True,
            ),
        ]

    def primaryPlugins(self):
        return ["RootBuilder"]

    def _pre_run_callback(self, path: str):
        if path == self.gameDirectory().absoluteFilePath(self.binaryName()):
            # TODO: run redmod only if started via "-modded"
            if self._organizer.pluginSetting(self.name(), "predeploy_redmod"):
                modded = bool((res := self._redmod_deploy()) and res[0])
            else:
                modded = False
            if self._organizer.pluginSetting(self.name(), "precompile_redscript"):
                self._redscript_compile(modded)
        return True

    def _redmod_deploy(self) -> tuple[bool, int] | None:
        r_path = Path(
            self.gameDirectory().absoluteFilePath("tools/redmod/bin/redMod.exe")
        )
        qInfo("REDMOD: " + str(r_path.exists()) + " " + str(r_path))
        if not r_path.exists():
            return None
        return self._organizer.waitForApplication(
            self._organizer.startApplication("REDmod deploy only")
        )

    def _redscript_compile(self, modded=False) -> tuple[bool, int] | None:
        """Compiles redscripts (into redmod modded folder with `modded=True`.
        Returns:
            if redmod is installed and activated, it returns the run result
            (see `IOrganizer.waitForApplication`)
            else None
        """
        if not (scc := self._redscript_path()):
            return None
        cache_dir = " -customCacheDir r6/cache/modded" if modded else ""
        return self._organizer.waitForApplication(
            self._organizer.startApplication(
                scc,
                args=f"-compile r6/scripts/{cache_dir}".split(" "),
                cwd=self.gameDirectory().absolutePath(),
            )
        )

    def _redscript_path(self, virtual=True) -> str:
        """Returns empty string if not found."""
        # TODO: virtual or not? => data path
        if virtual:
            tree = self._organizer.virtualFileTree()
            scc_path = "engine/tools/scc.exe"
            if tree.exists(scc_path):
                return self.dataDirectory().absoluteFilePath(scc_path)
            elif tree.exists(f"root/{scc_path}"):
                return self.gameDirectory().absoluteFilePath(scc_path)
            return ""
        else:
            scc_paths = self._organizer.findFiles(
                "engine/tools", lambda f: f == "scc.exe"
            )
            if not scc_paths:
                scc_paths = self._organizer.findFiles(
                    "root/engine/tools", lambda f: f == "scc.exe"
                )
            return scc_paths[0] if scc_paths else ""

    def executables(self) -> list[mobase.ExecutableInfo]:
        game_name = self.gameName()
        game_dir = self.gameDirectory()
        bin_path = game_dir.absoluteFilePath(self.binaryName())
        skip_start_screen = (
            " -skipStartScreen"
            if self._organizer.pluginSetting(self.name(), "skipStartScreen")
            else ""
        )
        execs = []
        # BUG: launcher does load redscripts
        if launcher := self.getLauncherName():
            execs.append(
                mobase.ExecutableInfo(
                    Path(launcher).stem,
                    QFileInfo(game_dir.absoluteFilePath(launcher)),
                )
            )
        return [
            *execs,
            # Without redmod
            mobase.ExecutableInfo(game_name, bin_path).withArgument(
                f"--launcher-skip{skip_start_screen}"
            ),
            # With redmod
            mobase.ExecutableInfo(
                f"{game_name} + REDmod",
                bin_path,
            ).withArgument(f"-modded{skip_start_screen}"),
            # Redmod deployment
            mobase.ExecutableInfo(
                "REDmod deploy only",
                QFileInfo(game_dir.absoluteFilePath("tools/redmod/bin/redMod.exe")),
            ).withArgument(
                f'deploy -root= "{game_dir.absolutePath()}"'
                " -rttiSchemaPath="
                f' "{game_dir.absoluteFilePath("tools/redmod/bin/../metadata.json")}"'
                " -reportProgress"
            ),
        ]

    def executableForcedLoads(self) -> list[mobase.ExecutableForcedLoadSetting]:
        return [
            mobase.ExecutableForcedLoadSetting(exe, lib).withEnabled(True)
            for exe in [self.binaryName(), self.getLauncherName()]
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

    def iniFiles(self):
        return ["UserSettings.json"]
