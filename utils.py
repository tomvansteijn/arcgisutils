#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Tom van Steijn, Royal HaskoningDHV

import arcpy as ap
import numpy as np

import logging
import os

CLASSLABELFORMATS = {
    'en': '{0:.{1:d}f} - {2:.{3:d}f}',
    'msep': '{0:,.{1:d}f} - {2:,.{3:d}f}',
    'nl': '{0:.{1:d}f} tot {2:.{3:d}f}'}

logging.basicConfig(level=logging.DEBUG)

def safe_get(list_, idx=0, default=None):
    """get requested item of list if len(list) > (idx+1), else default"""
    try:
        return list_[idx]
    except IndexError:
        return default


def safe_get_layer(layer):
    """convert layer pathname to layer instance if not layer instance"""
    if not isinstance(layer, ap.mapping.Layer):
        try:
            layer = ap.mapping.Layer(layer)
        except ValueError:
            raise
    return layer


def setclassbreaks_values(layer, values):
    """set class breaks of given layer to values in list"""
    layer = safe_get_layer(layer)
    layer.symbology.classBreakValues = values


def setclassbreaks_range(layer, start, stop, step):
    """set class breaks of given layer to range"""
    layer = safe_get_layer(layer)
    layer.symbology.classBreakValues = np.arange(start, stop + step, step)


def fixlabels(layer, decimals=2, lang='en'):
    """format class break labels"""
    fmt = CLASSLABELFORMATS.get(lang.lower(), 'en')
    lyr = ap.mapping.Layer(layer)
    values = lyr.symbology.classBreakValues
    newlabels = []
    for left, right in zip(values[:-1], values[1:]):
        if left in {-999, -9999, -1e9}:
            newlabels.append('< {0:,.{1:d}f}'.format(right, decimals))
        elif right in {999, 9999, 1e9}:
            newlabels.append('> {0:,.{1:d}f}'.format(left, decimals))
        else:
            newlabels.append(fmt.format(left, decimals, right, decimals))
    lyr.symbology.classBreakLabels = newlabels


def namereplace(find, replace, grouplayer=None, wildcard='*'):
    """replace string in layer names of all layers in TOC, optional wildcard"""
    if grouplayer:
        layers = ap.mapping.ListLayers(ap.mapping.Layer(grouplayer), wildcard)
    else:
        doc = ap.mapping.MapDocument('CURRENT')
        layers = ap.mapping.ListLayers(doc, wildcard)
    for layer in layers:
        layer.name = layer.name.replace(find, replace)
    ap.RefreshTOC()


def export_bookmarks(folder, fileformat='{name:}.pdf', dataframe='Layers'):
    mxd = ap.mapping.MapDocument('CURRENT')
    df = ap.mapping.ListDataFrames(mxd, dataframe)[0]
    for bookmark in ap.mapping.ListBookmarks(mxd, data_frame=df):
        df.extent = bookmark.extent
        name = bookmark.name.replace(',', '').replace(':', '')
        mapfile = os.path.join(folder, fileformat.format(name=name))
        ap.mapping.ExportToPDF(mxd, mapfile)


def export_pages_png(folder, fileformat='{pagename:}.png', dpi=200):
    mxd = ap.mapping.MapDocument('CURRENT')
    for pageNum in range(1, mxd.dataDrivenPages.pageCount + 1):
        mxd.dataDrivenPages.currentPageID = pageNum
        pagename = mxd.dataDrivenPages.pageRow.Name
        filename = os.path.join(folder, fileformat.format(pagename=pagename))
        logging.info('exporting to {}'.format(os.path.basename(filename)))
        ap.mapping.ExportToPNG(mxd, filename, resolution=dpi)


def clip_by_display(features, dataframe):
    """clip features by display extent of dataframe"""
    mxd = ap.mapping.MapDocument('CURRENT')
    df = safe_get(ap.mapping.ListDataFrames(mxd, dataframe))
    if df is None:
        raise ValueError('dataframe {} not found'.format(dataframe))
    extent_mask = ap.Polygon(ap.Array([df.extent.lowerLeft,
        df.extent.lowerRight,
        df.extent.upperLeft,
        df.extent.upperRight]))
    filename, ext = os.path.splitext(features)
    if ext == '':
        output_features = '{}_{}'.format(filename, dataframe)
    else:
        output_features = '{}_{}.{}'.format(filename, dataframe, ext)
    ap.analysis.Clip(features, extent_mask, output_features)


def unique_values(table, field):
    with ap.da.SearchCursor(table, [field]) as cursor:
        return sorted({safe_get(row, 0) for row in cursor})

def splitby(layer, keyfield):
    fields = ap.ListFields(layer)
    field = safe_get([f for f in fields if f.name == keyfield], 0)
    if not field.type in {'String', 'Int'}:
        raise ValueError('{} field not allowed as key'.format(field.type))
    if not isinstance(layer, ap.mapping.Layer):
        layer = ap.mapping.Layer(layer)
    for value in unique_values(layer, keyfield):
        logging.info('selecting {} = {}'.format(keyfield, value))
        query = '"{field:}" = \'{value:}\''.format(field=keyfield, value=value)
        ap.management.SelectLayerByAttribute(layer, 'NEW_SELECTION', query)
        filename, ext = os.path.splitext(layer.dataSource)
        filepath = os.path.join('{filename:}_{value:}{ext:}'.format(
            filename=filename,
            value=value,
            ext=ext,))
        logging.info('exporting to {}'.format(filepath))
        ap.management.CopyFeatures(layer, filepath)


def setdatasource(layer, datasource):
    """set layer or grouplayer to datasource"""
    if not isinstance(layer, ap.mapping.Layer):
        layer = ap.mapping.Layer(layer)
    if layer.isGroupLayer:
        for sublayer in layer:
            setdatasource(sublayer, datasource)
        return
    folder, filename = os.path.split(datasource)
    if datasource.endswith('.shp'):
        workspace = 'SHAPEFILE_WORKSPACE'
    else:
        workspace = 'RASTER_WORKSPACE'
    layer.replaceDataSource(folder, workspace, os.path.splitext(filename)[0])


def copysymbology(layer, symbologylayer):
    """copy layer symbology to layer or grouplayer"""
    if not isinstance(layer, ap.mapping.Layer):
        layer = ap.mapping.Layer(layer)
    if isinstance(symbologylayer, ap.mapping.Layer):
        layerfile = os.path.splitext(symbologylayer.dataSource)[0] + '.lyr'
        ap.management.SaveToLayerFile(symbologylayer, layerfile)
        symbologylayer = layerfile
    if layer.isGroupLayer:
        for sublayer in layer:
            copysymbology(sublayer, symbologylayer)
    else:
        ap.management.ApplySymbologyFromLayer(layer, symbologylayer)
