"""
DripTorch I/O helper functions
"""

# Internal imports
from .templates import QuicFire
from .errors import *
from ._version import __version__

# External imports
from folium import Polygon
import numpy as np
import pyproj
from shapely.geometry import mapping, shape, MultiLineString, LineString, Point, MultiPoint
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform
from typing import Union


class Projector:
    """
    Helper class to handle reprojections during I/O operations.

    Parameters
    ----------
    src_epsg : int
        Source EPSG code
    dst_epsg : int
        Destination EPSG code
    """

    def __init__(self, src_epsg: int, dst_epsg: int):

        # Configure transformer for forward projections
        self.forward_proj = pyproj.Transformer.from_proj(
            pyproj.Proj(f'epsg:{src_epsg}'),
            pyproj.Proj(f'epsg:{dst_epsg}'),
            always_xy=True
        )

        # Configure transform for inverse projections
        self.backward_proj = pyproj.Transformer.from_proj(
            pyproj.Proj(f'epsg:{dst_epsg}'),
            pyproj.Proj(f'epsg:{src_epsg}'),
            always_xy=True
        )

    def forward(self, geometry: BaseGeometry) -> BaseGeometry:
        """Project from source EPSG to destination EPSG

        Parameters
        ----------
        geometry : BaseGeometry
            Input geometry to reproject

        Returns
        -------
        BaseGeometry
            Reprojected geometry
        """

        return transform(self.forward_proj.transform, geometry)

    def backward(self, geometry: BaseGeometry) -> BaseGeometry:
        """Project from destimation EPSG to source EPSG

        Parameters
        ----------
        geometry : BaseGeometry
            Input geometry to reproject

        Returns
        -------
        BaseGeometry
            Reprojected geometry
        """

        return transform(self.backward_proj.transform, geometry)

    @staticmethod
    def estimate_utm_epsg(lon, lat, **kwargs):
        """Estimate the UTM EPSG code for a given point

        Parameters
        ----------
        lon : float
            Longitude of point
        lat : float
            Latitude of point

        Returns
        -------
        int
            UTM EPSG code
        """
        return int(32700-round((45+lat)/90, 0)*100+round((183+lon)/6, 0))

    @classmethod
    def web_mercator_to_utm(cls, geometry: BaseGeometry) -> BaseGeometry:
        """Convert geometry from Web Mercator to UTM

        Parameters
        ----------
        geometry : BaseGeometry
            Input geometry to reproject

        Returns
        -------
        BaseGeometry
            Reprojected geometry
        """

        lon, lat = list(geometry.centroid.coords[0])
        utm_epsg = cls.estimate_utm_epsg(lon, lat)

        projector = cls(4326, utm_epsg)

        return utm_epsg, projector.forward(geometry)

    @classmethod
    def to_web_mercator(cls, geometry: Union[BaseGeometry, dict], src_epsg: int) -> Union[BaseGeometry, dict]:
        """Convenience method to project a shapely geometry or GeoJSON feature to web mercator

        Parameters
        ----------
        geometry : Union[BaseGeometry, dict]
            Either a shapely geometry or a GeoJSON feature (not a feature collection)
        src_epsg : int
            Source EPSG code that the spatial data are currently project in


        Returns
        -------
        BaseGeometry | dict
            A shapely geometry or GeoJSON feature projected in 4326
        """

        projector = cls(src_epsg, 4326)

        if isinstance(geometry, dict):
            geometry = shape(geometry)
            return mapping(projector.forward(geometry))

        return projector.forward(geometry)


def read_geojson_polygon(geojson: dict) -> Polygon:
    """Parse a GeoJSON to a shapely Polygon

    Parameters
    ----------
    geojson : dict
        GeoJSON feature projected in 4326

    Raises
    ------
    GeojsonError
        Raise error if we can't figure out the formatting

    Returns
    -------
    Polygon
        Shapely polygon geometry
    """

    # If the geojson is a feature collection then we loop over the features
    # and find the first instance of a polygon geometry type
    if geojson['type'] == 'FeatureCollection':
        for feature in geojson['features']:
            if feature['geometry']['type'].lower() == 'polygon':
                geometry = shape(feature['geometry'])
                break

    # Maybe it's just the geometry?
    elif geojson['type'].lower() == 'Polygon':
        geometry = shape(geojson)

    # Fix your shit, we're not gonna to keep trying to guess
    else:
        raise GeojsonError(GeojsonError.read_error)

    return geometry


def write_geojson(geometries: list[BaseGeometry], src_epsg: int, dst_epsg: int = 4326, properties={},
                  style={}, elapsed_time=None) -> dict:
    """Write a list of shapely geometries to GeoJSON

    Parameters
    ----------
    geometries : list[BaseGeometry]
        List of shapely geometries
    src_epsg : int
        EPSG code of the CRS that the spatial data are currently projected in.
    dst_epsg : int
        EPSG code of the CRS that the spatial data will be projected to.
    properties : dict, optional
        Properties for each feature. Defaults to {}.
    style : dict, optional
        Rendering style applied to all features. Defaults to {}.
    elapsed_time : float, optional
        Time elapsed during the firing operation. Defaults to None.

    Returns
    -------
    dict
        GeoJSON feature collection
    """

    # Get a projector instance for inverse projection
    projector = Projector(src_epsg, dst_epsg)

    # Get the names of all the props
    property_names = properties.keys()

    # Loop over each geometry in the input list and write to GeoJSON
    features = []
    for i, geometry in enumerate(geometries):

        props = {}
        for name in property_names:
            props[name] = properties[name][i]

        features.append(
            {
                'type': 'Feature',
                'properties': props | style,
                'geometry': mapping(projector.forward(geometry))
            }
        )

    # Compile the features in a feature collection
    geojson = {
        'type': 'FeatureCollection',
        'features': features
    }

    # Add elapsed time to properties if it was provided
    if elapsed_time is not None:
        geojson['elapsedTime'] = elapsed_time

    # Add DripTorch version to the GeoJSON
    geojson['driptorchVersion'] = __version__

    return geojson


def write_quicfire(geometry: list, times: list, elapsed_time, resolution: int = 1) -> str:
    """Writes a QUIC-fire ignition file

    Parameters
    ----------
    geometry : list
        List of geometry to write
    times : list
        Arrival times corresponding to the geometry coordinates (seconds)
    resolution : int
        Horizontal resolution of QUIC-fire domain (meters). Defaults to 1.

    Raises
    ------
    ExportError
        Error if Point and (Multi)LineString geometry types are mixed

    Returns
    -------
    str
        QUIC-fire formated ignition file
    """

    rows = ''
    n_rows = 0

    # Process ignition paths for QF format 5
    if all(isinstance(x, (LineString, MultiLineString)) for x in geometry):

        # Loop over each geometry
        for i, geom in enumerate(geometry):
            time = times[i]
            # Check if we have a linestring and wrap in a list if so
            if isinstance(geom, LineString):
                geom = [geom]
                time = [time]
            # Loop over each line in the geometry
            for j, part in enumerate(geom):
                coords = np.array(part.coords)
                t = time[j]
                # Loop over each coordinate in the line
                for k, xy in enumerate(coords[:-1]):
                    rows += f'{xy[0]} {xy[1]} {coords[k+1,0]} {coords[k+1,1]} {t[k]} {t[k+1]}\n'
                    n_rows += 1
        file = QuicFire.fmt_5.substitute(
            n_rows=n_rows, rows=rows, elapsed_time=round(elapsed_time, 2))

    # Process ignition paths for QF format 4
    elif all(isinstance(x, (Point, MultiPoint)) for x in geometry):
        # Loop over each geometry
        for i, geom in enumerate(geometry):
            time = times[i]
            # Check if we have a point and wrap in a list if so
            if isinstance(geom, Point):
                geom = [geom]
                time = [time]
            # Loop over each point in the geometry
            for j, part in enumerate(geom):
                xy = np.array(part.coords[0])
                rows += f'{int(xy[0]/resolution)} {int(xy[1]/resolution)} {time[j]}\n'
                n_rows += 1
        file = QuicFire.fmt_4.substitute(
            n_rows=n_rows, rows=rows, elapsed_time=round(elapsed_time, 2))

    # Handle the case where we have mixed geometry types
    else:
        raise ExportError(ExportError.incompatible_line_types)

    # Remove blank lines from file
    file = '\n'.join([line for line in file.split('\n') if line.strip()])

    return file
