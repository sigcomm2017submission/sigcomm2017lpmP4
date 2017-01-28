from p4t.common import OptimizationStep
from p4t.bmv2.classifiers import BmvClassifierFactory, BmvActionClassifier
from p4t.bmv2.utils import chain_tables, redirect_table
from p4t.optimizations.lpm import optimize


class LpmOptimizationStep(OptimizationStep):
    step_name = 'lpm'

    def optimize(self, args, factory, classifiers, program):  # pylint: disable=arguments-differ
        # TODO: decouple classifiers and vmr rep
        try:
            table_name, = args
        except ValueError:
            raise ValueError("Lpm step accepts one argument: lpm <table_name>")

        orig_classifier = classifiers[table_name]

        factory = BmvClassifierFactory("p4t_lpm", program)
        opt_classifier = optimize(classifiers[table_name], factory)

        init = BmvActionClassifier("p4t_lpm", factory.init_action)
        chain_tables(init, opt_classifier.table)
        redirect_table(orig_classifier.table, init)
