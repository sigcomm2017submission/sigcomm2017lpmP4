from itertools import chain, groupby

import bm_runtime.standard.ttypes as bm_types

from p4t.simple.vmr import SVMREntry, tobits

from p4t.bmv2.vmr import BmvVMREntry, BmvVMRDefaultEntry, BmvVMRAction, tobytes, to_runtime_data
from p4t.bmv2.utils import chain_tables
from p4t.bmv2.primitives import PriorityEncoder, KeyConstruction, SubKey


class BmvBasicClassifier(object):
    """ VMR with attached table.

    This presents target independent interface for manipulating VMR.
    """

    def __init__(self, table, vmr=None):
        """ Construct a classifier VMR optinally supplying entries.

        Args:
            vmr: Entries iterable to construct from.
        """

        self._table = table
        self._vmr = []
        self._default_entry = None

        if vmr is None:
            return
        for entry in vmr:
            if self._table.name != entry.table_name:
                raise ValueError(
                    'Entry table {:s} does not match VMR table {:s}'
                    .format(entry.table_name, self._table.name)
                )
            if entry.isdefault():
                self._default_entry = entry
            else:
                self._vmr.append(entry)

    def __len__(self):
        """ Get a number of VMR entries."""

        return len(self._vmr)

    def __getitem__(self, i):
        """ Get a VMREntry on a given position. """

        return self._to_svmr_entry(self._vmr[i])

    def add(self, entry):
        if self._table.match_type == 'exact':
            if not entry.is_exact():
                raise ValueError('Entry should be an exact match')
            self._add_exact(entry.key, entry.action.action, entry.action.runtime_data)
        elif self._table.match_type == 'lpm':
            if not entry.is_prefix():
                raise ValueError('Entry should be prefix')
            self._add_prefix(entry.key, sum(entry.mask), entry.action.aciton, entry.aciton.runtime_data)
        else:
            raise NotImplementedError("Only exact and prefix matches are supported")

    @property
    def default_action(self):
        action = self.table.pipeline.program.get_action(self._default_entry.action_name)
        return BmvVMRAction(action, self._default_entry.runtime_data)

    @default_action.setter
    def default_action(self, action):
        self._default_entry = BmvVMRDefaultEntry(
            self._table.name, action.action.name, action.runtime_data
        )

    def subset(self, name, i):
        result = BmvActionClassifier(name, self.table)
        result.default_action = self.default_action
        for entry in self[i]:
            result.add(entry)
        return result

    @property
    def bmv_entries(self):
        """ Returns target specific untyped VMR."""

        return chain(self._vmr, [self._default_entry] if self._default_entry is not None else [])

    def _field_length(self):
        try:
            field, = self._table.fields
            return field.length
        except ValueError:
            raise NotImplementedError('Multifield tables are currently unsupported')

    def _add_prefix(self, key, length, action, args):
        """ Add new prefix entry to VMR.

        Args:
            key: Lookup key, must be a sequence of bool.
            length: Prefix length.
            action: P4 Action to execute on match.
            args: Action parameters, must be a list of bytes objects.
        """

        self._vmr.append(BmvVMREntry(
            self._table.name,
            [bm_types.BmMatchParam(
                type=bm_types.BmMatchParamType.LPM,
                lpm=bm_types.BmMatchParamLPM(tobytes(key, self._field_length()), length)
            )],
            action.name, args,
            bm_types.BmAddEntryOptions(priority=None)
        ))

    def _add_exact(self, key, action, args):
        """Add new exact entry to VMR.

        Args:
            key: Lookup key, must be a sequence of bool.
            action: P4 action to execute on match.
            args: Action parameters, must be a list of bytes objects.
        """

        self._vmr.append(BmvVMREntry(
            self._table.name,
            [bm_types.BmMatchParam(
                type=bm_types.BmMatchParamType.EXACT,
                exact=bm_types.BmMatchParamExact(tobytes(key, self._field_length()))
            )],
            action.name, args,
            bm_types.BmAddEntryOptions(priority=None)
        ))

    @property
    def table(self):
        """VMR table."""
        return self._table

    def _to_svmr_entry(self, entry):
        key = []
        mask = []
        priority = None

        if not entry.isdefault():
            for match_key, field in zip(entry.match_key, self._table.fields):
                if match_key.type == bm_types.BmMatchParamType.LPM:
                    key.extend(tobits(match_key.lpm.key, field.length))
                    mask.extend([True] * match_key.lpm.prefix_length + [False] * (field.length - match_key.lpm.prefix_length))
                else:
                    raise NotImplementedError
            priority = entry.options.priority
        else:
            length = sum(f.length for f in self._table.fields)
            key = [False] * length
            mask = [False] * length

        return SVMREntry(key, mask, BmvVMRAction(self._table.pipeline.program.get_action(entry.action_name), entry.runtime_data), priority)


class BmvReorderingClassifier(BmvBasicClassifier):
    """ Classifier that reorders classification bits."""

    def __init__(self, name, lookup_type, classifier, bits, keys):
        """ Initializes a new reordering classifier from the existing P4 table.

        Args:
            name: The name of the new classifier.
            table: The original table.
            bits: The sequence of bit indices to use.
            keys: The key lookup infrastructure to create new keys.
        """

        # TODO: what if are passed reordering classifier?

        super(BmvReorderingClassifier, self).__init__(
            classifier.table.pipeline.add_table(name, lookup_type, classifier.table.max_size)
        )

        self._table.set_keys(keys.add(self._bits2subkeys(classifier.table.fields, bits)))
        self._table.set_actions(classifier.table.actions)

        self._bits = bits
        self._vmr = []

        for entry in classifier:
            mask = [entry.mask[j] for j in self._bits]
            key = [entry.value[j] for j in self._bits]
            self.add(SVMREntry(key, mask, entry.action, entry.priority))

        self.default_action = classifier.default_action

    @staticmethod
    def _bits2subkeys(fields, bits):
        """ Transforms a sequence of bit indices into a list subkeys.

        Args:
            fields: Sequence of fields that define bits' source.
            bit_indices: Indices of bits that should form new keys.
        """
        # TODO: check that bit indices are contiguous
        bit2field = []
        offsets = []
        for field in fields:
            bit2field.extend([field] * field.length)
            offsets.extend(range(field.length))

        field_offset = ((bit2field[x], offsets[x]) for x in bits)
        field_offset_grouped = (list(x[1]) for x in groupby(field_offset, lambda y: y[0].name))

        return [
            SubKey(field=x[0][0], start=x[0][1], end=x[-1][1] + 1)
            for x in field_offset_grouped
        ]


class BmvMultigroupClassifier(object):
    def __init__(self, name, subclassifiers, init_action):
        if len(subclassifiers) < 2:
            raise ValueError("The number of subclassifiers must not be less than two")

        self._pipeline = subclassifiers[0].table.pipeline
        self._init_action = init_action
        self._prios = PriorityEncoder()

        self._dispatcher = self._create_dispatcher(
            name + "_dispatch", self._pipeline, self._prios.prio
        )

        self._subclassifiers = []
        for subclassifier in subclassifiers:
            self._add_subclassifier(subclassifier)
        self._set_max = BmvActionClassifier(self._pipeline, self._prios.create_setmax())

        chain_tables(*chain(self._subclassifiers, [self._set_max, self._dispatcher.table]))
        self._prios.create_setmax

    @property
    def table(self):
        return self._subclassifiers[0].table

    @staticmethod
    def _create_dispatcher(name, pipeline, dispatch_key):
        dispatch_table = pipeline.add_table(name, 'exact', 1)
        dispatch_table.set_keys(dispatch_key)
        return BmvBasicClassifier(dispatch_table)

    @staticmethod
    def _update_actions(dst_table, src_table):
        dst_table.set_actions(
            *(dst_table.actions + src_table.actions)
        )
        dst_table.set_default_next(src_table.get_default_next())
        for action in src_table.actions:
            # TODO: check for conflicts
            dst_table.set_next(action, src_table.get_next(action))

    def _add_subclassifier(self, classifier):
        # TODO: priorities are assumed to be gloablly unique
        self._update_actions(self._dispatcher.table, classifier.table)

        set_prio = self._prios.add()
        classifier.table.set_actions(set_prio)

        for entry in classifier.vmr:
            # TODO: we can't just take it and set it like this
            self._dispatcher.add(SVMREntry(
                tobits(entry.priority, PriorityEncoder.PRIO_WIDTH),
                [True] * PriorityEncoder.PRIO_WIDTH, entry.args, 0
            ))

            entry.action = BmvVMRAction(set_prio, to_runtime_data(set_prio, entry.priority))

        self._subclassifiers.append(classifier)

    def __getitem__(self, key):
        return self._subclassifiers[key]

    def __len__(self):
        return len(self._subclassifiers)


class BmvActionClassifier(BmvBasicClassifier):
    def __init__(self, pipeline, action):
        super(BmvActionClassifier, self).__init__(
            pipeline.add_table(action.name, 'exact', 0)
        )
        self.table.set_actions(action)
        self.set_default_action(action)

    def add(self, entry):
        raise TypeError("One cannot simply add an entry to the ActionClassifier")

    def set_default_action(self, entry):
        raise TypeError("One cannot simply change a default action of an ActionClassifier")


class BmvClassifierFactory(object):
    def __init__(self, name, program):
        self._init_action = program.add_action(name + "_init", {})
        self._keys = KeyConstruction(program, name, self._init_action)

    @property
    def init_action(self):
        return self._init_action

    def reordering_classifier(self, name, classifier, lookup_type, bits):
        return BmvReorderingClassifier(name, classifier, lookup_type, bits, self._keys)

    def multigroup_classifier(self, name, subclassifiers):
        return BmvMultigroupClassifier(name, subclassifiers, self._init_action)
