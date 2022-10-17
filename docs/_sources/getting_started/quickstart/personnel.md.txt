# Personnel

Ignition personnel can be configured and assembled in an _ignition crew_. For individual igniters, you can specify their velocity in meters/second and the line type of the ignition they produce. 

```python
# Create a few igniters with different line types
fast_line_igniter = dt.Igniter(2)
slow_dot_igniter = dt.Igniter(0.1, gap_legnth=10)
medium_dash_igniter = dt.Igniter(1, dash_length=10)
irregular_dash_igniter = dt.Igniter(1, dash_length=10, gap_length=50)
```

We can allocate these igniters to an ignition crew in various ways. One thing to note is that some firing techniques, such as strip-heading and flanking patterns require that all igniters in an crew walk at the same speed. By default, the `IgnitionCrew` constructor will throw an exception if igniters with unequal velocities are allocated to the crew. If you want to allow for unequal velocity, which could be appropriate in a ring ignition pattern for example, then set `same_velocity=False`. 

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

or create a crew by duplicating an single igniter is to use the `clone_igniter()` alternative contructor.

```python
six_man_crew = dt.IgnitionCrew.clone_igniter(medium_dash_igniter, 6)
```

It is also possible to create other types of igniters, such as drone-base PSD/DAID devices. Just remember that even when you only have a single igniter resource, you still need to add it to an ignition crew to be passes to pattern generation methods.

```python
drone_igniter = dt.Igniter(10, 0.5, rate_units='seconds')
drone_crew = dt.IgnitionCrew.from_list([drone_igniter])
```