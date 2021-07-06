from qgis.PyQt.QtWidgets import QDialog, QListWidgetItem

from qgis.core import (
    QgsProviderRegistry,
    QgsProviderConnectionException,
    QgsVectorLayer,
    QgsProject,
    QgsDataSourceUri,
    QgsWkbTypes
)

from QGIS_FMV.gui.ui_FmvOpenDatabase import Ui_OpenDatabase


class DbListWidgetItem(QListWidgetItem):
    def __init__(self, text, connection, parent=None):
        super().__init__(text, parent=parent)

        self.connection = connection



class DatabaseDialog(QDialog, Ui_OpenDatabase):
    """ About Dialog """

    def __init__(self, iface, parent=None, Exts=None):
        """ Contructor """
        super().__init__(parent)
        self.setupUi(self)
        self.iface = iface
        self.parent = parent

        self.populate_databases()


    def populate_databases(self):
        """populate the database combo box."""
        metadata = QgsProviderRegistry.instance().providerMetadata('postgres')
        dbs = [
            DbListWidgetItem(k, v)
            for k, v in metadata.connections().items()
        ]
        for i in dbs:
            self.db_list.addItem(i)


    def load_layer(self):
        conn = self.db_list.currentItem().connection
        if conn:
            try:
                tablename = 'datei_view'
                schemaname = 'video'
                uri = QgsDataSourceUri(
                    conn.uri()
                )
                uri.setDataSource(schemaname, tablename, 'geom')
                uri.setSrid('25832')
                uri.setWkbType(QgsWkbTypes.LineString)
                uri.setKeyColumn('video_id')
                layer = QgsVectorLayer(uri.uri(False), tablename, 'postgres')
                QgsProject.instance().addMapLayer(layer)

                self.iface.showAttributeTable(layer)
                self.accept()
            except QgsProviderConnectionException as e:
                ## TODO: Error message!
                print(e)