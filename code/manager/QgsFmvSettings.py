from qgis.PyQt.QtWidgets import QDialog
from qgis.core import QgsSettings

from QGIS_FMV.gui.ui_FmvSettings import Ui_Settings



class SettingsDialog(QDialog, Ui_Settings):
    """ About Dialog """

    def __init__(self, iface, parent=None, Exts=None):
        """ Contructor """
        super().__init__(parent)
        self.setupUi(self)
        self.iface = iface
        self.parent = parent
        self.settings = QgsSettings()

        self.populate_dir()


    def populate_dir(self):
        dir = self.settings.value('QGIS_FMV/Settings/video_dir')
        if dir:
            self.video_dir_widget.setFilePath(dir)


    def on_dir_change(self, dir):
        self.settings.setValue(
            'QGIS_FMV/Settings/video_dir',
            dir
        )