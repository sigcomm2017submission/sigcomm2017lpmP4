#include <boost/python.hpp>

#include "p4t_native.h"

BOOST_PYTHON_MODULE(p4t_native) {
    using namespace boost::python;

    def("min_pmgr", p4t::min_pmgr);
    def("best_subgroup", p4t::best_subgroup);
    def("set_num_threads", p4t::set_num_threads);
    def("min_bmgr", p4t::min_bmgr);
    def("min_pmgr_w_expansions", p4t::min_pmgr_w_expansions);
}
