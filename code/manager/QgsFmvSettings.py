from qgis.PyQt.QtWidgets import QDialog
from qgis.core import QgsSettings, QgsProviderRegistry

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
        self.populate_db()


    def populate_dir(self):
        dir = self.settings.value('QGIS_FMV/Settings/video_dir')
        if dir:
            self.video_dir_widget.setFilePath(dir)


    def populate_db(self):
        self.db_combobox.clear()

        metadata = QgsProviderRegistry.instance().providerMetadata('postgres')
        dbs = [
            k
            for k in metadata.connections().keys()
        ]
        self.db_combobox.addItems(dbs)

        current_db = self.settings.value('QGIS_FMV/Settings/db')
        if current_db and current_db in dbs:
            self.db_combobox.setCurrentText(current_db)


    def on_dir_change(self, dir):
        self.settings.setValue(
            'QGIS_FMV/Settings/video_dir',
            dir
        )


    def save_db(self):
        db = self.db_combobox.currentText()
        metadata = QgsProviderRegistry.instance().providerMetadata('postgres')
        if db in metadata.connections().keys():
            conn = metadata.connections()[db]
            if conn.tableExists('video','datei_view'):
                self.settings.setValue(
                    'QGIS_FMV/Settings/db',
                    db
                )
                self.iface.messageBar().pushSuccess(
                    'Connection successful!',
                    'successfully connected to {}'.format(db))
                self.parent.conn = conn
            else:
                self.iface.messageBar().pushWarning(
                    'Not a valid database!',
                    'table datei_view not found on the database!')
        else:
            self.iface.messageBar().pushWarning(
                'Not a valid database!',
                'connection {} not found'.format(db))