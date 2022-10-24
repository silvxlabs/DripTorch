# Burn unit

A burn unit is the spatial boundary of a firing operation while the firing direction determines the arrangement and timing of the ignition pattern. Everything that happens downstream in DripTorch depends on the unit boundary and the firing direction.

You can create a burn unit in DripTorch by providing a Shapely `Polygon` object to the `BurnUnit` constructor. DripTorch expects the polygon CRS to be Web Mercator (EPSG: 4326). You can use the following function to convert any Shapely geometry or GeoJSON dictionary from a specific EPSG code to 4326.

```python
import driptorch as dt

# Reproject a shapely polygon to 4326
polygon_wm = dt.Projector.to_web_mercator(polygon, 5070)

# Reproject a GeoJSON feature to 4326 (This won't work on Feature Collections, first you need to extract a feature from the feature list)
feature_wm = dt.Projector.to_web_mercator(feature, 5070)
```

Internally, DripTorch will convert the 4326-projected spatial data to the appropriate UTM projection. The UTM EPSG code will be passed down to child objects of the burn unit and used to project the data back to 4326 when exporting.

```python
from shapely.geometry import Polygon

# Create a shapely Polygon object
polygon = Polygon([(-114.44869995117188, 47.088504171925706), (-114.44470882415771, 47.08745225315146), (-114.44342136383057, 47.09066638416644), (-114.44496631622313, 47.09236102969754), (-114.44633960723877, 47.0924194647886), (-114.45281982421875, 47.089205439567344), (-114.45153236389159, 47.08815353464254), (-114.44869995117188, 47.088504171925706)])

# Create a burn unit with a firing direction of 90 degrees
burn_unit = dt.BurnUnit(polygon, 90)

# If your polygon is already in UTM, then you'll need to specifiy the UTM EPSG code in the contructor
burn_unit = dt.BurnUnit(polygon, 90, utm_epsg=32611)
```

If your spatial data is formatted in GeoJSON then use the `from_json()` alternative constructor. DripTorch will look through the list of features and extract the first instance of a polygon geometry. [geojon.io](https://geojson.io) is a great web application for creating GeoJSONs. The GeoJSON doesn't have to be a Feature Collection. DripTorch will accept Feature types as well.

```python
# Define GeoJSON feature collection
geojson = {"type":"FeatureCollection","features":[{"type":"Feature","properties":{},"geometry":{"type":"Polygon","coordinates":[[[-114.44869995117188,47.088504171925706],[-114.44470882415771,47.08745225315146],[-114.44342136383057,47.09066638416644],[-114.44496631622313,47.09236102969754],[-114.44633960723877,47.0924194647886],[-114.45281982421875,47.089205439567344],[-114.45153236389159,47.08815353464254],[-114.44869995117188,47.088504171925706]]]}}]}


# Create a burn unit from a GeoJSON feature collection with a firing direction of 217 degrees
burn_unit = dt.BurnUnit.from_json(geojson, 217)
```

## Blacklining

You can emmulate a plowline or handline operation by buffering the burn unit.

```python
# Buffer the burn unit to inside a control line of 2 meters
firing_area = burn_unit.buffer_control_line(2)
```

You can also simulate the blackline operation which only buffers the downfiring side of the unit.

```python
# Create an additional 10 meter buffer in the firing_area object on the downwind side of the unit
firing_area = firing_area.buffer_downwind(10)
```

The difference between the `burn_unit` and `firing_area` can be computed for removing fuels prior to running a fire simulation.

```python
fuel_removal_area = burn_unit.difference(firing_area)
```

And you can write the `BurnUnit` object back to GeoJSON for use in other applications.

```python
# Write a GeoJSON in the default projection (EPSG: 4326)
geojson = fuel_removal_area.to_json()

# Write a GeoJSON projected in Albers Equal Area Conic (EPSG: 5070)
geojson = burn_unit.to_json(dst_epsg=5070)
```

```{note}
DripTorch caches the source EPSG code when loading a geometry, whether you specified it manual or left it as the default (4326). Everything under the hood operates in UTM, however when you export to GeoJSON DripTorch will always convert the coordinates to 4326. For other types of exports, such as exports to fire model ignition files, the projection will stay in UTM if you don't specify a destination CRS.
```

Buffering the burn unit to account for the control line and blackline operation is optional. Just remember that the `BurnUnit` instance you pass to the built-in pattern ignition generators (discussed below) determines the where the ignition paths are clipped. So, if you create an interior firing area polygon by buffering the original burn unit, what we called `firing_area` above, be sure to pass that polygon to downstream operations in DripTorch if you don't want ignitions in your control line or blackline area.
