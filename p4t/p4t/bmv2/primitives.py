""" Modules providing basic building blocks for classifier manipulation. """

from itertools import chain
from p4t.common import OptimizationError

from collections import namedtuple

SubKey = namedtuple('SubKey', ['field', 'start', 'end'])

class KeyConstruction(object):
    """ Class that to construct lookup keys from any subset of bits."""

    def __init__(self, program, prefix, init_action):
        """ Initializes new key construction entity.

        Args:
            program: P4 program (e.g., bmv2.p4_types.Program).
            prefix: Prefix used to disambigulate among other instances.
            init_action: Action where an actual key construction should happen.
        """

        self._program = program
        self._prefix = prefix
        self._init_action = init_action

        keys_header_name = prefix + 'keys'
        self._header_type = program.add_header_type('{:s}_t'.format(keys_header_name))
        self._header = program.add_header(keys_header_name, self._header_type, metadata=True)

        self._keys = []

    def add(self, subkeys):
        """ adds new """
        idx = len(self._keys)

        total_length = sum(x.end - x.start for x in subkeys)
        key = self._header_type.add_field('key_{:d}'.format(idx), total_length)
        self._init_action.add_primitive_call(
            'compress_{:d}'.format(len(subkeys)),
            self._header.get_field_instance(key), *chain(*subkeys)
        )

        self._keys.append(key)
        return self._header.get_field_instance(key)


class PriorityEncoder(object):
    """ Class that provides a way to select the highest priority among multiple values. """
    PRIO_WIDTH = 16

    def __init__(self, program, prefix, init_action):
        """ Initializes the PriorityEncoder.

        Args:
            program: P4 program (e.g., bmv2.p4_types.Program).
            prefix: Prefix used to disambigulate among other instances.
            init_action: Action where an actual key construction should happen.
        """

        self._program = program
        self._prefix = prefix
        self._init_action = init_action

        prios_header_name = prefix + 'prios'
        self._header_type = program.add_header_type('{:s}_t'.format(prios_header_name))
        self._header = program.add_header(prios_header_name, self._header_type, metadata=True)

        self._prio = self._header_type.add_field('prio', self.PRIO_WIDTH)
        self._init_action.add_primitive_call('modify_field', self._header.get_field_instance(self._prio), 0)
        self._subprios = []

    def add(self):
        """ Adds one more subpriority field to take a maximum from.

        Returns:
            An action accepting a single value that sets up the subpriority field.
        """
        if hasattr(self, '_setmax_created'):
            raise OptimizationError("An attempt to add new priority after setmax action was created.")
        idx = len(self._subprios)
        subprio = self._header_type.add_field('prio_{:d}'.format(idx), self.PRIO_WIDTH)
        set_prio_action = self._program.add_action(self._prefix + 'set_prio_{:d}'.format(idx), {'prio': self.PRIO_WIDTH})
        set_prio_action.add_primitive_call('modify_field', self._header.get_field_instance(subprio), 'prio')
        self._init_action.add_primitive_call('modify_field', self._header.get_field_instance(subprio), 0)
        self._subprios.append(subprio)
        return set_prio_action

    @property
    def prio(self):
        """ A field instance storing the maximal priority value. """
        return self._header.get_field_instance(self._prio)

    def create_setmax(self):
        """ Sets up an action that performs highest priority selection.

        Returns:
            Action that performs highest priority selection.
        """
        set_max_prio = self._program.add_action(self._prefix + 'set_max_prio', {})
        set_max_prio.add_primitive_call(
            'set_max_field_{:d}'.format(len(self._subprios)),
            self._header.get_field_instance(self._prio),
            *(self._header.get_field_instance(f) for f in self._subprios)
        )
        return set_max_prio



        tvmr.add_default(action)
    
        self._subvmrs.append(tvmr)
        return table        self.
