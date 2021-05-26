# -*- encoding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING

import mobase

# Fix for mypy: missing mixin super() support.
if TYPE_CHECKING:
    IPluginGameBase = mobase.IPluginGame
else:
    IPluginGameBase = object


class IWithForcedLibraries(IPluginGameBase):
    """Mixin for `IPluginGame`: forced load of proxy libraries.

    Attributes:
        forced_libraries: the file names (.dll) of the libraries (required)
    """

    forced_libraries: list[str]

    def executableForcedLoads(self) -> list[mobase.ExecutableForcedLoadSetting]:
        try:
            efls = super().executableForcedLoads()
        except AttributeError:
            efls = []
        efls.extend(
            mobase.ExecutableForcedLoadSetting(self.binaryName(), lib).withEnabled(True)
            for lib in self.forced_libraries
        )
        return efls


class IUsesBepInEx(IWithForcedLibraries):
    """Mixin for `IPluginGame`: BepInEx requires the proxy library winhttp.dll to inject
    mods. If it is installed with Mod Organizer via the VFS, the dll needs to be force
    loaded.
    """

    forced_libraries = ["winhttp.dll"]
