from p4t.simple.vmr import SVMREntry
from p4t.simple.primitives import FPCAction

# TODO: check correct copying of entries


class BasicClassifier(object):
    def __init__(self, name, bitwidth, vmr=None, default_action=None):
        self._name = name
        self._bitwidth = bitwidth

        self._vmr = []
        self.default_action = default_action
        if vmr is not None:
            for entry in vmr:
                self.add(entry)

    def __len__(self):
        return len(self._vmr)

    def __getitem__(self, i):
        return self._vmr[i]

    def add(self, entry):
        self._check_entry_length(entry)
        self._vmr.append(entry)

    def subset(self, name, indices):
        return BasicClassifier(
            name, self.bitwidth,
            (self._vmr[i] for i in indices),
            self.default_action
            )

    @property
    def name(self):
        return self._name

    @property
    def bitwidth(self):
        return self._bitwidth

    def _check_entry_length(self, entry):
        if len(entry.value) != self._bitwidth:
            raise ValueError("VMR has wrong bit length")


class MultigroupClassifier(object):
    def __init__(self, name, subclassifiers):
        self._name = name
        self._subclassifiers = subclassifiers

    def __len__(self):
        return len(self._subclassifiers)

    def __getitem__(self, i):
        return self._subclassifiers[i]


class ReorderingClassifier(BasicClassifier):
    def __init__(self, name, bits, vmr=None, default_action=None):
        super(ReorderingClassifier, self).__init__(name, len(bits), vmr, default_action)

        self._bits = bits

    @classmethod
    def from_original_vmr(cls, name, bits, original_vmr=None, default_action=None):
        vmr = []
        if original_vmr is not None:
            for entry in original_vmr:
                mask = [entry.mask[j] for j in bits]
                key = [entry.value[j] for j in bits]
                action = entry.action if len(bits) == len(entry.mask) else FPCAction(entry)
                vmr.append(SVMREntry(key, mask, action, entry.priority))
        return cls(name, bits, vmr, default_action)

    @classmethod
    def from_classifier(cls, name, classifier, bits):
        assert(isinstance(classifier, BasicClassifier))
        return cls.from_original_vmr(name, bits, classifier, classifier.default_action)

    def subset(self, name, indices):
        return ReorderingClassifier(
            name, self.bits,
            (self._vmr[i] for i in indices),
            self.default_action
            )

    @property
    def bits(self):
        return self._bits


class ClassifierFactory(object):
    @staticmethod
    def reordering_classifier(name, classifier, bits):
        return ReorderingClassifier.from_classifier(name, classifier, bits)

    @staticmethod
    def multigroup_classifier(name, subclassifiers):
        return MultigroupClassifier(name, subclassifiers)
