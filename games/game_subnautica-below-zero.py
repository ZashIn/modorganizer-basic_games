from __future__ import annotations

import mobase

from . import game_subnautica  # namespace to not load SubnauticaGame here, too!


class SubnauticaBelowZeroGame(game_subnautica.SubnauticaGame):

    Name = "Subnautica Below Zero Support Plugin"
    Author = "dekart811, Zash"
    Version = "2.0"

    GameName = "Subnautica: Below Zero"
    GameShortName = "subnauticabelowzero"
    GameNexusName = "subnauticabelowzero"
    GameSteamId = 848450
    GameBinary = "SubnauticaZero.exe"
    GameDataPath = ""
    GameDocumentsDirectory = "%GAME_PATH%"
    GameSavesDirectory = r"%GAME_PATH%\SNAppData\SavedGames"

    _game_extra_save_paths = [
        r"%USERPROFILE%\Appdata\LocalLow\Unknown Worlds"
        r"\Subnautica Below Zero\SubnauticaZero\SavedGames"
    ]

    def init(self, organizer: mobase.IOrganizer) -> bool:
        super().init(organizer)
        checker = game_subnautica.SubnauticaModDataChecker()
        checker.update_patterns({"unfold": ["BepInExPack_BelowZero"]})
        self._featureMap[mobase.ModDataChecker] = checker
        return True
