from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

try:
    from PyQt6.QtCore import QDir, QFileInfo, qInfo, qWarning, qCritical
except ImportError:
    from PyQt5.QtCore import QDir, QFileInfo, qInfo, qWarning, qCritical  # type: ignore

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
            "*.archive": "archive/pc/mod",
            "*.xl": "archive/pc/mod",
            "bin": "root/",  # CET, red4ext
            # redscript
            "engine": "root/",
            "r6": "root/",
            "red4ext": "root/",
            # redmod
            # "*": "mods",
        },
    }

    def dataLooksValid(
        self, filetree: mobase.IFileTree
    ) -> mobase.ModDataChecker.CheckReturn:
        # fix: single root folders get traversed by Simple Installer
        if filetree.parent() is not None:
            return self.CheckReturn.INVALID
        if (
            res := super().dataLooksValid(filetree)
        ) is self.CheckReturn.INVALID and all(self._valid_redmod(e) for e in filetree):
            return self.CheckReturn.FIXABLE
        return res

    def fix(self, filetree: mobase.IFileTree) -> mobase.IFileTree | None:
        # Check for correct redmod format
        tree = super().fix(filetree) or filetree
        for entry in tree:
            if not self._regex["valid"].match(
                entry.name().casefold()
            ) and self._valid_redmod(entry):
                tree.move(entry, "mods/")
        return tree

    def _valid_redmod(self, filetree: mobase.IFileTree | mobase.FileTreeEntry) -> bool:
        return isinstance(filetree, mobase.IFileTree) and bool(
            filetree and filetree.find("info.json")
        )


class Cyberpunk2077Game(BasicGame, mobase.IPluginFileMapper):
    Name = "Cyberpunk 2077 Support Plugin"
    Author = "6788, Zash"
    Version = "2.0"

    GameName = "Cyberpunk 2077"
    GameShortName = "cyberpunk2077"
    GameBinary = "bin/x64/Cyberpunk2077.exe"
    GameLauncher = "REDprelauncher.exe"
    GameDataPath = "_ROOT"

    GameDocumentsDirectory = "%USERPROFILE%/AppData/Local/CD Projekt Red/Cyberpunk 2077"
    GameSavesDirectory = "%USERPROFILE%/Saved Games/CD Projekt Red/Cyberpunk 2077"
    GameSaveExtension = "dat"
    GameSteamId = 1091500
    GameGogId = 1423049311
    GameSupportURL = (
        r"https://github.com/ModOrganizer2/modorganizer-basic_games/wiki/"
        "Game:-Cyberpunk-2077"
    )

    _root_mapping_blacklist = {GameDataPath.casefold(), "root", "bin"}

    _root_builder_config: dict[str, mobase.MoVariant] = {
        "usvfsmode": False,  # True,  # does not work with CET
        "linkmode": True,
        "backup": True,
        "cache": True,
        "autobuild": True,
        "redirect": True,
        "installer": False,
        "exclusions": "archive/pc/content,BonusContent,setup_redlauncher.exe,tools",
        "linkextensions": (
            # redscript, red4ext
            "dll,exe"
            # CET - does NOT work with USVFS writing to overwrite! => copy mode
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

        self._organizer.onUserInterfaceInitialized(
            lambda _: self._set_root_builder_settings()
        )
        self._organizer.onAboutToRun(self._pre_run_callback)
        return True

    def _set_root_builder_settings(self) -> None:
        if not self._organizer.isPluginEnabled("RootBuilder"):
            qWarning("RootBuilder not enabled, but required for most mods!")
        # TODO: warning about RootBuilder
        if not self._organizer.pluginSetting(self.name(), "set_rootbuilder_settings"):
            return
        try:
            for setting, value in self._root_builder_config.items():
                self._organizer.setPluginSetting("RootBuilder", setting, value)
            # Set the settings only once to keep user changes
            self._organizer.setPluginSetting(
                self.name(), "set_rootbuilder_settings", False
            )
        except RuntimeError:
            # TODO: show message to install RootBuilder
            qCritical("ERROR RootBuilder not installed")

    def settings(self) -> list[mobase.PluginSetting]:
        return [
            mobase.PluginSetting(
                "skipStartScreen",
                'Skips the "Breaching..." start screen on game launch.',
                True,
            ),
            mobase.PluginSetting(
                "predeploy_redmod",
                "Deploys redmod before game launch",
                True,
            ),
            mobase.PluginSetting(
                "set_rootbuilder_settings",
                "Sets rootbuilder settings on (next) MO2 start",
                True,
            ),
        ]

    def _pre_run_callback(self, path: str) -> bool:
        # TODO: run redmod only if started via "-modded"
        if not self._organizer.pluginSetting(self.name(), "predeploy_redmod"):
            return True
        if path == self.gameDirectory().absoluteFilePath(self.binaryName()):
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

    def executables(self) -> list[mobase.ExecutableInfo]:
        game_name = self.gameName()
        game_dir = self.gameDirectory()
        bin_path = game_dir.absoluteFilePath(self.binaryName())
        skip_start_screen = (
            " -skipStartScreen"
            if self._organizer.pluginSetting(self.name(), "skipStartScreen")
            else ""
        )
        execs = [
            # With redmod
            mobase.ExecutableInfo(
                f"{game_name} + REDmod",
                bin_path,
            ).withArgument(f"-modded{skip_start_screen}"),
            # Without redmod
            mobase.ExecutableInfo(game_name, bin_path).withArgument(
                f"--launcher-skip{skip_start_screen}"
            ),
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
        if launcher_name := self.getLauncherName():
            execs.append(
                mobase.ExecutableInfo(
                    Path(launcher_name).stem,
                    QFileInfo(game_dir.absoluteFilePath(launcher_name)),
                ).withArgument(f"-modded{skip_start_screen}")
            )
        return execs

    # Not needed with RootBuilder links / copies
    # def executableForcedLoads(self) -> list[mobase.ExecutableForcedLoadSetting]:
    #     return [
    #         mobase.ExecutableForcedLoadSetting(exe, lib).withEnabled(True)
    #         for exe in [self.binaryName(), self.getLauncherName()]
    #         for lib in [
    #             "bin/x64/version.dll",  # CET
    #             "bin/x64/d3d11.dll",  # Red4ext
    #             "red4ext/RED4ext.dll",
    #             "bin/x64/nvngx.dll",  # FidelityFx Super Resolution
    #         ]
    #     ]

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
                if child.name.casefold() in self._root_mapping_blacklist:
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
