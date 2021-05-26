# -*- encoding: utf-8 -*-

from __future__ import annotations

import mobase

from ..basic_features import ModDataAndRequirementChecker, ModRequirementMapping
from ..basic_game import BasicGame
from ..forced_libraries import IUsesBepInEx

framework_description = ModRequirementMapping.framework_description


class ValheimGame(IUsesBepInEx, BasicGame):

    Name = "Valheim Support Plugin"
    Author = "Zash"
    Version = "1.0.0"

    GameName = "Valheim"
    GameShortName = "valheim"
    GameNexusId = 3667
    GameSteamId = [892970, 896660, 1223920]
    GameBinary = "valheim.exe"
    GameDataPath = ""

    def init(self, organizer: mobase.IOrganizer) -> bool:
        super().init(organizer)
        self._featureMap[mobase.ModDataChecker] = ModDataAndRequirementChecker(
            ignore_patterns=[
                "*.txt",
                "*.md",
                "icon.png",
                "license",
                "manifest.json",
            ],
            mappings={"*.assets": "valheim_Data/"},
            requirements=[
                # Higher priority with *_VML.dll before *.dll
                ModRequirementMapping(
                    "InSlimVML",
                    nexus_id=21,
                    required_by=["InSlimVML/Mods/*_VML.dll"],
                    installs=[
                        "InSlimVML/Mods/0Harmony.dll",
                        "valheim_Data/",
                        "inslimvml.ini",
                        "winhttp.dll",
                    ],
                    custom_mapping={"unstripped_managed/": ""},  # optional
                    problem_description=framework_description,
                ),
                ModRequirementMapping(
                    "BepInEx",
                    url="https://valheim.thunderstore.io/package/denikson/BepInExPack_Valheim/",  # noqa E501
                    required_by=["BepInEx/plugins/*.dll", "BepInEx/config/*.cfg"],
                    installs=[
                        "BepInEx/",
                        "doorstop_libs/",
                        "unstripped_corlib/",
                        "doorstop_config.ini",
                        "start_game_bepinex.sh",
                        "start_server_bepinex.sh",
                        "winhttp.dll",
                    ],
                    problem_description=framework_description,
                ),
                ModRequirementMapping(
                    "CustomTextures",
                    nexus_id=21,
                    required_by=[
                        # Includes directories, gets expanded to CustomTextures/*
                        "BepInEx/plugins/CustomTextures/*",
                        # gets expanded up to *.png
                        "BepInEx/plugins/CustomTextures/*.png",
                    ],
                    installs=["BepInEx/plugins/CustomTextures.dll"],
                ),
                ModRequirementMapping(
                    "AdvancedBuilder",
                    nexus_id=5,
                    required_by=["AdvancedBuilder/Builds/*.vbuild"],
                    installs=["InSlimVML/Mods/CR-BuildShare_VML.dll"],
                ),
            ],
        )
        return True
