""" Contains definitions for BMV2 VMR classes."""

from collections import namedtuple

from bitstring import Bits
from p4t.simple.vmr import check_lengths_match


class BmvVMREntry(namedtuple(
        'BmvVMREntry',
        ['table_name', 'match_key', 'action_name', 'runtime_data', 'options']
)):
    """ BMV2 VMR entry.

    This is the tuple of arguments to be supplied to `bm_mt_add_entry` function.

    Attributes:
        table_name: The name of the table to which this VMR is for.
        match_key: The list of BmMatchParam instances specifying the value-mask.
        action_name: The name of the action to execute
        runtime_data: List of action parameters bytes.
        options: Entry options.
   """

    __slots__ = ()

    @staticmethod
    def isdefault():
        """Return whether this is a default entry (see VMRDefaultEntry)."""
        return False


class BmvVMRDefaultEntry(namedtuple(
        'BmvVMRDefaultEntry',
        ['table_name', 'action_name', 'runtime_data']
)):

    """ BMV2 default VMR entry.

    This is the tuple of arguments to be supplied to `bm_mt_set_default_action`.

    Attributes:
        table_name: The name of the table to which this VMR is for.
        action_name: The name of the action to execute
        runtime_data: List of action parameters bytes.
    """

    __slots__ = ()

    @staticmethod
    def isdefault():
        """ Return whether this is a default entry (see VMRDefaultEntry)."""
        return True


class BmvVMRAction(object):
    def __init__(self, action, runtime_data):
        self._action = action
        self._runtime_data = runtime_data


def tobytes(value, length):
    """Convert value to bytes.

    Args:
        value: Must be either Bits or bytes or list of bool or int.
        length: The expected bit length of the value.

    """
    if isinstance(value, str):
        return value
    elif isinstance(value, int):
        return (Bits(length % 8) + Bits(int=value, length=length)).bytes
    elif isinstance(value, Bits):
        check_lengths_match(length, len(value))
        return (Bits(length % 8) + value).bytes
    elif isinstance(value, list):
        check_lengths_match(length, len(value))
        return (Bits(length % 8) + Bits(value)).bytes
    else:
        raise TypeError("Value {:s} is of unsupported type: {:s}".format(value, type(value)))


# TODO: make automatic on BmvVMRAction construction.
def to_runtime_data(action, values):
    """Convert values to runtime data using action parameters information.

    Args:
        action: P4 action.
        values: Iterable of elements acceptable by tobits function.
    """
    return [tobytes(value, p.bitwidth) for value, p in zip(values, action.parameters)]
