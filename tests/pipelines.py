# External Imports
from shapely import affinity
from shapely.geometry.polygon import Polygon
import numpy as np
import os.path as path

# Internal Imports
import driptorch as dt
from driptorch.io import *
from tests.resources import testgeoms


def generate_simulations(
    unit_bounds: dict,
    front_buffer: int,
    back_buffer: int,
    wind_direction: float,
    ignitor_speed: float,
    ignitor_rate: float,
    number_ignitors: float,
    offset:float,
    ignitor_spacing: float = None,
    ignitor_depth: float = None,
    heat_depth: float = None,
    **kwargs
):

    
    burn_unit = dt.BurnUnit.from_json(unit_bounds, wind_direction=wind_direction)
    firing_area = burn_unit.buffer_control_line(front_buffer)
    firing_area = firing_area.buffer_downwind(back_buffer)
    blackline_area = burn_unit.difference(firing_area)
    domain = burn_unit.copy()
    lower_left = domain.get_bounds().min(axis=0)

    dash_igniter = dt.Igniter(ignitor_speed, rate=ignitor_rate)
    point_crew = dt.IgnitionCrew.clone_igniter(dash_igniter, number_ignitors)

    # Inferno Technique
    inferno_technique = dt.firing.inferno(firing_area)
    inferno_pattern = inferno_technique.generate_pattern()
    trans_geoms = []
    for geom in inferno_pattern.geometry:
        trans_geoms.append(affinity.translate(
            geom, -lower_left[0], -lower_left[1]))
    inferno_pattern_geometry_rect = trans_geoms

    # Ring Technique
    ring_technique = dt.firing.Ring(firing_area, point_crew)
    ring_pattern = ring_technique.generate_pattern(offset)
    trans_geoms = []
    for geom in ring_pattern.geometry:
        trans_geoms.append(affinity.translate(
            geom, -lower_left[0], -lower_left[1]))
    ring_pattern_geometry_rect = trans_geoms

    # Head Technique
    head_technique = dt.firing.head(firing_area,point_crew)
    head_pattern = head_technique.generate_pattern(offset)
    trans_geoms = []
    for geom in head_pattern.geometry:
        trans_geoms.append(affinity.translate(
            geom, -lower_left[0], -lower_left[1]))
    head_pattern_geometry_rect = trans_geoms

    # Back Technique
    back_technique = dt.firing.back(firing_area,point_crew)
    back_pattern = back_technique.generate_pattern(offset)
    trans_geoms = []
    for geom in back_pattern.geometry:
        trans_geoms.append(affinity.translate(
            geom, -lower_left[0], -lower_left[1]))
    back_pattern_geometry_rect = trans_geoms

    if ignitor_depth and heat_depth:

        # Flank Technique
        flank_technique = dt.firing.flank(firing_area,point_crew)
        flank_pattern = flank_technique.generate_pattern(ignitor_depth,heat_depth)
        trans_geoms = []
        for geom in flank_pattern.geometry:
            trans_geoms.append(affinity.translate(
                geom, -lower_left[0], -lower_left[1]))
        flank_pattern_geometry_rect = trans_geoms

    if ignitor_depth and heat_depth and ignitor_spacing:

        # Strip Technique
        strip_technique = dt.firing.strip(firing_area,point_crew)
        strip_pattern = strip_technique.generate_pattern(ignitor_spacing,ignitor_depth,heat_depth)
        trans_geoms = []
        for geom in strip_pattern.geometry:
            trans_geoms.append(affinity.translate(
                geom, -lower_left[0], -lower_left[1]))
        strip_pattern_geometry_rect = trans_geoms


