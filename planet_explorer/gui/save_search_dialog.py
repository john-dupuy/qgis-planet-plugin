import os
import json
import copy

from qgis.core import Qgis

from qgis.PyQt import uic
from qgis.PyQt.QtCore import Qt, QDateTime
from qgis.PyQt.QtWidgets import (
    QVBoxLayout, 
    QDialogButtonBox, 
    QSizePolicy,
    QInputDialog
)

from qgis.gui import QgsMapCanvas, QgsMessageBar

from qgis.utils import iface

from ..pe_utils import (
    qgsgeometry_from_geojson
)

from ..planet_api.p_client import (
        PlanetClient
)

from .pe_filters import filters_from_request

WIDGET, BASE = uic.loadUiType(os.path.join(
        os.path.dirname(os.path.dirname(__file__)), 
        "ui", "save_search_dialog.ui"))

class SaveSearchDialog(BASE, WIDGET):

    def __init__(self, request, parent=None):
        super(SaveSearchDialog, self).__init__(parent)
        self.request = request
        self.request_to_save = None

        self.setupUi(self)  

        self.bar = QgsMessageBar()
        self.bar.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed )
        self.layout().addWidget(self.bar)     

        self.buttonBox.button(QDialogButtonBox.Save).clicked.connect(self.save)
        self.buttonBox.button(QDialogButtonBox.Cancel).clicked.connect(self.rejected)

        self.btnCreateFolder.clicked.connect(self.createFolder)

        self.set_from_request()

        self.populate_folders()


    def createFolder(self):
        name, _ = QInputDialog.getText(self, "Save Search", "Enter folder name")
        if name and name not in self._folder_names:
            self._folder_names.append(name)
            self.populate_folders()

    def populate_folders(self):
        self.comboFolder.clear()
        self.comboFolder.addItems(self._folders())

    _folder_names = None

    def _folders(self):
        if self._folder_names is None:
            self._folder_names = [""]
            client = PlanetClient.getInstance()
            res = client.api_client().get_searches().get()
            for search in res["searches"]:
                tokens = search["name"].split("/")
                if len(tokens) > 1 and tokens[0] not in self._folder_names:
                    self._folder_names.append(tokens[0])        

        return self._folder_names

    def set_from_request(self):
        filters = filters_from_request(self.request, "geometry")
        geom = filters[0]["config"]
        aoi_txt = json.dumps(geom)
        layout = QVBoxLayout()
        layout.setMargin(0)
        self.canvas = QgsMapCanvas()
        layers = iface.mapCanvas().mapSettings().layers()
        crs = iface.mapCanvas().mapSettings().destinationCrs()
        self.canvas.setLayers(layers)
        extent = qgsgeometry_from_geojson(aoi_txt).boundingBox()
        self.canvas.setDestinationCrs(crs)
        self.canvas.setExtent(extent)
        layout.addWidget(self.canvas)
        self.widgetAOI.setLayout(layout)

        filters = filters_from_request(self.request, 'acquired')
        if filters:
            gte = filters[0]['config'].get('gte')
            if gte is not None:
                self.lblStartDate.setText(QDateTime.fromString(gte, Qt.ISODate).date().toString())
            else:
                self.lblStartDate.setText("---")
                self.chkExcludeStart.setEnabled(False)
            lte = filters[0]['config'].get('lte')
            if lte is not None:
                self.lblEndDate.setText(QDateTime.fromString(lte, Qt.ISODate).date().toString())
            else:
                self.lblEndDate.setText("---")
                self.chkExcludeEnd.setEnabled(False)

    def save(self):
        name = self.txtName.text()
        if len(name) == 0:
            self.bar.pushMessage("", "Invalid name", Qgis.Warning)
            return

        folder = self.comboFolder.currentText()
        if folder:
            name = f"{folder}/{name}"

        filters = filters_from_request(self.request, 'acquired')        
        if filters:
            config = filters[0]['config']
            if self.chkExcludeStart.isChecked():
                del config['gte']
            if self.chkExcludeEnd.isChecked():
                del donfig['lte']
            self.request_to_save = copy.deepcopy(self.request)
            self.replace_date_filter(self.request_to_save, config)            
            self.request_to_save["name"] = name
        self.accept()

    def replace_date_filter(self, request, newfilter):
        def process_filter(filterdict):
            if filterdict["type"] in ["AndFilter", "OrFilter"]:
                for subfilter in filterdict["config"]:
                    process_filter(subfilter)
            elif (filterdict["field_name"] == "acquired"):
                    filterdict["config"] == newfilter

        process_filter(request["filter"])

        

    