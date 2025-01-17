import numpy as np
from cv2 import COLOR_BGR2RGB, cvtColor, COLOR_GRAY2RGB, findHomography
import inspect
import json
from math import sin, atan, tan, sqrt, radians, pi, degrees
import os
import shutil
from qgis.PyQt.QtCore import QSettings, QUrl, QEventLoop, QCoreApplication, Qt
from qgis.PyQt.QtGui import QImage, QPainter
from qgis.PyQt.QtNetwork import QNetworkRequest
from qgis.PyQt.QtWidgets import QFileDialog
from qgis.core import (
    QgsApplication,
    QgsRectangle,
    QgsNetworkAccessManager,
    QgsTask,
    QgsRasterLayer,
    QgsProject,
    QgsCoordinateTransform,
    QgsPointXY,
    QgsDistanceArea,
    QgsCoordinateReferenceSystem,
    Qgis as QGis,
)
import subprocess

from QGIS_FMV.utils.QgsFmvUtilsState import globalVariablesState
from osgeo import gdal, osr
from QGIS_FMV.QgsFmvConstants import WGS84String

from QGIS_FMV.geo import QgsGeoUtils
from QGIS_FMV.klvdata.element import UnknownElement
from QGIS_FMV.klvdata.streamparser import StreamParser
from QGIS_FMV.utils.QgsFmvLayers import (
    addLayerNoCrsDialog,
    ExpandLayer,
    UpdateFootPrintData,
    UpdateTrajectoryData,
    UpdateBeamsData,
    UpdatePlatformData,
    UpdateFrameCenterData,
    UpdateFrameAxisData,
    SetcrtSensorSrc,
    SetcrtPltTailNum,
    selectLayerByName,
)
from QGIS_FMV.utils.QgsUtils import QgsUtils as qgsu
from QGIS_FMV.QgsFmvConstants import (
    isWindows,
    frames_g,
    Reverse_geocoding_url,
    min_buffer_size,
    Platform_lyr,
    Footprint_lyr,
    FrameCenter_lyr,
    dtm_buffer,
    ffmpegConf,
    ffmpeg_path,
    ffprobe_path,
    UASLocalMetadataSet,
    KlvHeaderKeyOther,
    defaultTargetWidth,
)

try:
    from pydevd import *
except ImportError:
    None

settings = QSettings()

# Video Global variable instance
gv = None

dtm_data = []
dtm_transform = None
dtm_colLowerBound = 0
dtm_rowLowerBound = 0

_settings = {}


def AddVideoToSettings(row_id, path):
    """ Add video to settings list """
    settings.setValue(getNameSpace() + "/Manager_List/" + row_id, path)


def RemoveVideoToSettings(row_id):
    """ Remove video in settings list """
    settings.remove(getNameSpace() + "/Manager_List/%s" % row_id)


def getVideoManagerList():
    """ Get Video Manager List """
    VideoList = []
    try:
        settings.beginGroup(getNameSpace() + "/Manager_List")
        VideoList = settings.childKeys()
        settings.endGroup()
    except Exception:
        None
    return VideoList


def getVideoFolder(video_file):
    """ Get or create Video Temporal folder """
    home = os.path.expanduser("~")

    qgsu.createFolderByName(home, "QGIS_FMV")

    root, _ = os.path.splitext(os.path.basename(video_file))
    homefmv = os.path.join(home, "QGIS_FMV")

    qgsu.createFolderByName(homefmv, root)
    return os.path.join(homefmv, root)


def RemoveVideoFolder(filename):
    """ Remove video temporal folder if exist """
    videoFile, _ = os.path.splitext(filename)
    folder = getVideoFolder(videoFile)
    try:
        shutil.rmtree(folder, ignore_errors=True)
    except Exception:
        None
    return


def getNameSpace():
    """ Get plugin name space """
    namespace = _callerName().split(".")[0]
    return namespace


def setCenterMode(mode, interface):
    """ Set map center mode """
    global gv
    gv = globalVariablesState()
    gv.setCenterMode(mode)
    gv.setIface(interface)


def getKlvStreamIndex(videoPath, islocal=False):
    if islocal:
        return 0
    # search for klv data in 5 streams
    for i in range(6):
        p = _spawn(
            [
                "-i",
                videoPath,
                "-ss",
                "00:00:00",
                "-to",
                "00:00:01",
                "-map",
                "0:d:" + str(i),
                "-f",
                "data",
                "-",
            ]
        )

        stdout_data, _ = p.communicate()

        if stdout_data == b"":
            continue
        else:
            # look if stream has valid klv data
            if UASLocalMetadataSet in stdout_data or KlvHeaderKeyOther in stdout_data:
                return i
            else:
                qgsu.showUserAndLogMessage(
                    "", "skipping stream " + str(i) + " not a klv stream.", onlyLog=True
                )
                continue

    qgsu.showUserAndLogMessage(
        "Error interpreting klv data, metadata cannot be read.",
        "the parser did not recognize KLV data",
        level=QGis.Warning,
    )
    return 0


def getVideoLocationInfo(videoPath, islocal=False, klv_folder=None, klv_index=0):
    """ Get basic location info about the video """
    location = []
    try:
        if islocal:
            dataFile = os.path.join(klv_folder, "0.0.klv")
            f = open(dataFile, "rb")
            stdout_data = f.read()
        else:
            p = _spawn(
                [
                    "-i",
                    videoPath,
                    "-ss",
                    "00:00:00",
                    "-to",
                    "00:00:01",
                    "-map",
                    "0:d:" + str(klv_index),
                    "-f",
                    "data",
                    "-",
                ]
            )

            stdout_data, _ = p.communicate()
            # qgsu.showUserAndLogMessage("Video Loc info raw result", stdout_data, onlyLog=True)
        if stdout_data == b"":
            # qgsu.showUserAndLogMessage("Error interpreting klv data, metadata cannot be read.", "the parser did not recognize KLV data", level=QGis.Warning)
            return
        for packet in StreamParser(stdout_data):
            if isinstance(packet, UnknownElement):
                qgsu.showUserAndLogMessage(
                    "Error interpreting klv data, metadata cannot be read.",
                    "the parser did not recognize KLV data",
                    level=QGis.Warning,
                )
                continue
            packet.MetadataList()
            centerLat = packet.FrameCenterLatitude
            centerLon = packet.FrameCenterLongitude
            # Target maybe unavailable because of horizontal view
            if centerLat is None and centerLon is None:
                centerLat = packet.SensorLatitude
                centerLon = packet.SensorLongitude
            loc = "-"

            if Reverse_geocoding_url != "":
                try:
                    url = QUrl(
                        Reverse_geocoding_url.format(str(centerLat), str(centerLon))
                    )
                    request = QNetworkRequest(url)
                    reply = QgsNetworkAccessManager.instance().get(request)
                    loop = QEventLoop()
                    reply.finished.connect(loop.quit)
                    loop.exec_()
                    reply.finished.disconnect(loop.quit)
                    loop = None
                    result = reply.readAll()
                    data = json.loads(result.data())

                    if "village" in data["address"] and "state" in data["address"]:
                        loc = (
                            data["address"]["village"] + ", " + data["address"]["state"]
                        )
                    elif "town" in data["address"] and "state" in data["address"]:
                        loc = data["address"]["town"] + ", " + data["address"]["state"]
                    else:
                        loc = data["display_name"]

                except Exception:
                    qgsu.showUserAndLogMessage(
                        "",
                        "getVideoLocationInfo: failed to get address from reverse geocoding service.",
                        onlyLog=True,
                    )

            location = [centerLat, centerLon, loc]

            qgsu.showUserAndLogMessage(
                "",
                "Got Location: lon: "
                + str(centerLon)
                + " lat: "
                + str(centerLat)
                + " location: "
                + str(loc),
                onlyLog=True,
            )

            break
        else:

            qgsu.showUserAndLogMessage(
                QCoreApplication.translate(
                    "QgsFmvUtils", "This video doesn't have Metadata ! : "
                )
            )

    except Exception as e:
        qgsu.showUserAndLogMessage(
            QCoreApplication.translate("QgsFmvUtils", "Video info callback failed! : "),
            str(e),
        )

    return location


def pluginSetting(name, namespace=None, typ=None):
    def _find_in_cache(name, key):
        """ Find key in QGIS settings """
        try:
            for setting in _settings[namespace]:
                if setting["name"] == name:
                    return setting[key]
        except Exception:
            return None
        return None

    def _type_map(t):
        """Return setting python type"""
        if t == "bool":
            return bool
        elif t == "number":
            return float
        else:
            return str

    namespace = namespace or _callerName().split(".")[0]
    full_name = namespace + "/" + name
    if settings.contains(full_name):
        if typ is None:
            typ = _type_map(_find_in_cache(name, "type"))
        v = settings.value(full_name, None, type=typ)
        return v
    else:
        return _find_in_cache(name, "default")


def _callerName():
    """ Get QGIS plugin name """
    stack = inspect.stack()
    parentframe = stack[2][0]
    name = []
    module = inspect.getmodule(parentframe)
    name.append(module.__name__)
    if "self" in parentframe.f_locals:
        name.append(parentframe.f_locals["self"].__class__.__name__)
    codename = parentframe.f_code.co_name
    if codename != "<module>":
        name.append(codename)
    del parentframe
    return ".".join(name)


def askForFiles(parent, msg=None, isSave=False, allowMultiple=False, exts="*"):
    """ dialog for save or load files """
    msg = msg or "Select file"
    caller = _callerName().split(".")
    name = "/".join(["LAST_PATH", caller[-1]])
    namespace = caller[0]
    path = pluginSetting(name, namespace)
    f = None
    if not isinstance(exts, list):
        exts = [exts]
    extString = ";; ".join(
        [
            " {} files (*.{} *.{})".format(e.upper(), e, e.upper())
            if e != "*"
            else "All files (*.*)"
            for e in exts
        ]
    )

    dlg = QFileDialog()

    if allowMultiple:
        ret = dlg.getOpenFileNames(parent, msg, path, "*." + extString)
        if ret:
            f = ret[0]
        else:
            f = ret = None
    else:
        if isSave:
            ret = dlg.getSaveFileName(parent, msg, path, extString) or None
            if ret[0] != "":
                name, ext = os.path.splitext(ret[0])
                if not ext:
                    ret[0] + "." + exts[0]  # Default extension
        else:
            ret = dlg.getOpenFileName(parent, msg, path, extString) or None
        f = ret

    if f is not None:
        setPluginSetting(name, os.path.dirname(f[0]), namespace)

    return ret


def setPluginSetting(name, value, namespace=None):
    """ Set plugin name in QGIS settings """
    namespace = namespace or _callerName().split(".")[0]
    settings.setValue(namespace + "/" + name, value)


def askForFolder(parent, msg=None, options=QFileDialog.ShowDirsOnly):
    """ dialog for save or load folder """
    msg = msg or "Select folder"
    caller = _callerName().split(".")
    name = "/".join(["LAST_PATH", caller[-1]])
    namespace = caller[0]
    path = pluginSetting(name, namespace)
    folder = QFileDialog.getExistingDirectory(parent, msg, path, options)
    if folder:
        setPluginSetting(name, folder, namespace)
    return folder


def convertQImageToMat(img, cn=3):
    """  Converts a QImage into an opencv MAT format  """
    img = img.convertToFormat(QImage.Format_RGB888)
    ptr = img.bits()
    ptr.setsize(img.byteCount())
    return np.array(ptr).reshape(img.height(), img.width(), cn)


def convertMatToQImage(img, t=QImage.Format_RGB888):
    """  Converts an opencv MAT image to a QImage  """
    height, width = img.shape[:2]
    if img.ndim == 3:
        rgb = cvtColor(img, COLOR_BGR2RGB)
    elif img.ndim == 2:
        rgb = cvtColor(img, COLOR_GRAY2RGB)
    else:
        raise Exception("Unstatistified image data format!")
    return QImage(rgb, width, height, t)


def SetGCPsToGeoTransform(
    cornerPointUL,
    cornerPointUR,
    cornerPointLR,
    cornerPointLL,
    frameCenterLon,
    frameCenterLat,
    ele,
):
    """ Make Geotranform from pixel to lon lat coordinates """
    gcps = []
    gv.setCornerUL(cornerPointUL)
    gv.setCornerUR(cornerPointUR)
    gv.setCornerLR(cornerPointLR)
    gv.setCornerLL(cornerPointLL)
    gv.setFrameCenter(frameCenterLat, frameCenterLon)

    xSize = gv.getXSize()
    ySize = gv.getYSize()

    Height = GetFrameCenter()[2]

    gcp = gdal.GCP(
        cornerPointUL[1], cornerPointUL[0], Height, 0, 0, "Corner Upper Left", "1"
    )
    gcps.append(gcp)
    gcp = gdal.GCP(
        cornerPointUR[1], cornerPointUR[0], Height, xSize, 0, "Corner Upper Right", "2"
    )
    gcps.append(gcp)
    gcp = gdal.GCP(
        cornerPointLR[1],
        cornerPointLR[0],
        Height,
        xSize,
        ySize,
        "Corner Lower Right",
        "3",
    )
    gcps.append(gcp)
    gcp = gdal.GCP(
        cornerPointLL[1], cornerPointLL[0], Height, 0, ySize, "Corner Lower Left", "4"
    )
    gcps.append(gcp)
    gcp = gdal.GCP(
        frameCenterLon, frameCenterLat, Height, xSize / 2, ySize / 2, "Center", "5"
    )
    gcps.append(gcp)

    at = gdal.GCPsToGeoTransform(gcps)
    gv.setAffineTransform(at)

    src = np.float64(
        np.array(
            [
                [0.0, 0.0],
                [xSize, 0.0],
                [xSize, ySize],
                [0.0, ySize],
                [xSize / 2.0, ySize / 2.0],
            ]
        )
    )
    dst = np.float64(
        np.array(
            [
                [cornerPointUL[0], cornerPointUL[1]],
                [cornerPointUR[0], cornerPointUR[1]],
                [cornerPointLR[0], cornerPointLR[1]],
                [cornerPointLL[0], cornerPointLL[1]],
                [frameCenterLat, frameCenterLon],
            ]
        )
    )

    try:
        geotransform, _ = findHomography(src, dst)
        gv.setTransform(geotransform)
    except Exception:
        pass

    if geotransform is None:
        qgsu.showUserAndLogMessage(
            "", "Unable to extract a geotransform.", onlyLog=True
        )

    return


def GetSensor():
    """ Get Sensor values """
    return [gv.getSensorLatitude(), gv.getSensorLongitude(), gv.getSensorTrueAltitude()]


def GetFrameCenter():
    """ Get Frame Center values """
    sensorTrueAltitude = gv.getSensorTrueAltitude()
    # if sensor height is null, compute it from sensor altitude.
    if gv.getFrameCenterElevation() is None:
        if sensorTrueAltitude is not None:
            gv.setFrameCenterElevation(sensorTrueAltitude - 500)
        else:
            gv.setFrameCenterElevation(0)

    return [
        gv.getFrameCenterLat(),
        gv.getFrameCenterLon(),
        gv.getFrameCenterElevation(),
    ]


def GetcornerPointUL():
    """ Get Corner upper Left values """
    return gv.getCornerUL()


def GetcornerPointUR():
    """ Get Corner upper Right values """
    return gv.getCornerUR()


def GetcornerPointLR():
    """ Get Corner lower Right values """
    return gv.getCornerLR()


def GetcornerPointLL():
    """ Get Corner lower left values """
    return gv.getCornerLL()


def GetGCPGeoTransform():
    """ Return Geotransform """
    return gv.getTransform()


def SetImageSize(w, h):
    """ Set Image Size """
    gv.setXSize(w)
    gv.setYSize(h)
    return


def GetImageWidth():
    """ Get Image Width """
    return gv.getXSize()


def GetImageHeight():
    """ Get Image Height """
    return gv.getYSize()


def _check_output(cmds, t="ffmpeg"):
    """ Check Output Commands in Python """

    if t == "ffmpeg":
        cmds.insert(0, ffmpeg_path)
    else:
        cmds.insert(0, ffprobe_path)

    return subprocess.check_output(cmds, shell=True, close_fds=(not isWindows))


def _spawn(cmds, t="ffmpeg"):
    """ Subprocess and Shell Commands in Python """

    if t == "ffmpeg":
        cmds.insert(0, ffmpeg_path)
    else:
        cmds.insert(0, ffprobe_path)

    cmds.insert(3, "-preset")
    cmds.insert(4, "ultrafast")

    # qgsu.showUserAndLogMessage("", "spawned : " + " ".join(cmds), onlyLog=True)
    return subprocess.Popen(
        cmds,
        shell=isWindows,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
        close_fds=(not isWindows),
    )


def ResetData():
    """ Reset Global Data """
    SetcrtSensorSrc()
    SetcrtPltTailNum()

def UpdateLayers(packet, parent=None, mosaic=False, group=None):
    """ Update Layers Values """
    gv.setGroupName(group)
    groupName = group
    gv.setFrameCenterElevation(packet.FrameCenterElevation)
    gv.setSensorLatitude(packet.SensorLatitude)
    gv.setSensorLongitude(packet.SensorLongitude)

    sensorTrueAltitude = packet.SensorTrueAltitude
    gv.setSensorTrueAltitude(sensorTrueAltitude)
    sensorRelativeElevationAngle = packet.SensorRelativeElevationAngle
    slantRange = packet.SlantRange
    OffsetLat1 = packet.OffsetCornerLatitudePoint1
    LatitudePoint1Full = packet.CornerLatitudePoint1Full

    UpdatePlatformData(packet, False)
    UpdateTrajectoryData(packet, False)

    frameCenterPoint = [
        packet.FrameCenterLatitude,
        packet.FrameCenterLongitude,
        packet.FrameCenterElevation,
    ]

    # If no framcenter (f.i. horizontal target) don't comptute footprint,
    # beams and frame center
    if frameCenterPoint[0] is None and frameCenterPoint[1] is None:
        gv.setTransform(None)
        return True

    # No framecenter altitude
    if frameCenterPoint[2] is None:
        if sensorRelativeElevationAngle is not None and slantRange is not None:
            frameCenterPoint[2] = (
                sensorTrueAltitude - sin(sensorRelativeElevationAngle) * slantRange
            )
        else:
            frameCenterPoint[2] = 0.0

    # qgsu.showUserAndLogMessage("", "FC Alt:"+str(frameCenterPoint[2]), onlyLog=True)

    if OffsetLat1 is not None and LatitudePoint1Full is None:
        CornerEstimationWithOffsets(packet)
        if mosaic:
            georeferencingVideo(parent)

    elif OffsetLat1 is None and LatitudePoint1Full is None:
        CornerEstimationWithoutOffsets(packet)
        if mosaic:
            georeferencingVideo(parent)

    else:
        cornerPointUL = [
            packet.CornerLatitudePoint1Full,
            packet.CornerLongitudePoint1Full,
        ]
        if None in cornerPointUL:
            return False

        cornerPointUR = [
            packet.CornerLatitudePoint2Full,
            packet.CornerLongitudePoint2Full,
        ]
        if None in cornerPointUR:
            return False

        cornerPointLR = [
            packet.CornerLatitudePoint3Full,
            packet.CornerLongitudePoint3Full,
        ]

        if None in cornerPointLR:
            return False

        cornerPointLL = [
            packet.CornerLatitudePoint4Full,
            packet.CornerLongitudePoint4Full,
        ]

        if None in cornerPointLL:
            return False

        UpdateFootPrintData(
            packet,
            cornerPointUL,
            cornerPointUR,
            cornerPointLR,
            cornerPointLL,
            False,
        )

        UpdateBeamsData(
            packet,
            cornerPointUL,
            cornerPointUR,
            cornerPointLR,
            cornerPointLL,
            False,
        )

        SetGCPsToGeoTransform(
            cornerPointUL,
            cornerPointUR,
            cornerPointLR,
            cornerPointLL,
            frameCenterPoint[1],
            frameCenterPoint[0],
            False,
        )

        if mosaic:
            georeferencingVideo(parent)

    UpdateFrameCenterData(frameCenterPoint, False)
    UpdateFrameAxisData(
        packet.ImageSourceSensor, GetSensor(), frameCenterPoint, False
    )

    # detect if we need a recenter or not. If Footprint and Platform fits in
    # 80% of the map, do not trigger recenter.
    p_lyr = selectLayerByName(Platform_lyr, groupName)

    iface = gv.getIface()
    centerMode = gv.getCenterMode()

    if p_lyr is not None:
        p_lyr_out_extent = p_lyr.extent()

        # Default EPSG is 4326, f_lyr.crs().authid ()
        # Disable transform if we have the same projection wit layers anf
        # canvas
        epsg4326 = "EPSG:4326"
        curAuthId = iface.mapCanvas().mapSettings().destinationCrs().authid()

        if curAuthId != epsg4326:
            xform = QgsCoordinateTransform(
                QgsCoordinateReferenceSystem(epsg4326),
                QgsCoordinateReferenceSystem(curAuthId),
                QgsProject().instance(),
            )

            transP = xform.transform(
                QgsPointXY(
                    list(p_lyr.getFeatures())[0].geometry().asPoint().x(),
                    list(p_lyr.getFeatures())[0].geometry().asPoint().y(),
                )
            )
            p_lyr_out_extent = QgsRectangle(
                transP.x(), transP.y(), transP.x(), transP.y()
            )

        bValue = iface.mapCanvas().extent().xMaximum() - iface.mapCanvas().center().x()

        # create a detection buffer
        map_detec_buffer = iface.mapCanvas().extent().buffered(bValue * -0.7)

        # recenter map on platform
        if not map_detec_buffer.contains(p_lyr_out_extent) and centerMode == 1:
            iface.mapCanvas().setExtent(p_lyr_out_extent)

        # Refresh Canvas
        iface.mapCanvas().refresh()

        return True


def georeferencingVideo(parent):
    """Extract Current Frame Thread
    :param packet: Parent class
    """
    image = parent.videoWidget.currentFrame()

    folder = getVideoFolder(parent.fileName)
    qgsu.createFolderByName(folder, "mosaic")
    out = os.path.join(folder, "mosaic")

    position = str(parent.player.position())

    taskGeoreferencingVideo = QgsTask.fromFunction(
        "Georeferencing Current Frame Task",
        GeoreferenceFrame,
        image=image,
        output=out,
        p=position,
        on_finished=parent.finishedTask,
        flags=QgsTask.CanCancel,
    )

    QgsApplication.taskManager().addTask(taskGeoreferencingVideo)
    return


def GeoreferenceFrame(task, image, output, p):
    """ Save Current Image """
    ext = ".tiff"
    t = "out_" + p + ext
    name = "g_" + p

    src_file = os.path.join(output, t)

    image.save(src_file)

    # Opens source dataset
    src_ds = gdal.OpenEx(
        src_file,
        gdal.OF_RASTER | gdal.OF_READONLY,
        open_options=["NUM_THREADS=ALL_CPUS"],
    )

    # Open destination dataset
    dst_filename = os.path.join(output, name + ext)
    dst_ds = gdal.GetDriverByName("GTiff").CreateCopy(
        dst_filename,
        src_ds,
        0,
        options=[
            "TILED=NO",
            "BIGTIFF=NO",
            "COMPRESS_OVERVIEW=DEFLATE",
            "COMPRESS=LZW",
            "NUM_THREADS=ALL_CPUS",
            "predictor=2",
        ],
    )
    src_ds = None
    # Get raster projection
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)

    # Set projection
    dst_ds.SetProjection(srs.ExportToWkt())

    geotransform_affine = gv.getAffineTransform()
    # Set location
    dst_ds.SetGeoTransform(geotransform_affine)
    dst_ds.GetRasterBand(1).SetNoDataValue(0)
    dst_ds.FlushCache()
    # Close files
    dst_ds = None

    # Add Layer to canvas
    layer = QgsRasterLayer(dst_filename, name)
    addLayerNoCrsDialog(layer, False, frames_g, isSubGroup=True)
    ExpandLayer(layer, False)
    if task.isCanceled():
        return None
    return {"task": task.description()}


def GetGeotransform_affine():
    """ Get current frame affine transformation """
    return gv.getAffineTransform()


def CornerEstimationWithOffsets(packet):
    """Corner estimation using Offsets
    :param packet: Metada packet
    """
    try:

        OffsetLat1 = packet.OffsetCornerLatitudePoint1
        OffsetLon1 = packet.OffsetCornerLongitudePoint1
        OffsetLat2 = packet.OffsetCornerLatitudePoint2
        OffsetLon2 = packet.OffsetCornerLongitudePoint2
        OffsetLat3 = packet.OffsetCornerLatitudePoint3
        OffsetLon3 = packet.OffsetCornerLongitudePoint3
        OffsetLat4 = packet.OffsetCornerLatitudePoint4
        OffsetLon4 = packet.OffsetCornerLongitudePoint4
        frameCenterLat = packet.FrameCenterLatitude
        frameCenterLon = packet.FrameCenterLongitude

        # Lat,Lon
        cornerPointUL = (OffsetLat1 + frameCenterLat, OffsetLon1 + frameCenterLon)
        cornerPointUR = (OffsetLat2 + frameCenterLat, OffsetLon2 + frameCenterLon)
        cornerPointLR = (OffsetLat3 + frameCenterLat, OffsetLon3 + frameCenterLon)
        cornerPointLL = (OffsetLat4 + frameCenterLat, OffsetLon4 + frameCenterLon)

        frameCenterPoint = [
            packet.FrameCenterLatitude,
            packet.FrameCenterLongitude,
            packet.FrameCenterElevation,
        ]

        # If no framcenter (f.i. horizontal target) don't comptute footprint,
        # beams and frame center
        if frameCenterPoint[0] is None and frameCenterPoint[1] is None:
            gv.setTransform(None)
            return True

        UpdateFootPrintData(
            packet,
            cornerPointUL,
            cornerPointUR,
            cornerPointLR,
            cornerPointLL,
            False,
        )

        UpdateBeamsData(
            packet,
            cornerPointUL,
            cornerPointUR,
            cornerPointLR,
            cornerPointLL,
            False,
        )

        SetGCPsToGeoTransform(
            cornerPointUL,
            cornerPointUR,
            cornerPointLR,
            cornerPointLL,
            frameCenterPoint[1],
            frameCenterPoint[0],
            False,
        )

    except Exception:
        return False

    return True


def CornerEstimationWithoutOffsets(
    packet=None, sensor=None, frameCenter=None, FOV=None, others=None
):
    """ Corner estimation without Offsets """
    try:
        if packet is not None:
            sensorLatitude = packet.SensorLatitude
            sensorLongitude = packet.SensorLongitude
            sensorTrueAltitude = packet.SensorTrueAltitude
            frameCenterLat = packet.FrameCenterLatitude
            frameCenterLon = packet.FrameCenterLongitude
            frameCenterElevation = packet.FrameCenterElevation
            sensorVerticalFOV = packet.SensorVerticalFieldOfView
            sensorHorizontalFOV = packet.SensorHorizontalFieldOfView
            headingAngle = packet.PlatformHeadingAngle
            sensorRelativeAzimut = packet.SensorRelativeAzimuthAngle
            targetWidth = packet.targetWidth
            slantRange = packet.SlantRange
        else:
            sensorLatitude = sensor[1]
            sensorLongitude = sensor[0]
            sensorTrueAltitude = sensor[2]
            frameCenterLat = frameCenter[1]
            frameCenterLon = frameCenter[0]
            frameCenterElevation = frameCenter[2]
            sensorVerticalFOV = FOV[0]
            sensorHorizontalFOV = FOV[1]
            headingAngle = others[0]
            sensorRelativeAzimut = others[1]
            targetWidth = others[2]
            slantRange = others[3]

        # If target width = 0 (occurs on some platforms), compute it with the slate range.
        # Otherwise it leaves the footprint as a point.
        # In some case targetWidth don't have value then equal to 0
        if targetWidth is None:
            targetWidth = 0
        if slantRange is None:
            slantRange = 0
        if targetWidth == 0 and slantRange != 0:
            targetWidth = 2.0 * slantRange * tan(radians(sensorHorizontalFOV / 2.0))
        elif targetWidth == 0 and slantRange == 0:
            # default target width to not leave footprint as a point.
            targetWidth = defaultTargetWidth
        #             qgsu.showUserAndLogMessage(QCoreApplication.translate(
        #                 "QgsFmvUtils", "Target width unknown, defaults to: " + str(targetWidth) + "m."))

        # compute distance to ground
        if (
            frameCenterElevation != 0
            and sensorTrueAltitude is not None
            and frameCenterElevation is not None
        ):
            sensorGroundAltitude = sensorTrueAltitude - frameCenterElevation
        elif frameCenterElevation == 0 and sensorTrueAltitude is not None:
            sensorGroundAltitude = sensorTrueAltitude
        else:
            # can't compute footprint without sensorGroundAltitude
            return False

        if sensorLatitude == 0:
            return False

        if sensorLongitude is None or sensorLatitude is None:
            return False

        if frameCenterLon is None or frameCenterLat is None:
            return False

        initialPoint = QgsPointXY(sensorLongitude, sensorLatitude)
        destPoint = QgsPointXY(frameCenterLon, frameCenterLat)

        da = QgsDistanceArea()
        da.setEllipsoid(WGS84String)
        distance = da.measureLine(initialPoint, destPoint)

        if distance == 0:
            return False

        if sensorVerticalFOV > 0 and sensorHorizontalFOV > sensorVerticalFOV:
            aspectRatio = sensorVerticalFOV / sensorHorizontalFOV

        else:
            aspectRatio = 0.75

        value2 = (headingAngle + sensorRelativeAzimut) % 360.0  # Heading
        value3 = targetWidth / 2.0

        value5 = sqrt(pow(distance, 2.0) + pow(sensorGroundAltitude, 2.0))
        value6 = targetWidth * aspectRatio / 2.0

        degrees_value = degrees(atan(value3 / distance))

        value8 = degrees(atan(distance / sensorGroundAltitude))
        value9 = degrees(atan(value6 / value5))
        value10 = value8 + value9
        value11 = sensorGroundAltitude * tan(radians(value10))
        value12 = value8 - value9
        value13 = sensorGroundAltitude * tan(radians(value12))
        value14 = distance - value13
        value15 = value11 - distance
        value16 = value3 - value14 * tan(radians(degrees_value))
        value17 = value3 + value15 * tan(radians(degrees_value))
        distance2 = sqrt(pow(value14, 2.0) + pow(value16, 2.0))
        value19 = sqrt(pow(value15, 2.0) + pow(value17, 2.0))
        value20 = degrees(atan(value16 / value14))
        value21 = degrees(atan(value17 / value15))

        # CP Up Left
        bearing = (value2 + 360.0 - value21) % 360.0
        cornerPointUL = list(
            reversed(QgsGeoUtils.destination(destPoint, value19, bearing))
        )

        # CP Up Right
        bearing = (value2 + value21) % 360.0
        cornerPointUR = list(
            reversed(QgsGeoUtils.destination(destPoint, value19, bearing))
        )

        # CP Low Right
        bearing = (value2 + 180.0 - value20) % 360.0
        cornerPointLR = list(
            reversed(QgsGeoUtils.destination(destPoint, distance2, bearing))
        )

        # CP Low Left
        bearing = (value2 + 180.0 + value20) % 360.0
        cornerPointLL = list(
            reversed(QgsGeoUtils.destination(destPoint, distance2, bearing))
        )

        frameCenterPoint = [frameCenterLat, frameCenterLon, frameCenterElevation]

        # If no frame center (f.i. horizontal target) don't compute footprint,
        # beams and frame center
        if frameCenterPoint[0] is None and frameCenterPoint[1] is None:
            gv.setTransform(None)
            return True

        if sensor is not None:
            return cornerPointUL, cornerPointUR, cornerPointLR, cornerPointLL

        UpdateFootPrintData(
            packet,
            cornerPointUL,
            cornerPointUR,
            cornerPointLR,
            cornerPointLL,
            False,
        )

        UpdateBeamsData(
            packet,
            cornerPointUL,
            cornerPointUR,
            cornerPointLR,
            cornerPointLL,
            False,
        )

        SetGCPsToGeoTransform(
            cornerPointUL,
            cornerPointUR,
            cornerPointLR,
            cornerPointLL,
            frameCenterPoint[1],
            frameCenterPoint[0],
            False,
        )

    except Exception as e:
        qgsu.showUserAndLogMessage(
            QCoreApplication.translate(
                "QgsFmvUtils", "CornerEstimationWithoutOffsets failed! : "
            ),
            str(e),
        )
        return False

    return True


def GetDemAltAt(lon, lat):
    """ Obtain height for Point,intersecting with DEM """
    alt = 0

    xOrigin = dtm_transform[0]
    yOrigin = dtm_transform[3]
    pixelWidth = dtm_transform[1]
    pixelHeight = -dtm_transform[5]

    col = int((lon - xOrigin) / pixelWidth)
    row = int((yOrigin - lat) / pixelHeight)
    try:
        alt = dtm_data[row - dtm_rowLowerBound][col - dtm_colLowerBound]
    except IndexError:
        pass
        # qgsu.showUserAndLogMessage(
        #        "", "GetDemAltAt: Point is out of DEM.", onlyLog=True)

    return float(alt)


def BurnDrawingsImage(source, overlay):
    """Burn drawings into image
    @type source: QImage
    @param source: Original Image

    @type overlay: QImage
    @param overlay: Drawings image
    @return: QImage
    """
    base = source.scaled(overlay.size(), Qt.IgnoreAspectRatio)

    p = QPainter()
    p.setRenderHint(QPainter.HighQualityAntialiasing)
    p.begin(base)
    # with CompositionMode_SourceOut we have a black image at the end.
    p.setCompositionMode(QPainter.CompositionMode_SourceOver)
    p.drawImage(0, 0, overlay)
    p.end()

    # Restore size
    base = base.scaled(source.size(), Qt.IgnoreAspectRatio)
    return base