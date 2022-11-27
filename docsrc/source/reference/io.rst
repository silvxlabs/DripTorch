===================
Projections and I/O
===================
.. currentmodule:: driptorch

Spatial projections
-------------------

.. autosummary::
   :toctree: api/

   io.Projector
   io.Projector.forward
   io.Projector.backward
   io.Projector.estimate_utm_epsg
   io.Projector.to_wgs84
   io.Projector.wgs84_to_utm

Importing and exporting
-----------------------

.. autosummary::
   :toctree: api/

   io.read_geojson_polygon
   io.write_geojson
   io.write_quicfire

