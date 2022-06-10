# DripTorch

Ignition pattern simulator for prescribed firing technqiues

# Installation

You can install `driptorch` from the Python Package Index with

```
pip install driptorch
```

# Quickstart

## Burn unit and wind direction

A burn unit is the spatial boundary of a firing operation while the wind direction determines the arrangement and timing of the ignition pattern. Everything that happens downstream in DripTorch depends on the unit boundary and the wind direction.

You can create a burn unit in DripTorch by providing a Shapely `Polygon` object to the `BurnUnit` constructor. DripTorch expects the polygon CRS to be in Web Mercator (EPSG: 4326), however you can manually specify the EPSG code with an optional argument; DripTorch will convert the spatial data to the appropriate UTM projection internally.

```python
import driptorch as dt

# Create a burn unit with a wind direction of 90 degrees
burn_unit = dt.BurnUnit(polygon, 90)

# If your polygon is not projected in 4326 you can specify the EPSG code
burn_unit = dt.BurnUnit(polygon, 90, epsg=3856)
```

If your spatial data is formatted in GeoJSON then use the `from_json()` alternative constructor. A great site to create GeoJSON feature collections is [geojon.io](https://geojson.io).

```python
# Create a burn unit from a GeoJSON feature collection and specify a wind direction of 90 degrees
burn_unit = dt.BurnUnit.from_json(<geojson>, 90, epsg=4326)
```

### Control line and downwind blackline buffering

You can emmulate a plowline or handline operation by buffering the burn unit.

```python
# Buffer the burn unit to inside a control line of 2 meters
firing_area = burn_unit.buffer_control_line(2)
```

You can also simulate the blackline operation which only buffers the side of the unit that is downwind.

```python
# Create an additional buffer in the firing_area object on the downwind side of the unit
firing_area = firing_area.buffer_downwind(10)
```

The difference between the `burn_unit` and `firing_area` can be computed for removing fuels prior to running a fire simulation.

```python
fuel_removal_area = burn_unit.difference(firing_area)
```

## Igniters and ignition crews

```python
fast_line_igniter = dt.Igniter(3, 0)
slow_dot_igniter = dt.Igniter(0.5, 10)
medium_dash_igniter = dt.Igniter(1.8, -5)
```

```python
two_man_crew = dt.IgnitionCrew(same_velocity=False)
two_man_crew.add_igniter(fast_line_igniter)
two_man_crew.add_igniter(medium_dash_igniter)
```

```python
three_man_crew = dt.IgnitionCrew.from_list([slow_dot_igniter, fast_line_igniter])
```

```python
six_man_crew = dt.IgnitionCrew.clone(medium_dash_igniter, 6)
```
