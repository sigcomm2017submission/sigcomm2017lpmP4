from itertools import groupby
from json import dumps as json_dumps

from p4t.bmv2.classifiers import BmvBasicClassifier


def classifiers_by_table(program, entries):
    """ Split entries by table and return list of corresponding typed VMRs.

    If there are multiple tables (possibly in different pipelines) that have
    the same name, the first one is returned.

    Args:
        program: P4 program.
        entries: Entries list to construct from.
    Returns:
        A dict mapping table name to typed vmr.
    """

    result = {}

    for table_name, table_entries in groupby(sorted(entries), lambda x: x.table_name):
        for pipeline in program.pipelines:
            try:
                result.update({
                    table_name: BmvBasicClassifier(pipeline.get_table(table_name), table_entries)
                })
                break
            except KeyError:
                pass

    return result


def chain_tables(*tables):
    prevoius = None
    for table in tables:
        if prevoius is not None:
            prevoius.set_default_next(table)
            for action in prevoius.actions:
                prevoius.set_next(action, table)

        prevoius = table


def _compare_name_if_exists(lhs, rhs):
    return lhs is not None and lhs.name == rhs.name


def redirect_table(original, target):
    # TODO: check that pipelines are equal
    for table in original.pipeline.tables:
        # TODO: normal comparasion between primitives!!!
        if _compare_name_if_exists(table.get_default_next(), original):
            table.set_default_next(target)
            for action in table.actions:
                if _compare_name_if_exists(table.get_next(action), original):
                    table.set_next(action, target)
    for conditinal in original.pipeline.conditionals:
        if _compare_name_if_exists(conditinal.false_next, original):
            conditinal.false_next = target
        if _compare_name_if_exists(conditinal.true_next, original):
            conditinal.true_next = target


def json_pp(json):
    print json_dumps(json, indent=2)
