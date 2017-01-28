""" Module that defines an optimization Manager, an optimization entry point. """
from p4t.common import OptimizationStep, OptimizationData
from p4t.steps import *  # pylint: disable=wildcard-import, unused-wildcard-import; # noqa: F403


class OptimizationManager(object):  # pylint: disable=too-few-public-methods
    """ A manager that dispatches an optimization request to optimization steps.

    Attributes:
        data: Data to perform an optimization on (see OptimizationData).
    """

    def __init__(self):
        self.data = OptimizationData()

    def optimize(self, step_name, step_args):
        """ Performs an optimization.

        Args:
            step_name: The name of the step.
            step_args: Step-specific optimization parameters.
        """
        try:
            step = OptimizationStep.steps[step_name]  # pylint: disable=no-member
        except KeyError:
            raise ValueError(
                '{:s}: there is no such optimization step'.format(step_name)
            )

        step().optimize(self.data, step_args)
