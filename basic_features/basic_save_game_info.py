# -*- encoding: utf-8 -*-

import sys
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import QDateTime, QLocale, Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QFormLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

import mobase


def format_date(date_time: QDateTime | datetime | str, format_str=""):
    """Default format for date and time in the `BasicGameSaveGameInfoWidget`.

    Args:
        date_time: either a `QDateTime`/`datetime` or a string together with
            a `format_str`.
        format_str (optional): date/time format string (see `QDateTime.fromString`).

    Returns:
        Date and time in short locale format.
    """
    if isinstance(date_time, str):
        date_time = QDateTime.fromString(date_time, format_str)
    return QLocale.system().toString(date_time, QLocale.FormatType.ShortFormat)


class BasicGameSaveGame(mobase.ISaveGame):
    def __init__(self, filepath: Path):
        super().__init__()
        self._filepath = filepath

    def getFilepath(self) -> str:
        return self._filepath.as_posix()

    def getName(self) -> str:
        return self._filepath.name

    def getCreationTime(self):
        return QDateTime.fromSecsSinceEpoch(int(self._filepath.stat().st_mtime))

    def getSaveGroupIdentifier(self) -> str:
        return ""

    def allFiles(self) -> list[str]:
        return [self.getFilepath()]


class BasicGameSaveGameInfoWidget(mobase.ISaveGameInfoWidget):
    _preview_width = 320

    def __init__(
        self,
        parent: QWidget,
        get_preview: Callable[
            [Path], Path | str | QPixmap | QImage | None
        ] = lambda p: None,
        get_metadata: Callable[
            [Path, mobase.ISaveGame], Mapping[str, str] | None
        ] = lambda p, s: None,
    ):
        """
        Args:
            parent: parent widget
            get_preview (optional): `callback(savegame_path)` returning the path
                to the saves preview image.
            get_metadata (optional): `callback(savegame_path, ISaveGame)` returning
                the saves metadata. By default the saves file date is shown.
        """
        super().__init__(parent)

        self._get_preview = get_preview
        self._get_metadata = get_metadata

        layout = QVBoxLayout()

        # Metadata form
        self._metadata_widget = QWidget()
        self._metadata_widget.setMaximumWidth(self._preview_width)
        self._metadata_layout = form_layout = QFormLayout(self._metadata_widget)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setVerticalSpacing(2)
        layout.addWidget(self._metadata_widget)
        self._metadata_widget.hide()  # Backwards compatibility (no metadata)

        # Preview (pixmap)
        self._label = QLabel()
        layout.addWidget(self._label)
        self.setLayout(layout)

        self.setWindowFlags(
            Qt.WindowType.ToolTip | Qt.WindowType.BypassGraphicsProxyWidget
        )

    def setSave(self, save: mobase.ISaveGame):
        save_path = Path(save.getFilepath())

        # Clear previous
        self.hide()
        self._label.clear()
        while self._metadata_layout.count():
            if w := self._metadata_layout.takeAt(0).widget():
                w.deleteLater()

        # Retrieve the pixmap and metadata:
        preview = self._get_preview(save_path)
        pixmap = None

        # Set the preview pixmap if the preview file exits
        if preview:
            if isinstance(preview, Path):
                pixmap = QPixmap(str(preview))
            elif isinstance(preview, str):
                pixmap = QPixmap(preview)
            elif isinstance(preview, QPixmap):
                pixmap = preview
            elif isinstance(preview, QImage):
                pixmap = QPixmap.fromImage(preview)
            else:
                print(
                    "Failed to retrieve the preview, bad return type: {}.".format(
                        type(preview)
                    ),
                    file=sys.stderr,
                )
        if pixmap and not pixmap.isNull():
            # Scale the pixmap and show it:
            pixmap = pixmap.scaledToWidth(self._preview_width)
            self._label.setPixmap(pixmap)
            self._label.show()
        else:
            self._label.hide()
            pixmap = None

        # Add metadata, file date by default.
        metadata = self._get_metadata(save_path, save)
        if metadata is None:
            metadata = {"File Date:": format_date(save.getCreationTime())}
        if metadata:
            for key, value in metadata.items():
                self._metadata_layout.addRow(*self._new_form_row(key, str(value)))
            self._metadata_widget.show()
            self._metadata_widget.setLayout(self._metadata_layout)
            self._metadata_widget.adjustSize()
        else:
            self._metadata_widget.hide()

        if metadata or pixmap:
            self.adjustSize()
            self.show()

    def _new_form_row(self, label="", field=""):
        qLabel = QLabel(text=label)
        qLabel.setAlignment(Qt.AlignmentFlag.AlignTop)
        qLabel.setStyleSheet("font: italic")
        qLabel.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
        qField = QLabel(text=field)
        qField.setWordWrap(True)
        qField.setAlignment(Qt.AlignmentFlag.AlignTop)
        qField.setStyleSheet("font: bold")
        qField.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        return qLabel, qField


class BasicGameSaveGameInfo(mobase.SaveGameInfo):
    def __init__(
        self,
        get_preview: Callable[
            [Path], Path | str | QPixmap | QImage | None
        ] = lambda p: None,
        get_metadata: Callable[
            [Path, mobase.ISaveGame], Mapping[str, str] | None
        ] = lambda p, s: None,
    ):
        """Args from: `BasicGameSaveGameInfoWidget`."""
        super().__init__()
        self._get_preview = get_preview
        self._get_metadata = get_metadata

    def getMissingAssets(self, save: mobase.ISaveGame):
        return {}

    def getSaveGameWidget(self, parent=None):
        return BasicGameSaveGameInfoWidget(
            parent, self._get_preview, self._get_metadata
        )
