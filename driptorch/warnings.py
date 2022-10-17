
class CrewSizeWarning(UserWarning):
    base_msg = 'Ignition crew size for this firing technique should be ' \
        'exactly'
    only_using_one = f'{base_msg} 1. Only the first igniter in the crew will be used'
    only_using_two = f'{base_msg} 2. Only the first two igniters in the crew will be used'
    cloning_first = f'{base_msg} 2. The first igniter was dulicated to increase ' \
        'the crew to the minimum required size.'


class IgniterWarning(UserWarning):
    velocity_warning = 'Igniter velocity is above reasonable rates'