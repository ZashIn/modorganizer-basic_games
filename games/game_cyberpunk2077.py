from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

try:
    from PyQt6.QtCore import QDir, QFileInfo, qInfo, qWarning
    from PyQt6.QtWidgets import QMessageBox
except ImportError:
    from PyQt5.QtCore import QDir, QFileInfo, qInfo  # type: ignore
    from PyQt5.QtWidgets import QMessageBox  # type: ignore

import mobase

from ..basic_features import BasicModDataChecker
from ..basic_features.basic_save_game_info import (
    BasicGameSaveGame,
    BasicGameSaveGameInfo,
)
from ..basic_game import BasicGame


class CyberpunkModDataChecker(BasicModDataChecker):
    default_file_patterns = {
        "valid": ["root", "archive", "mods"],
        "move": {
            # archive and ArchiveXL
            # "archive": "root/",
            "*.archive": "archive/pc/mod",
            "*.xl": "archive/pc/mod",
            "bin": "root/",  # CET, red4ext
            # redscript
            "engine": "root/",
            "r6": "root/",
            "red4ext": "root/",
            # redmod
            # "mods": "",
        },
    }

    def dataLooksValid(
        self, filetree: mobase.IFileTree
    ) -> mobase.ModDataChecker.CheckReturn:
        # fix: single root folders get traversed by Simple Installer
        if filetree.parent() is not None:
            # if filetree.find("info.json"):
            #     return self.CheckReturn.FIXABLE
            # else:
            return self.CheckReturn.INVALID
        res = super().dataLooksValid(filetree)
        # TODO: redmod validation & fix
        # if mods := filetree.find("mods", mobase.FileTreeEntry.DIRECTORY):
        #     assert isinstance(mods, mobase.IFileTree)
        #     self._valid_redmod(mods)
        return res

    def fix(self, filetree: mobase.IFileTree) -> mobase.IFileTree | None:
        tree = super().fix(filetree)
        # Check for correct redmod format
        # if tree and (mods := tree.find("mods", mobase.FileTreeEntry.DIRECTORY)):
        #     assert isinstance(mods, mobase.IFileTree)
        #     for entry in mods:
        #         if not entry.isDir() or not mods.find(f"{entry.name}/info.json"):
        #             return None
        return tree

    def _valid_redmod(self, filetree: mobase.IFileTree) -> bool:
        return bool(filetree) and all(
            filetree.find(f"{entry.name}/info.json") for entry in filetree
        )


class Cyberpunk2077Game(BasicGame, mobase.IPluginFileMapper):
    Name = "Cyberpunk 2077 Support Plugin"
    Author = "6788, Zash"
    Version = "2.0"

    GameName = "Cyberpunk 2077"
    GameShortName = "cyberpunk2077"
    GameBinary = "bin/x64/Cyberpunk2077.exe"
    GameLauncher = "REDprelauncher.exe"
    GameDataPath = "_ROOT"  # "%GAME_PATH%"
    # "_Rootbuilder"  # "%GAME_PATH%"  # Use RootBuilder mapping only = clear folder structure

    GameDocumentsDirectory = "%USERPROFILE%/AppData/Local/CD Projekt Red/Cyberpunk 2077"
    GameSavesDirectory = "%USERPROFILE%/Saved Games/CD Projekt Red/Cyberpunk 2077"
    GameSaveExtension = "dat"
    GameSteamId = 1091500
    GameGogId = 1423049311
    GameSupportURL = (
        r"https://github.com/ModOrganizer2/modorganizer-basic_games/wiki/"
        "Game:-Cyberpunk-2077"
    )

    _root_blacklist = {GameDataPath.casefold(), "root", "bin"}

    _root_builder_config: dict[str, mobase.MoVariant] = {
        # "usvfsmode": True,
        # "linkmode": True,
        "usvfsmode": False,
        "linkmode": True,
        "backup": True,
        "cache": True,
        "autobuild": True,
        "redirect": True,
        "installer": False,
        "exclusions": "archive/pc/content,BonusContent,setup_redlauncher.exe,tools",
        "linkextensions": (  # "asi,bin,dll,exe,ini,json,kark,lua,otf,redscript,reds,sqlite3,toml,ts,ttf",
            # redscript, red4ext
            "dll,exe"
            # CET
            # BUG: generated json not linked => use copy mode
            ",asi,lua,ini"
            ",sqlite3,json,keep,kark,lua,otf,ttf"
            ",toml"  # redscript + cybercmd
        ),
    }

    def __init__(self):
        super().__init__()
        mobase.IPluginFileMapper.__init__(self)

    def init(self, organizer: mobase.IOrganizer) -> bool:
        super().init(organizer)
        self._featureMap[mobase.SaveGameInfo] = BasicGameSaveGameInfo(
            lambda p: Path(p or "", "screenshot.png"),
        )
        self._featureMap[mobase.ModDataChecker] = CyberpunkModDataChecker()

        self._organizer.onAboutToRun(self._pre_run_callback)
        self._qwindow = None

        def ui_init(window):
            self._qwindow = window
            self._set_root_builder_settings()

        self._organizer.onUserInterfaceInitialized(ui_init)
        return True

    def _set_root_builder_settings(self) -> None:
        qInfo("RootBuilder on? " + str(self._organizer.isPluginEnabled("RootBuilder")))
        # TODO: warning about RootBuilder
        # TODO: set settings only
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
                "predeploy_redmod",
                "Deploys redmod before game launch (better compatibility with redscript)",
                True,
            ),
            # mobase.PluginSetting(
            #     "precompile_redscript",
            #     "Compiles redscript before game launch (better compatibility).",
            #     True,
            # ),
        ]

    def _pre_run_callback(self, path: str) -> bool:
        # TODO: run redmod only if started via "-modded"
        if not self._organizer.pluginSetting(self.name(), "predeploy_redmod"):
            return True
        if path == self.gameDirectory().absoluteFilePath(self.binaryName()):
            # qtmbox = QMessageBox(
            #     QMessageBox.Icon.Question,
            #     "Precompile RedMod",
            #     f"Do you want to precompile REDmod before launch?",
            #     buttons=QMessageBox.StandardButton.Yes
            #     | QMessageBox.StandardButton.No
            #     | QMessageBox.StandardButton.Cancel,
            #     parent=self._qwindow,
            # )
            # if (choice := qtmbox.exec()) == QMessageBox.StandardButton.Yes:
            #     if redmod:
            #         modded = bool((res := self._redmod_deploy()) and res[0])
            # elif choice == QMessageBox.StandardButton.Cancel:
            #     return False
            if (res := self._redmod_deploy()) and not bool(res[0]):
                # TODO: show redmod deploy error
                return False
        return True

    def _redmod_deploy(self) -> tuple[bool, int] | None:
        if not Path(
            self.gameDirectory().absoluteFilePath("tools/redmod/bin/redMod.exe")
        ).exists():
            return None
        return self._organizer.waitForApplication(
            self._organizer.startApplication("REDmod deploy only")
        )

    # def _redscript_compile(self, modded=True) -> tuple[bool, int] | None:
    #     """Compiles redscripts (into redmod modded folder with `modded=True`.
    #     Returns:
    #         if redmod is installed and activated, it returns the run result
    #         (see `IOrganizer.waitForApplication`)
    #         else None
    #     """
    #     if not (scc := self._redscript_path()):
    #         return None
    #     cache_dir = " -customCacheDir r6/cache/modded" if modded else ""
    #     return self._organizer.waitForApplication(
    #         self._organizer.startApplication(
    #             scc,
    #             args=f"-compile r6/scripts/{cache_dir}".split(" "),
    #             cwd=self.gameDirectory().absolutePath(),
    #         )
    #     )

    # def _redscript_path(self, virtual=False) -> str:
    #     """Returns empty string if not found."""
    #     # TODO: virtual or not? => data path
    #     if virtual:
    #         tree = self._organizer.virtualFileTree()
    #         scc_path = "engine/tools/scc.exe"
    #         if tree.exists(scc_path):
    #             return self.dataDirectory().absoluteFilePath(scc_path)
    #         elif tree.exists(f"root/{scc_path}"):
    #             return self.gameDirectory().absoluteFilePath(scc_path)
    #         return ""
    #     else:
    #         scc_paths = self._organizer.findFiles(
    #             "engine/tools", lambda f: f == "scc.exe"
    #         )
    #         if not scc_paths:
    #             scc_paths = self._organizer.findFiles(
    #                 "root/engine/tools", lambda f: f == "scc.exe"
    #             )
    #         return scc_paths[0] if scc_paths else ""

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
            # Redmod
            # TODO: load order `-mod=modB,modA,modC` and -force (see https://github.com/E1337Kat/cyberpunk2077_ext_redux/issues/297)
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

    def mappings(self) -> list[mobase.Mapping]:
        game_path = Path(self.gameDirectory().absolutePath())
        overwrite_path = Path(self._organizer.overwritePath())

        return list(self._root_mappings(game_path, overwrite_path))

    def _root_mappings(
        self, game_path: Path, overwrite_path: Path
    ) -> Iterable[mobase.Mapping]:
        for mod_path in self._active_mod_paths():
            mod_name = mod_path.name

            for child in mod_path.iterdir():
                # Check blacklist
                if child.name.casefold() in self._root_blacklist:
                    qInfo(f"Skipping {child.name} ({mod_name})")
                    continue
                destination = game_path / child.name
                # Mapping: mod -> root
                isdir = child.is_dir()
                yield mobase.Mapping(
                    source=str(child),
                    destination=str(destination),
                    is_directory=isdir,
                    create_target=False,
                )
                yield self._overwrite_mapping(
                    overwrite_path / child.name, destination, is_dir=isdir
                )

    def _active_mod_paths(self) -> Iterable[Path]:
        mods_parent_path = Path(self._organizer.modsPath())
        modlist = self._organizer.modList().allModsByProfilePriority()
        for mod in modlist:
            if self._organizer.modList().state(mod) & mobase.ModState.ACTIVE:
                yield mods_parent_path / mod

    def _overwrite_mapping(
        self, overwrite_source: Path, destination: Path, is_dir: bool
    ) -> mobase.Mapping:
        """Mapping: overwrite <-> root"""
        if is_dir:
            # Root folders in overwrite need to exits.
            overwrite_source.mkdir(parents=True, exist_ok=True)
        return mobase.Mapping(
            str(overwrite_source),
            str(destination),
            is_dir,
            create_target=True,
        )
