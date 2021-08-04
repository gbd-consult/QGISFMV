import os
from qgis.PyQt.QtGui import QColor, QFont, QPolygonF
from qgis.PyQt.QtWidgets import QApplication
from qgis.PyQt.QtCore import QCoreApplication, QPointF

from QGIS_FMV.utils.QgsUtils import QgsUtils as qgsu
from qgis.PyQt.QtCore import QVariant, QSettings
from qgis.core import (
    QgsPalLayerSettings,
    QgsTextFormat,
    QgsLayerTreeGroup,
    QgsTextBufferSettings,
    QgsVectorLayerSimpleLabeling,
    QgsMarkerSymbol,
    QgsLayerTreeLayer,
    QgsField,
    QgsFields,
    QgsVectorLayer,
    QgsVectorFileWriter,
    QgsFillSymbol,
    QgsLineSymbol,
    QgsSvgMarkerSymbolLayer,
    QgsSingleSymbolRenderer,
    QgsDistanceArea,
    QgsCoordinateReferenceSystem,
    QgsProject,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsPoint,
    QgsLineString,
)

from qgis.utils import iface
from QGIS_FMV.utils.QgsFmvStyles import FmvLayerStyles as S
from itertools import groupby
from qgis._3d import (
    QgsPhongMaterialSettings,
    QgsVectorLayer3DRenderer,
    QgsLine3DSymbol,
    QgsPoint3DSymbol,
    QgsPolygon3DSymbol,
)

try:
    from pydevd import *
except ImportError:
    None

from QGIS_FMV.QgsFmvConstants import (
    Platform_lyr,
    Beams_lyr,
    Footprint_lyr,
    FrameCenter_lyr,
    FrameAxis_lyr,
    Point_lyr,
    Line_lyr,
    Polygon_lyr,
    frames_g,
    Trajectory_lyr,
    epsg,
)
from QGIS_FMV.QgsFmvConstants import encoding

groupName = None


_layerreg = QgsProject.instance()
crtSensorSrc = crtSensorSrc2 = crtPltTailNum = "DEFAULT"

TYPE_MAP = {
    str: QVariant.String,
    float: QVariant.Double,
    int: QVariant.Int,
    bool: QVariant.Bool,
}

Point = "Point"
PointZ = "PointZ"
LineZ = "LineStringZ"
Line = "LineString"
Polygon = "Polygon"


# def getLayerExtent(layer=None):
#     """ Get Layer extent """
#     return (
#         iface.mapCanvas().mapSettings().layerExtentToOutputExtent(layer, layer.extent())
#     )


def selectLayerByName(layerName, group=None):
    """ Select Layer by Name """
    returnLayer = None
    try:
        if group is None:
            returnLayer = QgsProject.instance().mapLayersByName(layerName)[0]
            return returnLayer
        else:
            root = QgsProject.instance().layerTreeRoot()
            returnLayer = QgsProject.instance().mapLayersByName(layerName)
            g = root.findGroup(group)
            if g is not None:
                for child in returnLayer:
                    layer = g.findLayer(child.id())
                    if layer is not None:
                        returnLayer = child
                        return returnLayer
    except IndexError:
        return returnLayer


def AddDrawPointOnMap(pointIndex, Longitude, Latitude, Altitude):
    """  add pin point on the map """
    pointLyr = selectLayerByName(Point_lyr, groupName)
    if pointLyr is None:
        return
    pointLyr.startEditing()
    feature = QgsFeature()
    feature.setAttributes([pointIndex, Longitude, Latitude, Altitude])

    p = QgsPointXY()
    p.set(Longitude, Latitude)
    feature.setGeometry(QgsGeometry.fromPointXY(p))
    pointLyr.addFeatures([feature])
    CommonLayer(pointLyr)
    return


def AddDrawLineOnMap(drawLines):
    """  add Line on the map """

    RemoveAllDrawLineOnMap()
    linelyr = selectLayerByName(Line_lyr, groupName)
    if linelyr is None:
        return

    linelyr.startEditing()
    for k, v in groupby(drawLines, key=lambda x: x == [None, None, None]):
        points = []
        if k is False:
            list1 = list(v)
            for i in range(0, len(list1)):
                pt = QgsPointXY(list1[i][0], list1[i][1])
                points.append(pt)
            polyline = QgsGeometry.fromPolylineXY(points)
            f = QgsFeature()
            f.setGeometry(polyline)
            linelyr.addFeatures([f])

    CommonLayer(linelyr)
    return


def RemoveAllDrawLineOnMap():
    """ Remove all features on Line Layer """
    lineLyr = selectLayerByName(Line_lyr, groupName)
    if lineLyr is None:
        return
    lineLyr.startEditing()
    lineLyr.dataProvider().truncate()
    CommonLayer(lineLyr)
    return


def RemoveLastDrawPolygonOnMap():
    """  Remove Last Feature on Polygon Layer """
    polyLyr = selectLayerByName(Polygon_lyr, groupName)
    if polyLyr is None:
        return
    polyLyr.startEditing()
    listOfIds = [feat.id() for feat in polyLyr.getFeatures()]
    if listOfIds:
        polyLyr.deleteFeature(listOfIds[-1])
        CommonLayer(polyLyr)
    return


def RemoveLastDrawPointOnMap():
    """ Remove Last features on Point Layer """
    pointLyr = selectLayerByName(Point_lyr, groupName)
    if pointLyr is None:
        return
    pointLyr.startEditing()
    listOfIds = [feat.id() for feat in pointLyr.getFeatures()]
    if listOfIds:
        pointLyr.deleteFeature(listOfIds[-1])
        CommonLayer(pointLyr)
    return


def RemoveAllDrawPointOnMap():
    """ Remove all features on Point Layer """
    pointLyr = selectLayerByName(Point_lyr, groupName)
    if pointLyr is None:
        return
    pointLyr.startEditing()
    pointLyr.dataProvider().truncate()
    CommonLayer(pointLyr)
    return


def RemoveAllDrawPolygonOnMap():
    """ Remove all features on Polygon Layer """
    polyLyr = selectLayerByName(Polygon_lyr, groupName)
    if polyLyr is None:
        return
    polyLyr.startEditing()
    polyLyr.dataProvider().truncate()
    CommonLayer(polyLyr)
    return


def AddDrawPolygonOnMap(poly_coordinates):
    """ Add Polygon Layer """
    polyLyr = selectLayerByName(Polygon_lyr, groupName)
    if polyLyr is None:
        return
    polyLyr.startEditing()
    feature = QgsFeature()
    point = QPointF()
    # create  float polygon --> construcet out of 'point'

    list_polygon = QPolygonF()
    for x in range(0, len(poly_coordinates)):
        if x % 2 == 0:
            point.setX(poly_coordinates[x])
            point.setY(poly_coordinates[x + 1])
            list_polygon.append(point)
    point.setX(poly_coordinates[0])
    point.setY(poly_coordinates[1])
    list_polygon.append(point)

    geomP = QgsGeometry.fromQPolygonF(list_polygon)
    feature.setGeometry(geomP)

    # Calculate Area WSG84 (Meters)
    area_wsg84 = QgsDistanceArea()
    area_wsg84.setSourceCrs(
        QgsCoordinateReferenceSystem.fromOgcWmsCrs("EPSG:4326"),
        _layerreg.transformContext(),
    )
    if area_wsg84.sourceCrs().isGeographic():
        area_wsg84.setEllipsoid(area_wsg84.sourceCrs().ellipsoidAcronym())

    # Calculate Centroid
    try:
        centroid = feature.geometry().centroid().asPoint()
    except Exception:
        iface.vectorLayerTools().stopEditing(polyLyr, False)
        return False

    feature.setAttributes(
        [
            centroid.x(),
            centroid.y(),
            0.0,
            area_wsg84.measurePolygon(geomP.asPolygon()[0]),
        ]
    )

    polyLyr.addFeatures([feature])

    CommonLayer(polyLyr)
    return True


def SetcrtSensorSrc():
    """ Set Style based on Sensor type """
    global crtSensorSrc, crtSensorSrc2
    crtSensorSrc = crtSensorSrc2 = "DEFAULT"


def SetcrtPltTailNum():
    """ Set Style based on Platform Type Number """
    global crtPltTailNum
    crtPltTailNum = "DEFAULT"


def UpdateFootPrintData(
    packet, cornerPointUL, cornerPointUR, cornerPointLR, cornerPointLL, ele
):
    """ Update Footprint Values """
    global crtSensorSrc, groupName
    imgSS = packet.ImageSourceSensor

    footprintLyr = selectLayerByName(Footprint_lyr, groupName)

    try:
        if all(
            v is not None
            for v in [
                footprintLyr,
                cornerPointUL,
                cornerPointUR,
                cornerPointLR,
                cornerPointLL,
            ]
        ) and all(
            v >= 2
            for v in [
                len(cornerPointUL),
                len(cornerPointUR),
                len(cornerPointLR),
                len(cornerPointLL),
            ]
        ):
            if imgSS != crtSensorSrc:
                SetDefaultFootprintStyle(footprintLyr, imgSS)
                crtSensorSrc = imgSS

            footprintLyr.startEditing()
            if footprintLyr.featureCount() == 0:
                feature = QgsFeature()
                feature.setAttributes(
                    [
                        cornerPointUL[1],
                        cornerPointUL[0],
                        cornerPointUR[1],
                        cornerPointUR[0],
                        cornerPointLR[1],
                        cornerPointLR[0],
                        cornerPointLL[1],
                        cornerPointLL[0],
                    ]
                )
                surface = QgsGeometry.fromPolygonXY(
                    [
                        [
                            QgsPointXY(cornerPointUL[1], cornerPointUL[0]),
                            QgsPointXY(cornerPointUR[1], cornerPointUR[0]),
                            QgsPointXY(cornerPointLR[1], cornerPointLR[0]),
                            QgsPointXY(cornerPointLL[1], cornerPointLL[0]),
                            QgsPointXY(cornerPointUL[1], cornerPointUL[0]),
                        ]
                    ]
                )
                feature.setGeometry(surface)
                footprintLyr.addFeatures([feature])
            else:
                fetId = 1
                attrib = {
                    0: cornerPointUL[1],
                    1: cornerPointUL[0],
                    2: cornerPointUR[1],
                    3: cornerPointUR[0],
                    4: cornerPointLR[1],
                    5: cornerPointLR[0],
                    6: cornerPointLL[1],
                    7: cornerPointLL[0],
                }

                footprintLyr.dataProvider().changeAttributeValues({fetId: attrib})

                footprintLyr.dataProvider().changeGeometryValues(
                    {
                        fetId: QgsGeometry.fromPolygonXY(
                            [
                                [
                                    QgsPointXY(cornerPointUL[1], cornerPointUL[0]),
                                    QgsPointXY(cornerPointUR[1], cornerPointUR[0]),
                                    QgsPointXY(cornerPointLR[1], cornerPointLR[0]),
                                    QgsPointXY(cornerPointLL[1], cornerPointLL[0]),
                                    QgsPointXY(cornerPointUL[1], cornerPointUL[0]),
                                ]
                            ]
                        )
                    }
                )

            CommonLayer(footprintLyr)
            # 3D Style
            if ele:
                SetDefaultFootprint3DStyle(footprintLyr)

    except Exception as e:
        qgsu.showUserAndLogMessage(
            QCoreApplication.translate(
                "QgsFmvLayers", "Failed Update FootPrint Layer! : "
            ),
            str(e),
        )


def UpdateBeamsData(
    packet, cornerPointUL, cornerPointUR, cornerPointLR, cornerPointLL, ele
):
    """ Update Beams Values """
    lat = packet.SensorLatitude
    lon = packet.SensorLongitude
    alt = packet.SensorTrueAltitude

    global groupName
    beamsLyr = selectLayerByName(Beams_lyr, groupName)

    try:
        if all(
            v is not None
            for v in [
                beamsLyr,
                lat,
                lon,
                alt,
                cornerPointUL,
                cornerPointUR,
                cornerPointLR,
                cornerPointLL,
            ]
        ) and all(
            v >= 2
            for v in [
                len(cornerPointUL),
                len(cornerPointUR),
                len(cornerPointLR),
                len(cornerPointLL),
            ]
        ):
            beamsLyr.startEditing()
            if beamsLyr.featureCount() == 0:

                # UL
                featureUL = QgsFeature()
                featureUL.setAttributes(
                    [lon, lat, alt, cornerPointUL[1], cornerPointUL[0]]
                )
                featureUL.setGeometry(
                    QgsLineString(
                        QgsPoint(lon, lat, alt),
                        QgsPoint(cornerPointUL[1], cornerPointUL[0]),
                    )
                )
                beamsLyr.addFeatures([featureUL])
                # UR
                featureUR = QgsFeature()
                featureUR.setAttributes(
                    [lon, lat, alt, cornerPointUR[1], cornerPointUR[0]]
                )
                featureUR.setGeometry(
                    QgsLineString(
                        QgsPoint(lon, lat, alt),
                        QgsPoint(cornerPointUR[1], cornerPointUR[0]),
                    )
                )
                beamsLyr.addFeatures([featureUR])
                # LR
                featureLR = QgsFeature()
                featureLR.setAttributes(
                    [lon, lat, alt, cornerPointLR[1], cornerPointLR[0]]
                )
                featureLR.setGeometry(
                    QgsLineString(
                        QgsPoint(lon, lat, alt),
                        QgsPoint(cornerPointLR[1], cornerPointLR[0]),
                    )
                )
                beamsLyr.addFeatures([featureLR])
                # LL
                featureLL = QgsFeature()
                featureLL.setAttributes(
                    [lon, lat, alt, cornerPointLL[1], cornerPointLL[0]]
                )
                featureLL.setGeometry(
                    QgsLineString(
                        QgsPoint(lon, lat, alt),
                        QgsPoint(cornerPointLL[1], cornerPointLL[0]),
                    )
                )
                beamsLyr.addFeatures([featureLL])

            else:
                # UL
                beamsLyr.dataProvider().changeAttributeValues(
                    {
                        1: {
                            0: lon,
                            1: lat,
                            2: alt,
                            3: cornerPointUL[1],
                            4: cornerPointUL[0],
                        }
                    }
                )
                beamsLyr.dataProvider().changeGeometryValues(
                    {
                        1: QgsGeometry(
                            QgsLineString(
                                QgsPoint(lon, lat, alt),
                                QgsPoint(cornerPointUL[1], cornerPointUL[0]),
                            )
                        )
                    }
                )
                # UR
                beamsLyr.dataProvider().changeAttributeValues(
                    {
                        2: {
                            0: lon,
                            1: lat,
                            2: alt,
                            3: cornerPointUR[1],
                            4: cornerPointUR[0],
                        }
                    }
                )
                beamsLyr.dataProvider().changeGeometryValues(
                    {
                        2: QgsGeometry(
                            QgsLineString(
                                QgsPoint(lon, lat, alt),
                                QgsPoint(cornerPointUR[1], cornerPointUR[0]),
                            )
                        )
                    }
                )
                # LR
                beamsLyr.dataProvider().changeAttributeValues(
                    {
                        3: {
                            0: lon,
                            1: lat,
                            2: alt,
                            3: cornerPointLR[1],
                            4: cornerPointLR[0],
                        }
                    }
                )
                beamsLyr.dataProvider().changeGeometryValues(
                    {
                        3: QgsGeometry(
                            QgsLineString(
                                QgsPoint(lon, lat, alt),
                                QgsPoint(cornerPointLR[1], cornerPointLR[0]),
                            )
                        )
                    }
                )
                # LL
                beamsLyr.dataProvider().changeAttributeValues(
                    {
                        4: {
                            0: lon,
                            1: lat,
                            2: alt,
                            3: cornerPointLL[1],
                            4: cornerPointLL[0],
                        }
                    }
                )
                beamsLyr.dataProvider().changeGeometryValues(
                    {
                        4: QgsGeometry(
                            QgsLineString(
                                QgsPoint(lon, lat, alt),
                                QgsPoint(cornerPointLL[1], cornerPointLL[0]),
                            )
                        )
                    }
                )

            CommonLayer(beamsLyr)
            # 3D Style
            if ele:
                SetDefaultBeams3DStyle(beamsLyr)

    except Exception as e:
        qgsu.showUserAndLogMessage(
            QCoreApplication.translate("QgsFmvUtils", "Failed Update Beams Layer! : "),
            str(e),
        )


def UpdateTrajectoryData(packet, ele):
    """ Update Trajectory Values """
    lat = packet.SensorLatitude
    lon = packet.SensorLongitude

    global groupName
    trajectoryLyr = selectLayerByName(Trajectory_lyr, groupName)

    try:
        if all(v is not None for v in [trajectoryLyr, lat, lon]):
            trajectoryLyr.startEditing()
            f = QgsFeature()
            if trajectoryLyr.featureCount() == 0:
                f.setAttributes([lon, lat])
                f.setGeometry(
                    QgsLineString(QgsPoint(lon, lat), QgsPoint(lon, lat))
                )
                trajectoryLyr.addFeatures([f])

            else:
                f_last = trajectoryLyr.getFeature(trajectoryLyr.featureCount())
                f.setAttributes([lon, lat])
                f.setGeometry(
                    QgsLineString(
                        QgsPoint(lon, lat),
                        QgsPoint(
                            f_last.attribute(0),
                            f_last.attribute(1),
                        ),
                    )
                )
                trajectoryLyr.addFeatures([f])

            CommonLayer(trajectoryLyr)
            # 3D Style
            if ele:
                SetDefaultTrajectory3DStyle(trajectoryLyr)

    except Exception as e:
        qgsu.showUserAndLogMessage(
            QCoreApplication.translate(
                "QgsFmvUtils", "Failed Update Trajectory Layer! : "
            ),
            str(e),
        )


def UpdateFrameAxisData(imgSS, sensor, framecenter, ele):
    """ Update Frame Axis Values """
    global crtSensorSrc2, groupName, frameAxisMarker

    lat = sensor[0]
    lon = sensor[1]
    alt = sensor[2]
    fc_lat = framecenter[0]
    fc_lon = framecenter[1]
    fc_alt = framecenter[2]

    frameaxisLyr = selectLayerByName(FrameAxis_lyr, groupName)

    try:
        if all(v is not None for v in [frameaxisLyr, lat, lon, alt, fc_lat, fc_lon]):
            if imgSS != crtSensorSrc2:
                SetDefaultFrameAxisStyle(frameaxisLyr, imgSS)
                crtSensorSrc2 = imgSS
            frameaxisLyr.startEditing()
            if frameaxisLyr.featureCount() == 0:
                f = QgsFeature()
                f.setAttributes([lon, lat, alt, fc_lon, fc_lat, fc_alt])
                f.setGeometry(
                    QgsLineString(
                        QgsPoint(lon, lat, alt), QgsPoint(fc_lon, fc_lat, fc_alt)
                    )
                )
                frameaxisLyr.addFeatures([f])
            else:
                frameaxisLyr.dataProvider().changeAttributeValues(
                    {1: {0: lon, 1: lat, 2: alt, 3: fc_lon, 4: fc_lat, 5: fc_alt}}
                )
                frameaxisLyr.dataProvider().changeGeometryValues(
                    {
                        1: QgsGeometry(
                            QgsLineString(
                                QgsPoint(lon, lat, alt),
                                QgsPoint(fc_lon, fc_lat, fc_alt),
                            )
                        )
                    }
                )

            CommonLayer(frameaxisLyr)
            # 3D Style
            if ele:
                SetDefaultFrameAxis3DStyle(frameaxisLyr)

    except Exception as e:
        qgsu.showUserAndLogMessage(
            QCoreApplication.translate(
                "QgsFmvUtils", "Failed Update Frame axis Layer! : "
            ),
            str(e),
        )


def UpdateFrameCenterData(packet, ele):
    """ Update FrameCenter Values """
    lat = packet[0]
    lon = packet[1]
    alt = packet[2]

    if alt is None:
        alt = 0.0

    global groupName
    frameCenterLyr = selectLayerByName(FrameCenter_lyr, groupName)

    try:
        if all(v is not None for v in [frameCenterLyr, lat, lon, alt]):
            frameCenterLyr.startEditing()

            if frameCenterLyr.featureCount() == 0:
                feature = QgsFeature()
                feature.setAttributes([lon, lat, alt])
                p = QgsPointXY()
                p.set(lon, lat)
                feature.setGeometry(QgsGeometry.fromPointXY(p))
                frameCenterLyr.addFeatures([feature])

            else:
                frameCenterLyr.dataProvider().changeAttributeValues(
                    {1: {0: lon, 1: lat, 2: alt}}
                )

                frameCenterLyr.dataProvider().changeGeometryValues(
                    {1: QgsGeometry.fromPointXY(QgsPointXY(lon, lat))}
                )

            CommonLayer(frameCenterLyr)
            # 3D Style
            if ele:
                SetDefaultFrameCenter3DStyle(frameCenterLyr)

    except Exception as e:
        qgsu.showUserAndLogMessage(
            QCoreApplication.translate(
                "QgsFmvUtils", "Failed Update Frame Center Layer! : "
            ),
            str(e),
        )


def UpdatePlatformData(packet, ele):
    """ Update PlatForm Values """
    global crtPltTailNum, groupName

    lat = packet.SensorLatitude
    lon = packet.SensorLongitude
    alt = packet.SensorTrueAltitude
    PlatformHeading = packet.PlatformHeadingAngle
    platformTailNumber = packet.PlatformTailNumber
    platformLyr = selectLayerByName(Platform_lyr, groupName)

    try:
        if all(v is not None for v in [platformLyr, lat, lon, alt, PlatformHeading]):
            if platformTailNumber != crtPltTailNum:
                SetDefaultPlatformStyle(platformLyr, platformTailNumber)
                crtPltTailNum = platformTailNumber

            platformLyr.startEditing()
            platformLyr.renderer().symbol().setAngle(float(PlatformHeading))

            if platformLyr.featureCount() == 0:
                feature = QgsFeature()
                feature.setAttributes([lon, lat, alt])
                feature.setGeometry(QgsPoint(lon, lat, alt))
                platformLyr.addFeatures([feature])

            else:
                platformLyr.dataProvider().changeAttributeValues(
                    {1: {0: lon, 1: lat, 2: alt}}
                )

                platformLyr.dataProvider().changeGeometryValues(
                    {1: QgsGeometry(QgsPoint(lon, lat, alt))}
                )

            CommonLayer(platformLyr)
            # 3D Style
            if ele:
                SetDefaultPlatform3DStyle(platformLyr)

    except Exception as e:
        qgsu.showUserAndLogMessage(
            QCoreApplication.translate(
                "QgsFmvUtils", "Failed Update Platform Layer! : "
            ),
            str(e),
        )


def CommonLayer(value):
    """ Common commands Layers """
    value.commitChanges()
    value.updateExtents()
    iface.layerTreeView().refreshLayerSymbology(value.id())


def CreateGroupByName(name=frames_g):
    """ Create Group if not exist """
    global groupName
    root = _layerreg.layerTreeRoot()
    videogroup = root.findGroup(groupName)
    group = videogroup.findGroup(name)
    if group is None:
        # group = root.insertGroup(-1, name)  # Insert on bottom
        group = videogroup.insertGroup(-1, name)  # Insert on bottom
        # Unchecked visibility
        group.setItemVisibilityCheckedRecursive(False)
        group.setExpanded(False)


def RemoveGroupByName(name=frames_g):
    """ Remove Group if not exist """
    root = _layerreg.layerTreeRoot()
    group = root.findGroup(name)
    if group is not None:
        for child in group.children():
            dump = child.name()
            _layerreg.removeMapLayer(dump.split("=")[-1].strip())
        root.removeChildNode(group)


def CreateVideoLayers(ele, name):
    """ Create Video Layers """
    global groupName
    groupName = name

    if selectLayerByName(Footprint_lyr, groupName) is None:
        lyr_footprint = newPolygonsLayer(
            None,
            [
                "Corner Longitude Point 1",
                "Corner Latitude Point 1",
                "Corner Longitude Point 2",
                "Corner Latitude Point 2",
                "Corner Longitude Point 3",
                "Corner Latitude Point 3",
                "Corner Longitude Point 4",
                "Corner Latitude Point 4",
            ],
            epsg,
            Footprint_lyr,
        )
        SetDefaultFootprintStyle(lyr_footprint)
        addLayerNoCrsDialog(lyr_footprint, group=groupName)


    if selectLayerByName(Platform_lyr, groupName) is None:
        lyr_platform = newPointsLayer(
            None, ["longitude", "latitude", "altitude"], epsg, Platform_lyr, PointZ
        )
        SetDefaultPlatformStyle(lyr_platform)
        addLayerNoCrsDialog(lyr_platform, group=groupName)

    QApplication.processEvents()


def ExpandLayer(layer, value=True):
    """Collapse/Expand layer"""
    ltl = _layerreg.layerTreeRoot().findLayer(layer.id())
    ltl.setExpanded(value)
    QApplication.processEvents()


def SetDefaultFootprintStyle(layer, sensor="DEFAULT"):
    """ Footprint Symbol """
    style = S.getSensor(sensor)
    fill_sym = QgsFillSymbol.createSimple(
        {
            "color": style["COLOR"],
            "outline_color": style["OUTLINE_COLOR"],
            "outline_style": style["OUTLINE_STYLE"],
            "outline_width": style["OUTLINE_WIDTH"],
        }
    )
    renderer = QgsSingleSymbolRenderer(fill_sym)
    layer.setRenderer(renderer)


def SetDefaultPlatformStyle(layer, platform="DEFAULT"):
    """ Platform Symbol """
    style = S.getPlatform(platform)

    svgStyle = {}
    svgStyle["name"] = style["NAME"]
    svgStyle["outline"] = style["OUTLINE"]
    svgStyle["outline-width"] = style["OUTLINE_WIDTH"]
    svgStyle["size"] = style["SIZE"]

    symbol_layer = QgsSvgMarkerSymbolLayer.create(svgStyle)
    layer.renderer().symbol().changeSymbolLayer(0, symbol_layer)


def SetDefaultFrameCenterStyle(layer):
    """ Frame Center Symbol """
    style = S.getFrameCenterPoint()
    symbol = QgsMarkerSymbol.createSimple(
        {
            "name": style["NAME"],
            "line_color": style["LINE_COLOR"],
            "line_width": style["LINE_WIDTH"],
            "size": style["SIZE"],
        }
    )
    renderer = QgsSingleSymbolRenderer(symbol)
    layer.setRenderer(renderer)


# TODO : Update layer symbology if draw color change?
# def UpdateStylesDrawLayers(NameSpace):
#     ''' Update Symbology Drawing Layers '''
#     s = QSettings()
#     pointLyr = selectLayerByName(Point_lyr, groupName)
#     if pointLyr is None:
#         return
#
#     style = S.getDrawingPoint()
#     LINE_COLOR = s.value(NameSpace + "/Options/drawings/points/pen")
#
#     symbol = QgsMarkerSymbol.createSimple(
#         {'name': style["NAME"],
#          'line_color': LINE_COLOR.name(),
#          'line_width': s.value(NameSpace + "/Options/drawings/points/width"),
#          'size': style["SIZE"]})
#
#     renderer = QgsSingleSymbolRenderer(symbol)
#     pointLyr.setRenderer(renderer)
#     CommonLayer(pointLyr)
#
#     linelyr = selectLayerByName(Line_lyr, groupName)
#     if linelyr is None:
#         return
#
#     style = S.getDrawingLine()
#     symbol = linelyr.renderer().symbol()
#
#     COLOR = s.value(NameSpace + "/Options/drawings/lines/pen")
#
#     symbol.setColor(COLOR.name())
#     symbol.setWidth(s.value(NameSpace + "/Options/drawings/lines/width"))
#     CommonLayer(linelyr)
#
#     polyLyr = selectLayerByName(Polygon_lyr, groupName)
#     if polyLyr is None:
#         return
#
#     style = S.getDrawingPolygon()
#
#     OUTLINE_COLOR = s.value(NameSpace + "/Options/drawings/polygons/pen")
#     COLOR = s.value(NameSpace + "/Options/drawings/polygons/brush")
#
#     fill_sym = QgsFillSymbol.createSimple({'color': COLOR.name(),
#                                        'outline_color': OUTLINE_COLOR.name(),
#                                        'outline_style': style['OUTLINE_STYLE'],
#                                        'outline_width': s.value(NameSpace + "/Options/drawings/polygons/width")})
#
#     renderer = QgsSingleSymbolRenderer(fill_sym)
#     polyLyr.setRenderer(renderer)
#     CommonLayer(polyLyr)
#     QApplication.processEvents()
#     return


def addLayer(layer, loadInLegend=True, group=None, isSubGroup=False):
    """
    Add one or several layers to the QGIS session and layer registry.
    @param layer: The layer object or list with layers  to add the QGIS layer registry and session.
    @param loadInLegend: True if this layer should be added to the legend.
    :return: The added layer
    """

    global groupName

    if not hasattr(layer, "__iter__"):
        layer = [layer]
    if group is not None:
        _layerreg.addMapLayers(layer, False)
        root = _layerreg.layerTreeRoot()

        if isSubGroup:
            vg = root.findGroup(groupName)
            g = vg.findGroup(group)
        else:
            g = root.findGroup(group)

        if g is None:
            # Create Group
            node_group = QgsLayerTreeGroup(group)
            root.insertChildNode(0, node_group)

        if isSubGroup:
            vg = root.findGroup(groupName)
            g = vg.findGroup(group)
        else:
            g = root.findGroup(group)

        g.insertChildNode(0, QgsLayerTreeLayer(layer[0]))

    else:
        _layerreg.addMapLayers(layer, loadInLegend)
    return layer


def addLayerNoCrsDialog(layer, loadInLegend=True, group=None, isSubGroup=False):
    """
    Tries to add a layer from layer object
    Same as the addLayer method, but it does not ask for CRS, regardless of current
    configuration in QGIS settings
    """

    settings = QSettings()
    prjSetting3 = settings.value("/Projections/defaultBehavior")
    settings.setValue("/Projections/defaultBehavior", "")
    layer = addLayer(layer, loadInLegend, group, isSubGroup)
    settings.setValue("/Projections/defaultBehavior", prjSetting3)
    QApplication.processEvents()
    return layer


def _toQgsField(f):
    """ Create QgsFiel """
    if isinstance(f, QgsField):
        return f
    return QgsField(f[0], TYPE_MAP.get(f[1], QVariant.String))


def newPointsLayer(
    filename, fields, crs, name=None, geometryType=Point, encoding=encoding
):
    """ Create new Point Layer """
    return newVectorLayer(filename, fields, geometryType, crs, name, encoding)


def newLinesLayer(
    filename, fields, crs, name=None, geometryType=Line, encoding=encoding
):
    """ Create new Line Layer """
    return newVectorLayer(filename, fields, geometryType, crs, name, encoding)


def newPolygonsLayer(filename, fields, crs, name=None, encoding=encoding):
    """ Create new Polygon Layer """
    return newVectorLayer(filename, fields, Polygon, crs, name, encoding)


def newVectorLayer(filename, fields, geometryType, crs, name=None, encoding=encoding):
    """
    Creates a new vector layer
    @param filename: The filename to store the file. The extensions determines the type of file.
    If extension is not among the supported ones, a shapefile will be created and the file will
    get an added '.shp' to its path.
    If the filename is None, a memory layer will be created
    @param fields: the fields to add to the layer. Accepts a QgsFields object or a list of tuples (field_name, field_type)
    Accepted field types are basic Python types str, float, int and bool
    @param geometryType: The type of geometry of the layer to create.
    @param crs: The crs of the layer to create. Accepts a QgsCoordinateSystem object or a string with the CRS authId.
    @param encoding: The layer encoding
    """
    if isinstance(crs, str):
        crs = QgsCoordinateReferenceSystem(crs)
    if filename is None:
        uri = geometryType
        if crs.isValid():
            uri += "?crs=" + crs.authid() + "&"
        fieldsdesc = ["field=" + f for f in fields]

        fieldsstring = "&".join(fieldsdesc)
        uri += fieldsstring

        if name is None:
            name = "mem_layer"
        layer = QgsVectorLayer(uri, name, "memory")

    else:
        formats = QgsVectorFileWriter.supportedFiltersAndFormats()
        OGRCodes = {}
        for (key, value) in formats.items():
            extension = str(key)
            extension = extension[extension.find("*.") + 2 :]
            extension = extension[: extension.find(" ")]
            OGRCodes[extension] = value

        extension = os.path.splitext(filename)[1][1:]
        if extension not in OGRCodes:
            extension = "shp"
            filename = filename + ".shp"

        if isinstance(fields, QgsFields):
            qgsfields = fields
        else:
            qgsfields = QgsFields()
            for field in fields:
                qgsfields.append(_toQgsField(field))

        QgsVectorFileWriter(
            filename, encoding, qgsfields, geometryType, crs, OGRCodes[extension]
        )

        layer = QgsVectorLayer(filename, os.path.basename(filename), "ogr")

    return layer
