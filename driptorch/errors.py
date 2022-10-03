
class GeojsonError(Exception):
    read_error = 'Invalid GeoJSON format, that is all we know'


class IgniterError(Exception):
    unequal_velocities = 'Cannot add igniter to crew due to unequal velocities. ' \
        'You can set `same_velocity=False` in the constructor, ' \
        'however this can raise subsequent errors if an ignition ' \
        'crew with unequal velocity is passed to an internal ignition ' \
        'pattern generation method.'
    unequal_rates = 'Cannot add igniter to crew due to unequal rates. ' \
        'You can set `same_rate=False` in the constructor, ' \
        'however this can raise subsequent errors if an ignition ' \
        'crew with unequal rates is passed to a fire module exporter.'


class ExportError(Exception):
    incompatible_line_types = 'QUIC-fire exports can not include ' \
        'Point and LineString/MultiLineString geometry types in the ' \
        'same file. Please reconfigure your ignition crew to have either ' \
        'all point ignitions or line/dash ignitions.'


class EPSGError(Exception):

    non_equivalent = 'EPSG code for input pattern does not match self.epsg'