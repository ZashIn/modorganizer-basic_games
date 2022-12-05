from pathlib import Path

import mobase

from ..basic_features import BasicModDataChecker
from ..basic_features.basic_save_game_info import (
    BasicGameSaveGame,
    BasicGameSaveGameInfo,
)
from ..basic_game import BasicGame


class CyberpunkModDataChecker(BasicModDataChecker):
    default_file_patterns = {
        "valid": ["root", "archive", "engine", "r6"],
        "move": {
            "bin": "root/",
            "red4ext": "root/",
            "engine": "root/",
        },
    }
    _extra_root_mapping = {
        "r6/scripts": "root/r6/",
        "engine/tools": "root/engine/",
    }

    def dataLooksValid(
        self, filetree: mobase.IFileTree
    ) -> mobase.ModDataChecker.CheckReturn:
        res = super().dataLooksValid(filetree)
        if res is mobase.ModDataChecker.VALID and any(
            filetree.exists(path) for path in self._extra_root_mapping
        ):
            return mobase.ModDataChecker.FIXABLE
        return res

    def fix(self, filetree: mobase.IFileTree) -> mobase.IFileTree | None:
        new_filetree = super().fix(filetree)
        if new_filetree is None:
            return None
        for source, target in self._extra_root_mapping.items():
            if entry := new_filetree.find(source):
                parent = entry.parent()
                new_filetree.move(entry, target)
                # Remove empty folder
                if parent is not None and not bool(parent):
                    parent.detach()
        return new_filetree


class Cyberpunk2077Game(BasicGame):
    Name = "Cyberpunk 2077 Support Plugin"
    Author = "6788, Zash"
    Version = "2.0"

    GameName = "Cyberpunk 2077"
    GameShortName = "cyberpunk2077"
    GameBinary = "bin/x64/Cyberpunk2077.exe"
    GameLauncher = "REDprelauncher.exe"
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

    def init(self, organizer: mobase.IOrganizer) -> bool:
        super().init(organizer)
        self._featureMap[mobase.SaveGameInfo] = BasicGameSaveGameInfo(
            lambda p: Path(p or "", "screenshot.png"),
        )
        self._featureMap[mobase.ModDataChecker] = CyberpunkModDataChecker()
        return True

    def listSaves(self, folder) -> list[mobase.ISaveGame]:
        ext = self._mappings.savegameExtension.get()
        return [
            BasicGameSaveGame(path.parent)
            for path in Path(folder.absolutePath()).glob(f"**/*.{ext}")
        ]

    def iniFiles(self):
        return ["UserSettings.json"]
