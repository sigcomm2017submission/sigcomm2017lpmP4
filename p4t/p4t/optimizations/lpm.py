from itertools import chain, product

from p4t.simple.vmr import SVMREntry
import p4t_native


def get_support(svmrentry):
    return tuple(i for i, x in enumerate(svmrentry.mask) if x)


def isprefix(bits):
    return all(not bits[i] or bits[i + 1] for i in range(len(bits) - 1))


def expand(svmrentry, bits):
    bits = set(bits)
    mask = []
    value_options = []
    for i, (v, m) in enumerate(zip(svmrentry.value, svmrentry.mask)):
        mask.append(m or (i in bits))
        value_options.append([v] if m or (i not in bits) else [True, False])
    return [SVMREntry(mask, tuple(value), svmrentry.action, svmrentry.priority)
            for value in product(*value_options)]


def _chain2diffs(bitchain):
    diffs = []
    last = set()
    for support in (set(bits) for bits in bitchain):
        diffs.append(sorted(list(support - last)))
        last = support
    return diffs


def _chain2bits(bitchain):
    return tuple(chain(*_chain2diffs(bitchain)))


def set_number_of_threads(num_threads):
    p4t_native.set_num_threads(num_threads)


def optimize(classifier, factory):
    prefix = classifier.name + "_p4t_lpm"

    partition, partition_indices = p4t_native.min_pmgr(classifier)
    subclassifiers = []

    for bitchain, indices in zip(partition, partition_indices):
        subclassifiers.append(factory.reordering_classifier(
            prefix + "_1", classifier.subset("_", indices), _chain2bits(bitchain)
        ))

    return subclassifiers


def optimize_bounded(classifiers, factory, max_num_groups):
    partitions, n_partition_indices = p4t_native.min_bmgr(classifiers, max_num_groups)

    subclassifiers = []
    traditionals = []
    for classifier, (partition, partition_indices) in zip(classifiers, zip(partitions, n_partition_indices)):
        prefix = classifier.name + "_p4t_lpm"
        remaining_indices = set(range(len(classifier)))
        for bitchain, indices in zip(partition, partition_indices):
            subclassifiers.append(factory.reordering_classifier(
                prefix + "_1", classifier.subset("_", indices), _chain2bits(bitchain)
            ))
            remaining_indices -= set(indices)
        traditionals.append(classifier.subset(prefix + "_tradidional", remaining_indices))

    return subclassifiers, traditionals


def optimize_lpm_bounded_memory(classifiers, factory, max_memory):
    partitions, n_partition_indices_n_exp = p4t_native.min_pmgr_w_expansions(classifiers, max_memory)

    subclassifiers = []
    non_expanded_subclassifiers = []
    for classifier, (partition, (partition_indices, expansions)) in zip(classifiers, zip(partitions, n_partition_indices_n_exp)):
        prefix = classifier.name + "_p4t_lpm"
        for bitchain, indices in zip(partition, partition_indices):
            expanded = classifier.subset("_", [])
            for i in indices:
                for entry in expand(classifier[i], expansions[i]):
                    expanded.add(entry)
            subclassifiers.append(factory.reordering_classifier(
                prefix + "_1", expanded, _chain2bits(bitchain)
            ))

            non_expanded_subclassifiers.append(factory.reordering_classifier(
                prefix + "_1", classifier.subset("_", indices), _chain2bits(bitchain)
            ))

    return subclassifiers, non_expanded_subclassifiers


def optimize_oi(classifier, factory, max_width, algo, only_exact=False, max_num_groups=None):
    prefix = classifier.name + "_p4t_lpm"

    subclassifiers = []
    while (max_num_groups is None or len(subclassifiers) < max_num_groups) and len(classifier) > 0:
        bits, indices = p4t_native.best_subgroup(classifier, max_width, only_exact, algo)
        subclassifiers.append(factory.reordering_classifier(
            prefix + "_1", classifier.subset("_", indices), bits
            ))
        classifier = classifier.subset(classifier.name, set(range(len(classifier))) - set(indices))

    return subclassifiers, classifier
