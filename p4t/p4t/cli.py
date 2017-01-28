""" This module provides a CLI for an OptimizationManager. """

import cmd
import json
from itertools import chain

import runtime_CLI as bm_CLI
import bm_runtime.standard.ttypes as bm_types

from p4t.manager import OptimizationManager
from p4t.bmv2.p4_types import Program
import p4t.bmv2.vmr as vmr
from p4t.bmv2.utils import classifiers_by_table


class TransformAPI(cmd.Cmd):
    """ Optimization subshell. """

    prompt = 'OptmizationCmd: '
    intro = 'Optimization subshell for P4 setup'

    def __init__(self, runtimeAPI):
        cmd.Cmd.__init__(self)

        self.runtimeAPI = runtimeAPI  # pylint: disable=invalid-name
        self.optimizer = OptimizationManager()
        self.vmr = []

    @bm_CLI.handle_bad_input
    def do_table_add(self, line):
        "Add entry to a match table: table_add <table name> <action name> <match fields> => <action parameters> [priority]"

        self.vmr.append(self._parse_table_add(line))

    @bm_CLI.handle_bad_input
    def do_table_set_default(self, line):
        "Set default action for a match table: table_set_default <table name> <action name> <action parameters>"

        self.vmr.append(self._parse_table_set_default(line))

    @bm_CLI.handle_bad_input
    def do_optimize(self, line):
        "Run optimization step: optimize <optimization_step> <step_args>"

        args = line.split()
        self.runtimeAPI.at_least_n_args(args, 1)

        json_config = json.loads(self.runtimeAPI.client.bm_get_config())

        program = Program(json_config)
        self.optimizer.data.program = program
        # TODO: it really should be a VMR
        self.optimizer.data.classifiers = classifiers_by_table(program, self.vmr)

        try:
            self.optimizer.optimize(args[0], args[1:])
        except ValueError as err:
            raise bm_CLI.UIn_Error(str(err))

        self.runtimeAPI.client.bm_load_new_config(json.dumps(json_config))
        for entry in chain(*(vmr.entries for vmr in self.optimizer.data.vmr.values())):
            if not entry.isdefault():
                entry_handle = self.runtimeAPI.client.bm_mt_add_entry(
                    0, entry.table_name, entry.match_key, entry.action_name, entry.runtime_data,
                    entry.options
                )
                print "Entry has been added with handle", entry_handle
            else:
                self.runtimeAPI.print_set_default(entry.table_name, entry.action_name, entry.runtime_data)
                self.runtimeAPI.client.bm_mt_set_default_action(0, entry.table_name, entry.action_name, entry.runtime_data)

        return True

    def do_EOF(self, _):  # pylint: disable=invalid-name,no-self-use
        """ Exit to an outer subshell. """
        print()
        return True

    def _parse_table_add(self, line):
        # This is a copy paste from the copyrighted file... Think about it
        args = line.split()

        self.runtimeAPI.at_least_n_args(args, 3)

        table_name, action_name = args[0], args[1]
        table = self.runtimeAPI.get_res("table", table_name, bm_CLI.TABLES)
        if action_name not in table.actions:
            raise bm_CLI.UIn_Error(
                "Table %s has no action %s" % (table_name, action_name)
            )

        if table.match_type in {bm_CLI.MatchType.TERNARY, bm_CLI.MatchType.RANGE}:
            try:
                priority = int(args.pop(-1))
            except:
                raise bm_CLI.UIn_Error(
                    "Table is ternary, but could not extract a valid priority from args"
                )
        else:
            priority = 0

        # guaranteed to exist
        action = bm_CLI.ACTIONS[action_name]

        idx = 0
        for idx, input_ in enumerate(args[2:]):
            if input_ == "=>":
                break
        idx += 2
        match_key = args[2:idx]
        action_params = args[idx+1:]
        if len(match_key) != table.num_key_fields():
            raise bm_CLI.UIn_Error(
                "Table %s needs %d key fields" % (table_name, table.num_key_fields())
            )

        runtime_data = self.runtimeAPI.parse_runtime_data(action, action_params)

        match_key = bm_CLI.parse_match_key(table, match_key)

        return vmr.BmvVMREntry(
            table_name, match_key, action_name, runtime_data,
            bm_types.BmAddEntryOptions(priority=priority)
            )

    def _parse_table_set_default(self, line):
        # This is a copy paste from the copyrighted file... Think about it

        args = line.split()

        self.runtimeAPI.at_least_n_args(args, 2)

        table_name, action_name = args[0], args[1]

        table = self.runtimeAPI.get_res("table", table_name, bm_CLI.TABLES)
        if action_name not in table.actions:
            raise bm_CLI.UIn_Error(
                "Table %s has no action %s" % (table_name, action_name)
            )
        action = bm_CLI.ACTIONS[action_name]
        if len(args[2:]) != action.num_params():
            raise bm_CLI.UIn_Error(
                "Action %s needs %d parameters" % (action_name, action.num_params())
            )

        runtime_data = bm_CLI.parse_runtime_data(action, args[2:])

        return vmr.BmvVMRDefaultEntry(table_name, action_name, runtime_data)


class TRuntimeAPI(bm_CLI.RuntimeAPI):
    """ CLI that defines additional  subshells for bm_CLI.RuntimeAPI. """

    def do_optimization(self, _):
        "Enter optimization subshell"
        TransformAPI(self).cmdloop()


def main():
    """ CLI entry point. """
    args = bm_CLI.get_parser().parse_args()

    standard_client, mc_client = bm_CLI.thrift_connect(  # pylint: disable=unbalanced-tuple-unpacking
        args.thrift_ip, args.thrift_port,
        bm_CLI.RuntimeAPI.get_thrift_services(args.pre)
    )

    bm_CLI.load_json_config(standard_client, args.json)

    TRuntimeAPI(args.pre, standard_client, mc_client).cmdloop()

if __name__ == '__main__':
    main()
