# DripTorch

Ignition pattern simulator for prescribed firing technqiues

## Installation

You can install `driptorch` from the Python Package Index with

```
pip install driptorch
```

## Quickstart

### Burn unit and wind direction

A burn unit is the spatial boundary of a firing operation while the wind direction determines the arrangement and timing of the ignition pattern. Everything that happens downstream in DripTorch depends on the unit boundary and the wind direction.

You can create a burn unit in DripTorch by providing a Shapely `Polygon` object to the `BurnUnit` constructor. DripTorch expects the polygon CRS to be in Web Mercator (EPSG: 4326), however you can manually specify the EPSG code with an optional argument; DripTorch will convert the spatial data to the appropriate UTM projection internally.

```python
import driptorch as dt
from shapely.geometry import Polygon

# Create a shapely Polygon object
polygon = Polygon([(-114.44869995117188, 47.088504171925706), (-114.44470882415771, 47.08745225315146), (-114.44342136383057, 47.09066638416644), (-114.44496631622313, 47.09236102969754), (-114.44633960723877, 47.0924194647886), (-114.45281982421875, 47.089205439567344), (-114.45153236389159, 47.08815353464254), (-114.44869995117188, 47.088504171925706)])

# Create a burn unit with a wind direction of 90 degrees
burn_unit = dt.BurnUnit(polygon, 90)

# If your polygon is not projected in 4326 you can specify the EPSG code
burn_unit = dt.BurnUnit(polygon, 90, epsg=<epsg_code>)
```

If your spatial data is formatted in GeoJSON then use the `from_json()` alternative constructor. DripTorch will look through the list of features and extract the first instance of a polygon geometry. A great site to create GeoJSON feature collections is [geojon.io](https://geojson.io).

```python
# Define GeoJSON feature collection
geojson = {
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {},
      "geometry": {
        "type": "Polygon",
        "coordinates": [
          [
            [
              -114.44869995117188,
              47.088504171925706
            ],
            [
              -114.44470882415771,
              47.08745225315146
            ],
            [
              -114.44342136383057,
              47.09066638416644
            ],
            [
              -114.44496631622313,
              47.09236102969754
            ],
            [
              -114.44633960723877,
              47.0924194647886
            ],
            [
              -114.45281982421875,
              47.089205439567344
            ],
            [
              -114.45153236389159,
              47.08815353464254
            ],
            [
              -114.44869995117188,
              47.088504171925706
            ]
          ]
        ]
      }
    }
  ]
}

# Create a burn unit from a GeoJSON feature collection with a wind direction of 217 degrees
burn_unit = dt.BurnUnit.from_json(geojson, 217)
```

### Control line and downwind blackline buffering

You can emmulate a plowline or handline operation by buffering the burn unit.

```python
# Buffer the burn unit to inside a control line of 2 meters
firing_area = burn_unit.buffer_control_line(2)
```

You can also simulate the blackline operation which only buffers the side of the unit that is downwind.

```python
# Create an additional 10 meter buffer in the firing_area object on the downwind side of the unit
firing_area = firing_area.buffer_downwind(10)
```

The difference between the `burn_unit` and `firing_area` can be computed for removing fuels prior to running a fire simulation.

```python
fuel_removal_area = burn_unit.difference(firing_area)
```

Buffering the burn unit to account for the control line and blackline operation is optional. Just remember that the `BurnUnit` instance you pass to the built-in pattern ignition generators (discussed below) determine the where the ignition paths are placed. So, if you create an interior firing area polygon by buffering the original burn unit, what we called `firing_area` above then be sure to pass that polygon to downstream operations in DripTorch.

### Igniters and ignition crews

Ignition personnel can be configured and assembled in an ignition crew. For individual igniters, you can specify their velocity in meters/second and ignition rate in either ignitions/meter or ignitions/second. The line type of the igniter is implicitly defined using the `rate` parameter in the `Igniter` contructor. For example, use an ignition rate of zero for an igniter that produces a continuous line of fire, use positive rate values for point ignitions and negative rate values for dash ignitions. By default, the rate parameter is in units of ignitions/meter. So, if you want your igniter to produce a point ignition every 5 meters then set `rate=1/5`. To specify the rate in ignitions/second, set `rate_units='seconds'`.

```python
# Create a few igniters with different line types
fast_line_igniter = dt.Igniter(3, 0)
slow_dot_igniter = dt.Igniter(0.5, 1/10)
medium_dash_igniter = dt.Igniter(1.8, -1/5)
```

Now we can allocate these igniters to an ignition crew in various ways. One thing to note is that some firing techniques, such as strip-heading and flanking patterns, require that all igniters in an crew walk at the same speed. By default, the `IgnitionCrew` constructor will throw an exception is igniters with unequal velocities are allocated to the crew. If you want to allow for unequal velocity, which could be appropriate in a ring ignition pattern for example, then set `same_velocity=False`.

```python
two_man_crew = dt.IgnitionCrew(same_velocity=False)
two_man_crew.add_igniter(fast_line_igniter)
two_man_crew.add_igniter(medium_dash_igniter)
```

DripTorch provides various way to construct an ignition crew. You can initialize the crew using a list of igniters,

```python
igniter_list = [slow_dot_igniter, fast_line_igniter]
three_man_crew = dt.IgnitionCrew.from_list(igniter_list)
# Throws an exception due to unequal igniter velocities
```

or create a crew by duplicating an single igniter is to use the `clone()` alternative contructor.

```python
six_man_crew = dt.IgnitionCrew.clone(medium_dash_igniter, 6)
```

It is also possible to create other types of igniters, such a Drone-base PSD devices. Just remember that even when you only have a single igniter resource, you still need to add it to an ignition crew to be passes to pattern generator methods.

```python
drone_igniter = dt.Igniter(10, 1, rate_units='seconds')
drone_crew = dt.IgnitionCrew.from_list([drone_igniter])
```

### Firing techniques (pattern generators)

Once your burn unit has been specified and you've allocated your ignition resources, you can simulate various firing techniques using DripTorch pattern generators. Currently, DripTorch supports the following firing techniques:

- Strip-heading fire (strip)
- Flanking fire (flank)
- Ring fire (ring)
- Head fire (head)
- Backing fire (back)

Firing techniques are accesible through the `FiringTechnique` submodule. For exapmle, to get an instance of the stip-heading fire generator use this command.

```python
# Initialize the pattern generator for the strip firing technique
strip = dt.FiringTechniques.strip(firing_area, ignition_crew)
```

All pattern generators have a `generate_pattern()` method, however the arguments may differ between techniques. To generate a pattern for the strip instance we just create, you must specify the spacing (staggering distance between igniters, in meters) and the depth (horizontal distance between igniters, again in meters).

```python
# Generate a strip pattern with 10 meter spacing and 50 meter depth
strip_pattern = strip.generate_pattern(10, 50)
```

Let's setup a ring fire as another example.

```python
# Initialize the pattern generator for the ring firing technique
ring = dt.FiringTechniques.ring(firing_area, ignition_crew)

# Create a rign ignition pattern with a 10 meters offset from the firing area boundary
ring_pattern = rign.generate_pattern(10)
```