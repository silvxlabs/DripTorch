![driptorch-logo](https://github.com/teamholtz/DripTorch/blob/main/img/logo.jpg?raw=true)

Ignition pattern simulator for prescribed firing technqiues

## Installation

You can install DripTorch from the SilvX Anaconda channel. First create a Conda environment with Python version 3.10 or later.

```shell
$(base) conda create -n driptorch python=3.10
```

Activate the environment and install DripTorch

```shell
$(base) conda activate driptorch
$(driptorch) conda install driptorch -c silvx
```

## Quickstart

### Burn unit and wind direction

A burn unit is the spatial boundary of a firing operation while the wind direction determines the arrangement and timing of the ignition pattern. Everything that happens downstream in DripTorch depends on the unit boundary and the wind direction.

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

# Create a burn unit with a wind direction of 90 degrees
burn_unit = dt.BurnUnit(polygon, 90)

# If your polygon is already in UTM, then you'll need to specifiy the UTM EPSG code in the contructor
burn_unit = dt.BurnUnit(polygon, 90, utm_epsg=32611)
```

If your spatial data is formatted in GeoJSON then use the `from_json()` alternative constructor. DripTorch will look through the list of features and extract the first instance of a polygon geometry. [geojon.io](https://geojson.io) is a great web application for creating GeoJSONs. The GeoJSON doesn't have to be a Feature Collection. DripTorch will accept Feature types as well.

```python
# Define GeoJSON feature collection
geojson = {"type":"FeatureCollection","features":[{"type":"Feature","properties":{},"geometry":{"type":"Polygon","coordinates":[[[-114.44869995117188,47.088504171925706],[-114.44470882415771,47.08745225315146],[-114.44342136383057,47.09066638416644],[-114.44496631622313,47.09236102969754],[-114.44633960723877,47.0924194647886],[-114.45281982421875,47.089205439567344],[-114.45153236389159,47.08815353464254],[-114.44869995117188,47.088504171925706]]]}}]}


# Create a burn unit from a GeoJSON feature collection with a wind direction of 217 degrees
burn_unit = dt.BurnUnit.from_json(geojson, 217)
```

### Control line and downwind blackline buffering

You can emmulate a plowline or handline operation by buffering the burn unit.

```python
# Buffer the burn unit to inside a control line of 2 meters
firing_area = burn_unit.buffer_control_line(2)
```

You can also simulate the blackline operation which only buffers the downwind side of the unit.

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
geojson = fuel_removal_area.to_json()
```

> Note: DripTorch caches the source EPSG code when loading a geometry, whether you specified it manual or left it as the default (4326). Everything under the hood operates in UTM, however when you export to GeoJSON DripTorch will always convert the coordinates to 4326. For other types of exports, such as exports to fire model ignition files, the projection will stay in UTM.

Buffering the burn unit to account for the control line and blackline operation is optional. Just remember that the `BurnUnit` instance you pass to the built-in pattern ignition generators (discussed below) determines the where the ignition paths are placed. So, if you create an interior firing area polygon by buffering the original burn unit, what we called `firing_area` above, then be sure to pass that polygon to downstream operations in DripTorch.

### Igniters and ignition crews

Ignition personnel can be configured and assembled in an _ignition crew_. For individual igniters, you can specify their velocity in meters/second and ignition rate in either ignitions/meter or ignitions/second. The line type of the igniter is implicitly defined using the `rate` parameter in the `Igniter` constructor. For example, use an ignition rate of zero for an igniter that produces a continuous line of fire, use a positive rate value for point ignitions and a negative rate for dash ignitions. By default, the rate parameter is in units of ignitions/meter. If you want your igniter to produce a point ignition every 5 meters then set `rate=1/5`. To specify the rate in ignitions/second, set `rate_units='seconds'`.

```python
# Create a few igniters with different line types
fast_line_igniter = dt.Igniter(3, 0)
slow_dot_igniter = dt.Igniter(0.5, 1/10)
medium_dash_igniter = dt.Igniter(1.8, -1/5)
```

We can allocate these igniters to an ignition crew in various ways. One thing to note is that some firing techniques, such as strip-heading and flanking patterns require that all igniters in an crew walk at the same speed. By default, the `IgnitionCrew` constructor will throw an exception if igniters with unequal velocities are allocated to the crew. If you want to allow for unequal velocity, which could be appropriate in a ring ignition pattern for example, then set `same_velocity=False`. Furthermore, some fire models may require different ignition input formats for different line typs. There is another optional toggle to restrict or allow different line types: `same_rate=False`.

```python
two_man_crew = dt.IgnitionCrew(same_velocity=False, same_rate=False)
two_man_crew.add_igniter(fast_line_igniter)
two_man_crew.add_igniter(medium_dash_igniter)
```

DripTorch provides various way to construct an ignition crew. You can initialize the crew using a list of igniters,

```python
igniter_list = [slow_dot_igniter, fast_line_igniter]
three_man_crew = dt.IgnitionCrew.from_list(igniter_list)
# Throws an exception due to unequal igniter velocities
```

or create a crew by duplicating an single igniter is to use the `clone_igniter()` alternative contructor.

```python
six_man_crew = dt.IgnitionCrew.clone(medium_dash_igniter, 6)
```

It is also possible to create other types of igniters, such as drone-base PSD/DAID devices. Just remember that even when you only have a single igniter resource, you still need to add it to an ignition crew to be passes to pattern generation methods.

```python
drone_igniter = dt.Igniter(10, 0.5, rate_units='seconds')
drone_crew = dt.IgnitionCrew.from_list([drone_igniter])
```

### Firing techniques (pattern generators)

Once your burn unit has been specified and you've allocated your ignition resources, you can simulate various firing techniques using DripTorch pattern generators. Currently, DripTorch supports the following firing techniques:

- Strip-heading fire - `strip(spacing, depth)`
- Flanking fire - `flank(depth)`
- Ring fire - `ring(offset)`
- Head fire - `head(offset)`
- Backing fire - `back(offset)`

Firing techniques are accesible through the `FiringTechnique` submodule. For exapmle, to get an instance of the strip-heading fire generator use the following command.

```python
# Initialize the pattern generator for the strip firing technique
strip = dt.FiringTechniques.strip(firing_area, ignition_crew)
```

All pattern generators have a `generate_pattern()` method, however the arguments may differ between techniques. To generate a pattern for the strip instance we just created, you must specify the spacing (staggering distance between igniters, in meters) and the depth (horizontal distance between igniters, again in meters).

```python
# Generate a strip pattern with 10 meter spacing and 50 meter depth
strip_pattern = strip.generate_pattern(10, 50)
```

Certain firing technique require a specific number of igniters in the ignition crew. For instance, the ring fire generator requires exactly two igniters. In this case, if you pass an ignition crew with one igniter, the constructor will warn you and clone the first igniter. If you supply a crew with three igniters, you will see a warning saying that DripTorch will only use the first two igniters in the crew.

```python
# Initialize the pattern generator for the ring firing technique
ring = dt.FiringTechniques.ring(firing_area, three_man_crew)
# You'll see a warning that only the first two igniters will be used

# Create a rign ignition pattern with a 10 meters offset from the firing area boundary
ring_pattern = ring.generate_pattern(10)
```

Once you have an ignition pattern you can view it in an interactive map and export the pattern to a fire simulator input file.

### Mapping

Thanks to [Folium](https://python-visualization.github.io/folium/), you can map burn unit boundaries and animated ignition paths. DripTorch has some convenience methods to make creating maps super simple. The mapping class takes the burn unit and you can optionally add the interior firing area and blackline area if you created those. Finally, adding the pattern will animate the ignition paths.

```python
# Initialize a map with the burn unit
map = dt.Map(burn_unit)

# Optionally add the firing and blackline areas
map.add_firing_area(firing_area)
map.add_blackline_area(blackline_area)

# Add the timed ignition pattern
map.add_pattern(strip_pattern)

# Show the map interactivly in a notebook
map.show()
```

![Alt text](https://github.com/teamholtz/DripTorch/blob/main/img/map-strip.jpg?raw=true)

### Exports

If you want to actually use your ignition pattern to set something on fire (at least in a simulator) then use one of the export methods in the pattern instance to write the ignition paths in a model-specific format. Currently, DripTorch only supports QUIC-fire, but other formats are on our roadmap.

```python
# Write the pattern to a QUIC-Fire ignition file
pattern.to_quicfire(filename='qf_ignition_file.dat')

# If you don't specify a file name then the method will return a str containing the file contents
qf_ignition_str = pattern.to_quicfire()
```
