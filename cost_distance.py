import numpy as np

# ref: https://pro.arcgis.com/en/pro-app/latest/tool-reference/spatial-analyst/understanding-cost-distance-analysis.htm  # noqa: E501
_MOVES = np.array(
    [
        # 0
        [0, -1],
        # 1
        [-1, -1],
        # 2
        [-1, 0],
        # 3
        [-1, 1],
        # 4
        [0, 1],
        # 5
        [1, 1],
        # 6
        [1, 0],
        # 7
        [1, -1],
    ],
    dtype=np.int8,
)

HEAP_SPEC = [
    ("max_value", np.int64),
    ("levels", np.int8),
    ("min_levels", np.int8),
    ("count", np.int64),
]
HEAP_DT = np.dtype(HEAP_SPEC)


def init_heap_data(capacity: np.int64, max_value: np.int64):
    if capacity < 1:
        raise ValueError("Capacity must be greater than 0")
    if max_value < 1:
        raise ValueError("Max value must be greater than 0")
    # Have to use single element array. Numba throws an error if you try to
    # return a record dtype. Using the array as a wrapper allows the record to
    # be passed around in these functions.
    heap = np.zeros(1, dtype=HEAP_DT)
    heap[0].max_value = max_value
    heap[0].levels = 0
    while 2 ** heap[0].levels < capacity:
        heap[0].levels += 1
    heap[0].min_levels = heap[0].levels
    heap[0].count = 0

    n = 2 ** heap[0].levels
    keys = np.full(2 * n, np.inf, dtype=F64)
    values = np.full(n, -1, dtype=I64)
    crossrefs = np.full(heap[0].max_value + 1, -1, dtype=I64)
    return keys, values, crossrefs, heap



def _sift(keys, heap, i):
    # Get first index in the pair. Pairs always start at uneven indices
    i -= i % 2 == 0
    # sift the minimum value back through the heap
    for _ in range(heap[0].levels, 1, -1):
        # Index into previous level
        iplvl = (i - 1) // 2
        keys[iplvl] = min(keys[i], keys[i + 1])
        i = iplvl - (iplvl % 2 == 0)



def _sift_all(keys, heap):
    # index at start of final level
    ilvl = (1 << heap[0].levels) - 1
    # Length of final level
    n = ilvl + 1
    for i in range(ilvl, ilvl + n, 2):
        _sift(keys, heap, i)



def _resize_levels(keys, values, heap, inc_dec):
    new_levels = heap[0].levels + inc_dec
    n = 1 << new_levels
    # We don't need to resize the crossrefs array
    new_keys = np.full(2 * n, np.inf, dtype=F64)
    new_values = np.full(n, -1, dtype=I64)
    if heap[0].count:
        inew = (1 << new_levels) - 1
        iold = (1 << heap[0].levels) - 1
        n = min(inew, iold) + 1
        new_keys[inew : inew + n] = keys[iold : iold + n]
        new_values[:n] = values[:n]
    keys = new_keys
    values = new_values
    heap[0].levels = new_levels
    _sift_all(keys, heap)
    return keys, values


@nb.jit(
    Tuple((KEYS_TYPE_SIG, VALUES_TYPE_SIG))(*HEAP_STATE_SIG, nb.int64),
    **JIT_KWARGS,
)
def _remove(keys, values, crossrefs, heap, i):
    lvl_start = (1 << heap[0].levels) - 1
    ilast = lvl_start + heap[0].count - 1
    i_val = i - lvl_start
    i_val_last = heap[0].count - 1

    # Get the last value
    value = values[i_val_last]
    # and update the crossref to point to its new location
    crossrefs[value] = i_val
    # Get the value to be removed
    value = values[i_val]
    # and delete its crossref
    crossrefs[value] = -1
    # Swap key to be removed with the last key
    keys[i] = keys[ilast]
    # Swap corresponding values
    values[i_val] = values[i_val_last]
    # Remove the last key since it is now invalid
    keys[ilast] = np.inf

    heap[0].count -= 1
    if (heap[0].levels > heap[0].min_levels) & (
        heap[0].count < (1 << (heap[0].levels - 2))
    ):
        keys, values = _resize_levels(keys, values, heap, -1)
    else:
        _sift(keys, heap, i)
        _sift(keys, heap, ilast)
    return keys, values


@nb.jit(
    HEAP_STATE_SIG(*HEAP_STATE_SIG, nb.float64, nb.int64),
    **JIT_KWARGS,
)
def _simple_push(keys, values, crossrefs, heap, key, value):
    lvl_size = 1 << heap[0].levels

    if heap[0].count >= lvl_size:
        keys, values = _resize_levels(keys, values, heap, 1)
        lvl_size = lvl_size << 1
    i = lvl_size - 1 + heap[0].count
    keys[i] = key
    values[heap[0].count] = value
    crossrefs[value] = heap[0].count
    heap[0].count += 1
    _sift(keys, heap, i)
    return keys, values, crossrefs, heap


@nb.jit(
    nb.types.Tuple((*HEAP_STATE_SIG, nb.int8))(
        *HEAP_STATE_SIG, nb.float64, nb.int64
    ),
    **JIT_KWARGS,
)
def push(keys, values, crossrefs, heap, key, value):
    if not (0 <= value <= heap[0].max_value):
        return keys, values, crossrefs, heap, -1

    lvl_size = 1 << heap[0].levels
    ii = crossrefs[value]
    if ii != -1:
        # Update the key value
        i = lvl_size - 1 + ii
        keys[i] = key
        _sift(keys, heap, i)
        return keys, values, crossrefs, heap, 0

    keys, values, crossrefs, heap = _simple_push(
        keys, values, crossrefs, heap, key, value
    )
    return keys, values, crossrefs, heap, 1


def push_if_lower(keys, values, crossrefs, heap, key, value):
    if not (0 <= value <= heap[0].max_value):
        return keys, values, crossrefs, heap, -1

    icr = crossrefs[value]
    if icr != -1:
        i = (1 << heap[0].levels) - 1 + icr
        if keys[i] > key:
            keys[i] = key
            _sift(keys, heap, i)
            return keys, values, crossrefs, heap, 1
        return keys, values, crossrefs, heap, 0

    keys, values, crossrefs, heap = _simple_push(
        keys, values, crossrefs, heap, key, value
    )
    return keys, values, crossrefs, heap, 1


def pop(keys, values, crossrefs, heap):
    # The minimum key sits at position 1
    i = 1
    # Trace min key through the heap levels
    for lvl in range(1, heap[0].levels):
        if keys[i] <= keys[i + 1]:
            i = (i * 2) + 1
        else:
            i = ((i + 1) * 2) + 1
    # Find it in the last level
    if keys[i] > keys[i + 1]:
        i += 1
    # Get corresponding index into values
    ii = i - ((1 << heap[0].levels) - 1)
    popped_key = keys[i]
    popped_value = values[ii]
    if heap.count:
        keys, values = _remove(keys, values, crossrefs, heap, i)
    return keys, values, crossrefs, heap, popped_key, popped_value

def _get_strides(shape):
    # Get strides for given nd array shape. Assumes c style strides
    # NOTE: output must have a standardized type because windows has different
    # default int types from linux.
    values = np.empty(len(shape), dtype=I64)
    values[0] = 1
    values[1:] = shape[::-1][:-1]
    strides = _mult_accumulate(values)[::-1]
    return 

def _ravel_indices(indices, shape):
    # Convert nd c-strided indices to flat indices
    strides = _get_strides(shape)
    flat_indices = [np.sum(strides * idx) for idx in indices]
    return np.array(flat_indices, dtype= np.int64)


def _cost_distance_analysis_core(
    flat_costs,
    flat_sources,
    flat_moves,
    move_lengths,
    shape,
    sources_null_value,
    # Elevation args
    flat_elev,
    elevation_null_value,
    use_elevation,
):
    size: np.int64 = flat_costs.size
    # The cumulative cost distance to every pixel from the sources
    flat_cost_distance = np.full(size, np.inf, dtype=np.int64)
    # traceback values:
    #    -1: source
    #    -2: not reached, barrier
    #    0-7: index into moves array
    flat_traceback = np.full(size, TRACEBACK_NOT_REACHED, dtype=np.int8)
    # allocation values:
    #    sources_null_value: not reached, barrier
    #    other: value from sources array
    flat_allocation = np.full(size, sources_null_value, dtype=np.int64)
    

    cost: np.float64
    new_cost: np.float64
    cumcost: np.float64
    new_cumcost: np.float64
    move_length: np.float64
    dz: np.float64
    ev: np.float64
    new_ev: np.float64
    index: np.int64
    index: np.int64
    new_index: np.int64
    src: np.int64
    index2d = np.zeros(2, dtype= np.int64)
    i: np.int64
    it: np.int64
    move: int8[:]
    is_at_edge: bool
    bad_move: bool
    left: bool
    right: bool
    top: bool
    bottom: bool
    costs_shape_m1 = np.zeros(2, dtype= np.int64)
    strides: np.int64[:] = _get_strides(shape)
    # 1.5 * size
    maxiter: np.int64 = size + (size // 2)

    # A heap for storing pixels and their accumulated cost as the algorithm
    # explores the cost landscape.
    heap_keys, heap_values, heap_xrefs, heap_state = init_heap_data(
        128, size - 1
    )

    costs_shape_m1[0] = shape[0] - 1
    costs_shape_m1[1] = shape[1] - 1

    for i in range(flat_sources.size):
        src = flat_sources[i]
        if src != sources_null_value:
            flat_traceback[i] = -1
            flat_allocation[i] = src
            heap_keys, heap_values, heap_xrefs, heap_state, _ = push(
                heap_keys, heap_values, heap_xrefs, heap_state, 0, i
            )

    # Main loop for Dijkstra's algorithm
    # The frontier heap contains the current known costs to pixels discovered
    # so far. When a pixel and its cumulative cost are popped, we have found
    # the minimum cost path to it and can store the cumulative cost in our
    # output array. We then add/update the cost to that pixel's neighborhood.
    # If a neighbor has already been popped before, we ignore it. The
    # cumulative cost is used as the priority in the heap. At the start, only
    # the sources are on the heap.
    #
    # ref: https://pro.arcgis.com/en/pro-app/latest/tool-reference/spatial-analyst/how-the-cost-distance-tools-work.htm  # noqa: E501
    # ref: https://en.wikipedia.org/wiki/Dijkstra%27s_algorithm
    for it in range(maxiter):
        if heap_state[0].count == 0:
            break

        # Get the cumulative cost at the current pixel of interest and get the
        # flat index of the current pixel and the source that led to it
        heap_keys, heap_values, heap_xrefs, heap_state, cumcost, index = pop(
            heap_keys, heap_values, heap_xrefs, heap_state
        )
        src = flat_allocation[index]
        # We have now found the minimum cost to this pixel so store it
        flat_cost_distance[index] = cumcost

        # Convert to 2d index for bounds checking
        index2d[0] = (index // strides[0]) % shape[0]
        index2d[1] = (index // strides[1]) % shape[1]
        # Compare against the bounds to see if we are at any edges
        top = index2d[0] == 0
        bottom = index2d[0] == costs_shape_m1[0]
        left = index2d[1] == 0
        right = index2d[1] == costs_shape_m1[1]
        is_at_edge = top or bottom or left or right

        # Look at neighborhood
        for i in range(8):
            if is_at_edge:
                move = _MOVES[i]
                bad_move = (
                    (top and move[0] < 0)
                    or (bottom and move[0] > 0)
                    or (left and move[1] < 0)
                    or (right and move[1] > 0)
                )
                if bad_move:
                    continue
            new_index = index + flat_moves[i]
            move_length = move_lengths[i]
            # If a value is already stored in this pixel, we have found an
            # optimal path to it previously and can skip it.
            if flat_cost_distance[new_index] != np.inf:
                continue
            cost = flat_costs[index]
            new_cost = flat_costs[new_index]
            # If the cost at this point is a barrier, skip
            # TODO: may be able consolidate into a single sentinel check if
            #       input data is standardized
            if new_cost < 0 or new_cost == np.inf or np.isnan(new_cost):
                continue

            if use_elevation:
                ev = flat_elev[index]
                new_ev = flat_elev[new_index]
                if new_ev == elevation_null_value:
                    continue
                dz = new_ev - ev
                move_length = np.sqrt(move_length + (dz * dz))

            new_cumcost = cumcost + (move_length * 0.5 * (cost + new_cost))
            if new_cumcost != np.inf:
                (
                    heap_keys,
                    heap_values,
                    heap_xrefs,
                    heap_state,
                    flag,
                ) = push_if_lower(
                    heap_keys,
                    heap_values,
                    heap_xrefs,
                    heap_state,
                    new_cumcost,
                    new_index,
                )
                if flag > 0:
                    flat_traceback[new_index] = i
                    flat_allocation[new_index] = src
    return flat_cost_distance, flat_traceback, flat_allocation


def cost_distance_analysis_numpy(
    costs,
    sources,
    sources_null_value,
    elevation=None,
    elevation_null_value=0,
    scaling=1.0,
):
    """
    Calculate accumulated cost distance, traceback, and allocation.
    This function uses Dijkstra's algorithm to compute the many-sources
    shortest-paths solution for a given cost surface. Valid moves are from a
    given pixel to its 8 nearest neighbors. This produces 3 2D arrays. The
    first is the accumulated cost distance, which contains the
    distance-weighted accumulated minimum cost to each pixel. The cost to move
    from one pixel to the next is ``length * mean(costs[i], costs[i+1])``,
    where ``length`` is 1 for horizontal and vertical moves and ``sqrt(2)`` for
    diagonal moves. The provided scaling factor informs the actual distance
    scaling to use. Source locations have a cost of 0. If `elevation` is
    provided, the length calculation incorporates the elevation data to make
    the algorithm 3D aware.
    The second array contains the traceback values for the solution. At each
    pixel, the stored value indicates the neighbor to move to in order to get
    closer to the cost-relative nearest source. The numbering is as follows:
        5  6  7
        4  X  0
        3  2  1
    Here, X indicates the current pixel and the numbers are the neighbor
    pixel positions. 0 indicates the neighbor immediately to the right and
    6 indicates the neighbor immediately above. In terms of rows and columns,
    these are the neighbor one column over and one row above, respectively. a
    value of -1 indicates that the current pixel is a source pixel and -2
    indicates that the pixel was not traversed (no data or a barrier).
    The third array contians the source allocation for each pixel. Each pixel
    is labeled based on the source location that is closest in terms of cost
    distance. The label is the value stored in the sources array at the
    corresponding source location.
    Parameters
    ----------
    costs : 2D ndarray
        A 2D array representing a cost surface.
    sources : 2D np.int64 ndarray
        An array of sources. The values at each valid location, as determined
        using `sources_null_value`, are used for the allocation output.
    sources_null_value: int
        The value in `sources` that indicates a null value.
    elevation : 2D ndarray, optional
        An array of elevation values. Same shape as `costs`. If provided, the
        elevation is used when determining the move length between pixels.
    elevation_null_value : scalar, optional
        The null value for `elevation` data. Default is 0.
    scaling : scalar or 1D sequence, optional
        The scaling to use in each direction. For a grid with 30m scale, this
        would be 30. Default is 1.
    Returns
    -------
    cost_distance : 2D ndarray
        The accumulated cost distance solution. This is the same shape as the
        `costs` input array.
    traceback : 2D ndarray
        The traceback result. This is the same shape as the `costs` input
        array.
    allocation : 2D ndarray
        The allocation result. This is the same shape as the `costs` input
        array.
    """
    costs = np.asarray(costs)
    
    sources = np.asarray(sources).astype(np.int64)
    shape = costs.shape
    if sources.shape != shape:
        raise ValueError("Costs and sources array shapes must match")

    if elevation is None:
        elevation = np.array([])
        elevation_null_value = 0
        use_elevation = False
    else:
        elevation = np.asarray(elevation)
        if elevation.shape != shape:
            raise ValueError(
                "Elevation must have the same shape as costs array"
            )
        use_elevation = True

    if is_scalar(scaling):
        scaling = np.array([scaling for _ in shape], dtype=F64)
    elif isinstance(scaling, (np.ndarray, list, tuple)):
        scaling = np.asarray(scaling).astype(F64)
        if scaling.size != len(shape) or len(scaling.shape) != 1:
            raise ValueError(f"Invalid scaling shape: {scaling.shape}")
    if any(scaling <= 0):
        raise ValueError("Scaling values must be greater than 0")

    flat_costs = costs.ravel()
    flat_elev = elevation.ravel()
    flat_sources = sources.ravel()
    flat_moves = _ravel_indices(_MOVES, shape)
    # Compute squared move lengths
    move_lengths = np.sum((scaling * _MOVES) ** 2, axis=1).astype(F64)
    if not use_elevation:
        # No elevation data provided so convert to actual euclidean lengths
        for i in range(move_lengths.size):
            move_lengths[i] = np.sqrt(move_lengths[i])

    (
        flat_cost_distance,
        flat_traceback,
        flat_allocation,
    ) = _cost_distance_analysis_core(
        flat_costs,
        flat_sources,
        flat_moves,
        move_lengths,
        shape,
        sources_null_value,
        # Optional elevation args
        flat_elev,
        elevation_null_value,
        use_elevation,
    )
    cost_distance = flat_cost_distance.reshape(shape)
    traceback = flat_traceback.reshape(shape)
    allocation = flat_allocation.reshape(shape)
    return cost_distance, traceback, allocation