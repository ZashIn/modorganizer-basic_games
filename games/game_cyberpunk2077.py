import typing
from pathlib import Path

import mobase

from ..basic_features.basic_save_game_info import BasicGameSaveGame
from ..basic_game import BasicGame

# MO 2.4 compatibility
if typing.TYPE_CHECKING:
    from PyQt6.QtCore import QDir
else:
    try:
        from PyQt6.QtCore import QDir
    except ImportError:
        from PyQt5.QtCore import QDir


class CyberpunkLocalSaves(mobase.LocalSavegames):
    def __init__(self, my_game_save_dir: QDir):
        super().__init__()
        self._saves_dir = my_game_save_dir.absolutePath()

    def mappings(self, profile_save_dir: QDir):
        return [
            mobase.Mapping(
                source=profile_save_dir.absolutePath(),
                destination=self._saves_dir,
                is_directory=True,
                create_target=True,
            )
        ]

    def prepareProfile(self, profile: mobase.IProfile):
        return profile.localSavesEnabled()


class CyberpunkSaveGame(BasicGameSaveGame):
    _name_file = "NamedSave.txt"  # from mod: Named Saves

    def __init__(self, filepath: Path):
        super().__init__(filepath)
        try:  # Custom name from Named Saves
            with open(filepath / self._name_file) as file:
                self._name = file.readline()
        except FileNotFoundError:
            self._name = ""

    def getName(self) -> str:
        return self._name or super().getName()


class Cyberpunk2077Game(BasicGame):
    Name = "Cyberpunk 2077 Support Plugin"
    Author = "6788, Zash"
    Version = "1.2.1"

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

        self._featureMap[mobase.LocalSavegames] = CyberpunkLocalSaves(
            self.savesDirectory()
        )
        return True

    def iniFiles(self):
        return ["UserSettings.json"]

    def listSaves(self, folder: QDir) -> list[mobase.ISaveGame]:
        ext = self._mappings.savegameExtension.get()
        return [
            CyberpunkSaveGame(path.parent)
            for path in Path(folder.absolutePath()).glob(f"**/*.{ext}")
        ]
