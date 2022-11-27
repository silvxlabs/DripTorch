
# DripTorch Unreleased Notes

## New Features

### Cloud-hosted DEM and on-the-fly grid reprojection ([PR #137](https://github.com/silvxlabs/DripTorch/pull/137))

These efforts support our goal to add contour following ignition patterns in version 0.9. The grid extraction and processing happens completely behind the scenes and is automatic. From the user's perspective, all that changes is the additional argument when instantiated a burn unit object; `burn_unit = dt.BurnUnit(use_topo=True)`

### Contour-following strip ignition prototype ([PR #138](https://github.com/silvxlabs/DripTorch/pull/138))

This PR encompasses the prototype code for an algorithm to commpute the geodesic distance transform over a 2.5 dimensional surface representated as a 2 dimensional matrix. 


## Bug fixes

### Incorrect naming of EPSG 4326 ([PR #139](https://github.com/silvxlabs/DripTorch/pull/139))

Somehow we got in the habit of calling EPSG: 4326 'Web Mercator' while it's actually WGS84. We have updated the code and docs to semantically reference 4326 as WGS84.

```{warning}
This is a breaking change for users directly using the `mercator_to_utm` and `to_mercator` methods from the `Projector` class. 
```
