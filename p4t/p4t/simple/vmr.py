from collections import namedtuple

from bitstring import Bits


def check_lengths_match(expected, actual):
    if expected != actual:
        raise ValueError("Length do not match: {:d} and {:d}"
                         .format(expected, actual))


class SVMREntry(namedtuple('SVMREntry', ['value', 'mask', 'action', 'priority'])):
    """A target independent vmr entry representation.

    Atributes:
        value: The value to be matched against, a sequence of bool.
        mask: The mask to be applied when matching, a sequence of bool.
        action: Action to execute on match.
        priority: Entry priority (if needed).
    """

    __slots__ = ()

    def __init__(self, value, mask, action, priority, length=None):  # pylint: disable=too-many-arguments
        """Construct VMREntry using optional bit length.

        Args:
            value: The value to be matched against (an instance of bitstring.Bits).
            mask: The mask to be applied when matching (an instance of bitstring.Bits).
            action: Action to be executed on match.
            priority: Entry priority (if needed)
            length: Bit length.
        """

        if length is not None:
            super(SVMREntry, self).__init__(
                tobits(value, length), tobits(mask, length), action, priority
            )
        else:
            super(SVMREntry, self).__init__(
                value, mask, action, priority
            )

    def is_prefix(self):
        return all(not self.mask[i] or self.mask[i + 1] for i in range(len(self.mask) - 1))

    def is_exact(self):
        return all(self.mask)


def tobits(value, length):
    """Convert value to bool sequence.

    Args:
        value: Must be either bits or bytes or int or list.
        length: Bit length of the value.
    """
    if isinstance(value, str):
        return Bits(bytes=value)[-length:]
    elif isinstance(value, int):
        return Bits(int=value, length=length)
    elif isinstance(value, Bits):
        check_lengths_match(length, len(value))
        return value
    elif isinstance(value, list):
        check_lengths_match(length, len(value))
        return Bits(value)
    else:
        raise TypeError("Value {:s} is of unsupported type: {:s}".format(value, type(value)))
