
class GeojsonError(Exception):
    read_error = 'Invalid GeoJSON format, that is all we know'


class UnequalIgniterVelocity(Exception):
    unequal_velocities = 'Cannot add igniter to crew due to unequal velocities. ' \
        'You can set `same_velocity=False` in the constructor, ' \
        'however this can raise subsequent errors if an ignition ' \
        'crew with unequal velocity is passed to an internal ignition ' \
        'pattern generation method.'
