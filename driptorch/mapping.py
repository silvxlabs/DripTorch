"""
Folium map wrapper for easy burn unit and animated pattern mapping
"""

# Internal imports
from .pattern import Pattern
from .unit import BurnUnit

# External imports
import folium
from folium import plugins


class Map:
    """Convinience class for plotting spatio-temporal ignition patterns with Folium

    Parameters
    ----------
    burn_unit : BurnUnit
        Burn unit boundary
   """

    def __init__(self, burn_unit: BurnUnit):
        """Constructor

        Args:
            burn_unit (BurnUnit): Burn unit boundary
        """

        # Configure the folium map object
        self.map = folium.Map(
            location=[0, 0],
            tiles=None
        )

        # Add the basemaps
        self._add_tile_layers()

        # Store the burn unit geojson. We'll add to the map later since
        # we want it plotted on the top
        self.unit_geojson = burn_unit.to_json(
            style={
                'fillColor': '#e8eb34',
                'color': '#0000ff',
                'fillOpacity': 0.0,
                'weight': 4
            }
        )

    def _add_tile_layers(self):
        """Helper method for adding imagery, terrain and street tiles to the map
        """

        # Imagery
        folium.TileLayer(
            tiles='https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/tile/{z}/{y}/{x}',
            attr='Tiles courtesy of the <a href="https://usgs.gov/">U.S. Geological Survey</a>',
            name='Imagery',
        ).add_to(self.map)

        # Hybrid (imagery + contours)
        folium.TileLayer(
            tiles='https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryTopo/MapServer/tile/{z}/{y}/{x}',
            attr='Tiles courtesy of the <a href="https://usgs.gov/">U.S. Geological Survey</a>',
            name='Contours'
        ).add_to(self.map)

        # OpenStreetMap
        folium.TileLayer('openstreetmap', name='Street').add_to(self.map)

    def add_firing_area(self, firing_area: BurnUnit):
        """Add the interior firing area to the map as a yellow polygon

        Parameters
        ----------
        firing_area : BurnUnit
            Interior firing area
        """

        # Write to GeoJSON and style
        geojson = firing_area.to_json(
            style={
                'fillColor': '#ffff00',
                'color': '#ffff00',
                'fillOpacity': 0.1
            }
        )

        # Add it to the folium map
        folium.GeoJson(
            data=geojson,
            style_function=Map.styling,
            name='Firing Area'
        ).add_to(self.map)

    def add_blackline_area(self, blackline_area: BurnUnit):
        """Add the blackline area to the map as a black polygon

        Parameters
        ----------
        blackline_area : BurnUnit
            Blackline area (difference between the burn unit and firing area)
        """

        # Write to GeoJSON and style
        geojson = blackline_area.to_json(
            style={
                'fillColor': '#000000',
                'color': '#000000',
                'fillOpacity': 0.5,
                'weight': 0
            }
        )

        # Add it to the map
        folium.GeoJson(
            data=geojson,
            style_function=Map.styling,
            name='Blackline Area',
        ).add_to(self.map)

    def add_pattern(self, pattern: Pattern):
        """Add the pattern to the map as an animated timedstamped
        GeoJSON. Lines, dashes and dots are red.

        Parameters
        ----------
        pattern : Pattern
            Ignition pattern
        """

        # Add the pattern to the map
        plugins.TimestampedGeoJson(
            pattern.to_json(),
            transition_time=10,
            add_last_point=False,
            period='PT1S'
        ).add_to(self.map)

    def show(self) -> folium.Map:
        """Method to show the map in a notebook

        Returns
        -------
        folium.Map
            Folium map object
        """

        # Add the burn unit boundary to the map
        unit_layer = folium.GeoJson(
            data=self.unit_geojson,
            style_function=Map.styling,
            name='Burn Unit',
        ).add_to(self.map)

        # Fit the map to the burn unit
        self.map.fit_bounds(unit_layer.get_bounds())

        # Add the layer control button
        folium.LayerControl().add_to(self.map)

        return self.map

    @staticmethod
    def styling(feature: dict):
        """Helper method for parsing styles from the GeoJSON features

        Parameters
        ----------
        feature : dict
            GeoJSON feature

        Returns
        -------
        dict
            Style dictionary
        """
        return {
            'fillColor': feature['properties']['fillColor'],
            'color': feature['properties']['color'],
            'weight': feature['properties'].get('weight', 2),
            'fillOpacity': feature['properties'].get('fillOpacity', 0.1)
        }
