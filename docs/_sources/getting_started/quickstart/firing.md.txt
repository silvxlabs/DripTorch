# Firing techniques

Once your burn unit has been specified and you've allocated your ignition resources, you can simulate various firing techniques using DripTorch pattern generators. Currently, DripTorch supports the following firing techniques:

- Strip-heading fire - `strip(spacing, depth)`
- Flanking fire - `flank()`
- Ring fire - `ring(offset)`
- Head fire - `head(offset)`
- Backing fire - `back(offset)`

Firing techniques are accesible through the `firing` subpackage. For example, to get an instance of the strip-heading fire generator use the following command.

```python
# Initialize the pattern generator for the strip firing technique
strip = dt.firing.Strip(firing_area, ignition_crew)
```

All pattern generators have a `generate_pattern()` method, however the arguments may differ between techniques. To generate a pattern for the strip instance we just created, you must specify the spacing (staggering distance between igniters, in meters) and the depth (horizontal distance between igniters, again in meters).

```python
# Generate a strip pattern with 10 meter spacing and 50 meter depth
strip_pattern = strip.generate_pattern(10, 50)
```

For strip and flank techniques you can specify the depth between heats with the `heat_depth` argument.

```python
# Generate a flank pattern with 40 meter depth between igniters and 80 meter depth between heats
flank_pattern = flank.generate_pattern(depth=40, heat_depth=80)
```

Additionally, in the flank technique, if you don't specify an igniter depth, the depth is automatically calcuated such that the igniters are equally spaced across the unit in a single heat.

```python
# Generate a single-heat flank patter
flank_pattern = flank.generate_pattern()
```

Certain firing technique require a specific number of igniters in the ignition crew. For instance, the ring fire generator requires exactly two igniters. In this case, if you pass an ignition crew with one igniter, the constructor will warn you that its going to clone the first igniter. If you supply a crew with three igniters, you will see a warning saying that DripTorch will only use the first two igniters in the crew.

```python
# Initialize the pattern generator for the ring firing technique
ring = dt.firing.ring(firing_area, three_man_crew)
# You'll see a warning that only the first two igniters will be used

# Create a rign ignition pattern with a 10 meters offset from the firing area boundary
ring_pattern = ring.generate_pattern(10)
```

Once you have an ignition pattern you can view it in an interactive map and export the pattern to a fire simulator input file.