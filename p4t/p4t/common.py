""" This module contains definitions that are used throughout all optimization infrastructure. """
from collections import namedtuple


class OptimizationError(Exception):
    """ A generic class for exceptions raised as a part of optimization process."""

    def __init__(self, what="optimization error"):
        Exception.__init__(self)
        self.what = what

    def __str__(self):
        return self.what


class OptimizationStepRegistration(type):
    """ A metaclass that works in conjunction with OptimizationStep to register optimization steps. """
    def __init__(cls, name, bases, attrs):
        super(OptimizationStepRegistration, cls).__init__(name, bases, attrs)
        if not hasattr(cls, 'steps'):
            cls.steps = {}
        else:
            if cls.step_name is None:
                raise ValueError('step_name is undefined for %s' % name)
        cls.steps.update({cls.step_name: cls})


class OptimizationStep(object):
    """ The base class from which all optimization steps should inherit.

    Typical definition of an optimization step should look like this:
    ::
        class TestOptimizationStep(OptimizationStep):
            step_name = 'test'

            def optimize(self, data, args):
                ...
    """
    __metaclass__ = OptimizationStepRegistration

    step_name = None

    def optimize(self, data, args):
        """ Performa an optimization step.

        Args:
            data: Data to performa the optimization on.
            args: Additional parameters to an optimization step.
        """
        raise NotImplementedError


class OptimizationData(namedtuple('OptimizationData', ['program', 'classifiers'])):
    """ A class encompassing data necessary for optimizations.

    Attributes:
        program: The represntation of P4 program (e.g., bmv2.pt_types.vmr).
        vmr: A dictionary mapping a table_name to VMR (e.g., bmv2.p4_vmr.BmvVMR).
        vmr_factory: A factory that creates new instances of target-specific VMRs
            (e.g., bmb2.p4_vmr.BmvVMRFactory).
    """

    __slots__ = ()
