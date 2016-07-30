#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Tom van Steijn, Royal HaskoningDHV

import arcpy as ap
import numpy as np 

import os

FORMATS = {
    'en': '{0:.{1:d}f} - {2:.{3:d}f}', 
    'nl': '{0:.{1:d}f} tot {2:.{3:d}f}'}

def safe_get(list_, idx=0):
    '''get first item of list if len(list)>0'''
    try:
        return list_[idx]
    except IndexError:
        return None

def setclassbreaks(layer, start, stop, step):
    lyr = ap.mapping.Layer(layer)
    lyr.symbology.classBreakValues = np.arange(start, stop + step, step)

def fixlabels(layer, decimals=2, lang='en'):
    fmt = FORMATS.get(lang.lower(), 'en')
    lyr = ap.mapping.Layer(layer)
    values = lyr.symbology.classBreakValues
    labels = []
    for left, right in zip(values[:-1], values[1:]):
        if left in {-999, -9999, -1e9}:
            labels.append('< {0:.{1:d}f}'.format(right, decimals))
        elif right in {999, 9999, 1e9}:
            labels.append('> {0:.{1:d}f}'.format(left, decimals))
        else:
            labels.append(fmt.format(left, decimals, right, decimals))    
    lyr.symbology.classBreakLabels = labels

def namereplace(find, repl, grouplayer=None, wildcard='*'):    
    if grouplayer:
        layers = ap.mapping.ListLayers(ap.mapping.Layer(grouplayer), wildcard)
    else:
        doc = ap.mapping.MapDocument('CURRENT')
        layers = ap.mapping.ListLayers(doc, wildcard)
    for layer in layers:
        layer.name = layer.name.replace(find, repl)
    ap.RefreshTOC()

def clip_by_display(features, dataframe):
    mxd = ap.mapping.MapDocument('CURRENT')
    df = safe_get(ap.mapping.ListDataFrames(mxd, dataframe))    
    if df is None:
        raise ValueError('dataframe {} not found'.format(dataframe))
    extent_mask = ap.Polygon(ap.Array([df.extent.lowerLeft,
        df.extent.lowerRight,
        df.extent.upperLeft,
        df.extent.upperRight]))
    filename, ext = os.path.splitext(features)
    output_features = '{}_{}.{}'.format(filename, dataframe, ext)
    ap.analysis.Clip(features, extent_mask, output_features)

def setdatasource(layer, datasource):
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