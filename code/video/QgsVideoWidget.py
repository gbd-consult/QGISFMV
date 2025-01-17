from qgis.PyQt.QtCore import Qt, QRect, QPoint, QEvent, QBasicTimer, QSize
from qgis.PyQt.QtGui import (
    QPalette,
    QPainter,
    QPen,
    QColor,
    QBrush,
    QCursor,
    QMouseEvent,
)
from qgis.PyQt.QtWidgets import QRubberBand
from qgis.core import (
    QgsProject,
    QgsPointXY,
    QgsWkbTypes,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
)
from qgis.gui import QgsRubberBand
from qgis.utils import iface

from PyQt5.QtMultimedia import (
    QMediaPlayer,
)
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtWidgets import QApplication

from QGIS_FMV.geo import QgsMgrs
from QGIS_FMV.player.QgsFmvDrawToolBar import DrawToolBar as draw
from QGIS_FMV.utils.QgsFmvLayers import (
    AddDrawPointOnMap,
    AddDrawLineOnMap,
    AddDrawPolygonOnMap,
    RemoveLastDrawPolygonOnMap,
    RemoveAllDrawPolygonOnMap,
    RemoveLastDrawPointOnMap,
    RemoveAllDrawPointOnMap,
    RemoveAllDrawLineOnMap,
)
from QGIS_FMV.utils.QgsFmvUtils import (
    SetImageSize,
    convertQImageToMat,
    GetGCPGeoTransform,
    GetImageHeight,
)
from QGIS_FMV.video.QgsVideoFilters import VideoFilters as filter
from QGIS_FMV.video.QgsVideoUtils import VideoUtils as vut
from QGIS_FMV.video.QgsVideoState import InteractionState, FilterState
from QGIS_FMV.video.QgsVideoWidgetSurface import VideoWidgetSurface

try:
    from pydevd import *
except ImportError:
    None

try:
    from cv2 import TrackerMOSSE_create, resize
except ImportError:
    None

"""
Video Widget
"""


class VideoWidget(QVideoWidget):
    def __init__(self, parent=None):
        """ Constructor """
        super().__init__(parent)
        self.surface = VideoWidgetSurface(self)
        self.setAttribute(Qt.WA_OpaquePaintEvent)

        self.Tracking_Video_RubberBand = QRubberBand(QRubberBand.Rectangle, self)
        self.Censure_RubberBand = QRubberBand(QRubberBand.Rectangle, self)

        color_blue = QColor(Qt.blue)
        color_black = QColor(Qt.black)
        color_amber = QColor(252, 215, 108)

        pal_blue = QPalette()
        pal_blue.setBrush(QPalette.Highlight, QBrush(color_blue))
        self.Tracking_Video_RubberBand.setPalette(pal_blue)

        pal_black = QPalette()
        pal_black.setBrush(QPalette.Highlight, QBrush(color_black))
        self.Censure_RubberBand.setPalette(pal_black)

        self._interaction = InteractionState()
        self._filterSatate = FilterState()

        self._isinit = False
        self._MGRS = False

        self.drawCesure = []
        (
            self.poly_coordinates,
            self.drawPtPos,
            self.drawLines,
            self.drawMeasureDistance,
            self.drawMeasureArea,
            self.drawPolygon,
        ) = ([], [], [], [], [], [])
        # Draw Polygon Canvas Rubberband
        self.poly_Canvas_RubberBand = QgsRubberBand(
            iface.mapCanvas(), True
        )  # Polygon type
        # set rubber band style
        self.poly_Canvas_RubberBand.setColor(color_amber)
        self.poly_Canvas_RubberBand.setWidth(3)

        # Tracking Canvas Rubberband
        self.Track_Canvas_RubberBand = QgsRubberBand(
            iface.mapCanvas(), QgsWkbTypes.LineGeometry
        )
        # set rubber band style
        self.Track_Canvas_RubberBand.setColor(color_blue)
        self.Track_Canvas_RubberBand.setWidth(5)

        # Cursor Canvas Rubberband
        self.Cursor_Canvas_RubberBand = QgsRubberBand(
            iface.mapCanvas(), QgsWkbTypes.PointGeometry
        )
        self.Cursor_Canvas_RubberBand.setWidth(4)
        self.Cursor_Canvas_RubberBand.setColor(QColor(255, 100, 100, 250))
        self.Cursor_Canvas_RubberBand.setIcon(QgsRubberBand.ICON_FULL_DIAMOND)

        self.parent = parent.parent()

        palette = self.palette()
        palette.setColor(QPalette.Background, Qt.transparent)
        self.setPalette(palette)

        self.origin, self.dragPos = QPoint(), QPoint()
        self.tapTimer = QBasicTimer()
        self.brush = QBrush(color_black)
        self.blue_Pen = QPen(color_blue, 3)

        self.lastMouseX = -1
        self.lastMouseY = -1

    def removeLastLine(self):
        """ Remove Last Line Objects """
        if self.drawLines:
            try:
                if self.drawLines[-1][3] == "mouseMoveEvent":
                    del self.drawLines[-1]  # Remove mouseMoveEvent element
            except Exception:
                None
            for pt in range(len(self.drawLines) - 1, -1, -1):
                del self.drawLines[pt]
                try:
                    if self.drawLines[pt - 1][0] is None:
                        break
                except Exception:
                    None
            self.UpdateSurface()
            AddDrawLineOnMap(self.drawLines)
        return

    def removeLastSegmentLine(self):
        """ Remove Last Segment Line Objects """
        try:
            if self.drawLines[-1][3] == "mouseMoveEvent":
                del self.drawLines[-1]  # Remove mouseMoveEvent element
        except Exception:
            None
        if self.drawLines:
            if self.drawLines[-1][0] is None:
                del self.drawLines[-1]

            del self.drawLines[-1]
            self.UpdateSurface()
            AddDrawLineOnMap(self.drawLines)
        return

    def removeAllLines(self):
        """ Resets Line List """
        if self.drawLines:
            self.drawLines = []
            self.UpdateSurface()
            # Clear all Layer
            RemoveAllDrawLineOnMap()

    def ResetDrawMeasureDistance(self):
        """ Resets Measure Distance List """
        self.drawMeasureDistance = []

    def ResetDrawMeasureArea(self):
        """ Resets Measure Area List """
        self.drawMeasureArea = []

    def removeAllCensure(self):
        """ Remove All Censure Objects """
        if self.drawCesure:
            self.drawCesure = []
            self.UpdateSurface()

    def removeLastCensured(self):
        """ Remove Last Censure Objects """
        if self.drawCesure:
            del self.drawCesure[-1]
            self.UpdateSurface()

    def removeLastPoint(self):
        """ Remove All Point Drawer Objects """
        if self.drawPtPos:
            del self.drawPtPos[-1]
            self.UpdateSurface()
            RemoveLastDrawPointOnMap()
        return

    def removeAllPoint(self):
        """ Remove All Point Drawer Objects """
        if self.drawPtPos:
            self.drawPtPos = []
            self.UpdateSurface()
            # Clear all Layer
            RemoveAllDrawPointOnMap()
        return

    def removeAllPolygon(self):
        """ Remove All Polygon Drawer Objects """
        if self.drawPolygon:
            self.drawPolygon = []
            self.UpdateSurface()
            # Clear all Layer
            RemoveAllDrawPolygonOnMap()

    def removeLastPolygon(self):
        """ Remove Last Polygon Drawer Objects """
        if self.drawPolygon:
            try:
                if self.drawPolygon[-1][3] == "mouseMoveEvent":
                    del self.drawPolygon[-1]  # Remove mouseMoveEvent element
            except Exception:
                None
            for pt in range(len(self.drawPolygon) - 1, -1, -1):
                del self.drawPolygon[pt]
                try:
                    if self.drawPolygon[pt - 1][0] is None:
                        break
                except Exception:
                    None

            self.UpdateSurface()
            # remove last index layer
            RemoveLastDrawPolygonOnMap()

    def keyPressEvent(self, event):
        """Exit fullscreen
        :type event: QKeyEvent
        :param event:
        :return:
        """
        if event.key() == Qt.Key_Escape and self.isFullScreen():
            self.setFullScreen(False)
            event.accept()
        elif event.key() == Qt.Key_Enter and event.modifiers() & Qt.Key_Alt:
            self.setFullScreen(not self.isFullScreen())
            event.accept()
        else:
            super().keyPressEvent(event)

    def mouseDoubleClickEvent(self, event):
        """
         Mouse double click event
        :type event: QMouseEvent
        :param event:
        :return:
        """
        if GetImageHeight() == 0:
            return

        if not vut.IsPointOnScreen(event.x(), event.y(), self.surface):
            return

        if GetGCPGeoTransform() is not None and self._interaction.lineDrawer:
            self.drawLines.append([None, None, None])
            return

        if GetGCPGeoTransform() is not None and self._interaction.measureDistance:
            self.drawMeasureDistance.append([None, None, None])
            self.parent.actionMeasureDistance.toggle()
            return

        if GetGCPGeoTransform() is not None and self._interaction.measureArea:
            self.drawMeasureArea.append([None, None, None])
            self.parent.actionMeasureArea.toggle()
            return

        if GetGCPGeoTransform() is not None and self._interaction.polygonDrawer:

            ok = AddDrawPolygonOnMap(self.poly_coordinates)
            # Prevent invalid geometry (Polygon with 2 points)
            if not ok:
                return

            self.drawPolygon.append([None, None, None])

            # Empty RubberBand
            for _ in range(self.poly_Canvas_RubberBand.numberOfVertices()):
                self.poly_Canvas_RubberBand.removeLastPoint()
            # Empty List
            self.poly_coordinates = []
            return

        self.UpdateSurface()
        scr = QApplication.desktop().screenNumber(self)
        self.setGeometry(QApplication.desktop().screenGeometry(scr))
        self.setFullScreen(not self.isFullScreen())
        event.accept()

    def videoSurface(self):
        """ Return video Surface """
        return self.surface

    def UpdateSurface(self):
        """ Update Video Surface only is is stopped or paused """
        if self.parent.playerState in (
            QMediaPlayer.StoppedState,
            QMediaPlayer.PausedState,
        ):
            self.update()
        QApplication.processEvents()

    def sizeHint(self):
        """ This property holds the recommended size for the widget """
        return self.surface.surfaceFormat().sizeHint()

    def currentFrame(self):
        """ Return current frame QImage """
        return self.surface.image

    def SetInvertColor(self, value):
        """Set Invert color filter
        @type value: bool
        @param value:
        @return:
        """
        self._filterSatate.invertColorFilter = value

    def SetObjectTracking(self, value):
        """Set Object Tracking
        @type value: bool
        @param value:
        @return:
        """
        self._interaction.objectTracking = value

    def SetMeasureDistance(self, value):
        """Set measure Distance
        @type value: bool
        @param value:
        @return:
        """
        self._interaction.measureDistance = value

    def SetMeasureArea(self, value):
        """Set measure Area
        @type value: bool
        @param value:
        @return:
        """
        self._interaction.measureArea = value

    def SetHandDraw(self, value):
        """Set Hand Draw
        @type value: bool
        @param value:
        @return:
        """
        self._interaction.HandDraw = value

    def SetCensure(self, value):
        """Set Censure Video Parts
        @type value: bool
        @param value:
        @return:
        """
        self._interaction.censure = value

    def SetMGRS(self, value):
        """Set MGRS Cursor Coordinates
        @type value: bool
        @param value:
        @return:
        """
        self._MGRS = value

    def SetGray(self, value):
        """Set gray scale
        @type value: bool
        @param value:
        @return:
        """
        self._filterSatate.grayColorFilter = value

    def SetMirrorH(self, value):
        """Set Horizontal Mirror
        @type value: bool
        @param value:
        @return:
        """
        self._filterSatate.MirroredHFilter = value

    def SetNDVI(self, value):
        """Set NDVI
        @type value: bool
        @param value:
        @return:
        """
        self._filterSatate.NDVI = value

    def SetEdgeDetection(self, value):
        """Set Canny Edge filter
        @type value: bool
        @param value:
        @return:
        """
        self._filterSatate.edgeDetectionFilter = value

    def SetAutoContrastFilter(self, value):
        """Set Automatic Contrast filter
        @type value: bool
        @param value:
        @return:
        """
        self._filterSatate.contrastFilter = value

    def SetMonoFilter(self, value):
        """Set mono filter
        @type value: bool
        @param value:
        @return:
        """
        self._filterSatate.monoFilter = value

    def RestoreFilters(self):
        """ Remove and restore all video filters """
        self._filterSatate.clear()

    def RestoreDrawer(self):
        """ Remove and restore all Drawer Options """
        self._interaction.clear()
        # Magnifier Glass
        self.dragPos = QPoint()
        self.tapTimer.stop()

    def RemoveCanvasRubberbands(self):
        """ Remove Canvas Rubberbands """
        self.poly_Canvas_RubberBand.reset()
        self.Track_Canvas_RubberBand.reset(QgsWkbTypes.LineGeometry)
        self.Cursor_Canvas_RubberBand.reset(QgsWkbTypes.PointGeometry)

    def RemoveVideoDrawings(self):
        """ Remove Video Drawings """
        (
            self.poly_coordinates,
            self.drawPtPos,
            self.drawLines,
            self.drawMeasureDistance,
            self.drawMeasureArea,
            self.drawPolygon,
        ) = ([], [], [], [], [], [])

    def paintEvent(self, event):
        """
        @type event: QPaintEvent
        @param event:
        @return:
        """

        if not self.surface.isActive():
            return

        self.painter = QPainter(self)
        self.painter.setRenderHint(QPainter.HighQualityAntialiasing)

        region = event.region()
        self.painter.fillRect(
            region.boundingRect(), self.brush
        )  # Background painter color

        try:
            self.surface.paint(self.painter)
            SetImageSize(self.currentFrame().width(), self.currentFrame().height())
        except Exception:
            None

        # Prevent draw on video if not started or finished
        # if self.parent.player.position() == 0:
        #    self.painter.end()
        #    return

        # Draw On Video
        draw.drawOnVideo(
            self.drawPtPos,
            self.drawLines,
            self.drawPolygon,
            self.drawMeasureDistance,
            self.drawMeasureArea,
            self.drawCesure,
            self.painter,
            self.surface,
            GetGCPGeoTransform(),
        )

        # Draw On Video Object tracking Object
        if self._interaction.objectTracking and self._isinit:
            frame = convertQImageToMat(self.currentFrame())
            offset = self.surface.videoRect()
            # Update tracker
            result = resize(frame, (offset.width(), offset.height()))
            ok, bbox = self.tracker.update(result)
            # Draw bounding box
            if ok:
                # check negative values
                x = bbox[0] + offset.x()
                y = bbox[1] + offset.y()
                if vut.IsPointOnScreen(x, y, self.surface):
                    self.painter.setPen(self.blue_Pen)
                    self.painter.setBrush(Qt.transparent)
                    self.painter.drawRect(x, y, bbox[2], bbox[3])

                    # Get Track object center
                    xc = x + (bbox[2] / 2)
                    yc = y + (bbox[3] / 2)
                    p = QPoint(xc, yc)
                    Longitude, Latitude, _ = vut.GetPointCommonCoords(p, self.surface)
                    # Draw Rubber Band on canvas
                    self.Track_Canvas_RubberBand.addPoint(
                        QgsPointXY(Longitude, Latitude)
                    )

            else:
                self._isinit = False
                del self.tracker

        # Magnifier Glass
        if self._interaction.magnifier and not self.dragPos.isNull():
            draw.drawMagnifierOnVideo(
                self, self.dragPos, self.currentFrame(), self.painter
            )

        # Stamp On Video
        if self._interaction.stamp:
            draw.drawStampOnVideo(self, self.painter)

        self.painter.end()
        return

    def resizeEvent(self, _):
        """
        @type _: QMouseEvent
        @param _:
        @return:
        """
        self.surface.updateVideoRect()
        self.update()
        # Magnifier Glass
        if self._interaction.magnifier and not self.dragPos.isNull():
            draw.drawMagnifierOnVideo(
                self, self.dragPos, self.currentFrame(), self.painter
            )
        # QApplication.processEvents()

    def AddMoveEventValue(self, values, Longitude, Latitude, Altitude):
        """
        Remove and Add move value for fluid drawing

        @type values: list
        @param values: Points list

        @type Longitude: float
        @param Longitude: Longitude value

        @type Latitude: float
        @param Latitude: Latitude value

        @type Altitude: float
        @param Altitude: Altitude value

        """
        for idx, pt in enumerate(values):
            if pt[-1] == "mouseMoveEvent":
                del values[idx]
        values.append([Longitude, Latitude, Altitude, "mouseMoveEvent"])

        self.UpdateSurface()

    def timerEvent(self, _):
        """ Time Event (Magnifier method)"""
        if not self._interaction.magnifier:
            self.activateMagnifier()

    def activateMagnifier(self):
        """ Activate Magnifier Glass """
        self.tapTimer.stop()
        self.UpdateSurface()

    def SetMagnifier(self, value):
        """Set Magnifier Glass
        @type value: bool
        @param value:
        """
        self._interaction.magnifier = value
        # We avoid that the second time we activate the tool, save the previous position.
        # Always keep the same behavior of the tool
        if not value:
            self.dragPos = QPoint()
            self.tapTimer.stop()

    def SetStamp(self, value):
        """Set Stamp
        @type value: bool
        @param value:
        """
        self._interaction.stamp = value

    def SetPointDrawer(self, value):
        """Set Point Drawer
        @type value: bool
        @param value:
        """
        self._interaction.pointDrawer = value

    def SetLineDrawer(self, value):
        """Set Line Drawer
        @type value: bool
        @param value:
        """
        self._interaction.lineDrawer = value

    def SetPolygonDrawer(self, value):
        """Set Polygon Drawer
        @type value: bool
        @param value:
        """
        self._interaction.polygonDrawer = value

    def mouseReleaseEvent(self, _):
        """
        @type event: QMouseEvent
        @param event:
        @return:
        """
        # Prevent draw on video if not started or finished
        # if self.parent.player.position() == 0:
        #    return

        # Censure Draw Interaction
        if self._interaction.censure:
            geom = self.Censure_RubberBand.geometry()
            self.Censure_RubberBand.hide()
            self.drawCesure.append([geom])

        # Object Tracking Interaction
        if self._interaction.objectTracking:
            geom = self.Tracking_Video_RubberBand.geometry()
            offset = self.surface.videoRect()
            bbox = (
                geom.x() - offset.x(),
                geom.y() - offset.y(),
                geom.width(),
                geom.height(),
            )
            img = self.currentFrame()
            frame = convertQImageToMat(img)
            # Remo rubberband on canvas and video
            self.Tracking_Video_RubberBand.hide()
            self.Track_Canvas_RubberBand.reset()

            self.tracker = TrackerMOSSE_create()
            result = resize(frame, (offset.width(), offset.height()))

            try:
                ok = self.tracker.init(result, bbox)
            except Exception:
                return
            if ok:
                self._isinit = True
                # Get Traker center
                xc = bbox[0] + (geom.width() / 2)
                yc = bbox[1] + (geom.height() / 2)
                p = QPoint(xc, yc)
                Longitude, Latitude, _ = vut.GetPointCommonCoords(p, self.surface)
                # Draw Rubber Band on canvas
                self.Track_Canvas_RubberBand.addPoint(QgsPointXY(Longitude, Latitude))
            else:
                self._isinit = False

    def leaveEvent(self, _):
        """
        @type _: QEvent
        @param _:
        @return:
        """
        # Remove coordinates label value
        self.parent.lb_cursor_coord.setText("")
        # Change cursor
        self.setCursor(QCursor(Qt.ArrowCursor))
        # Reset mouse rubberband
        self.Cursor_Canvas_RubberBand.reset(QgsWkbTypes.PointGeometry)
