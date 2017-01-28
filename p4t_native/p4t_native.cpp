#include <iostream>
#include <limits>
#include <numeric>
#include <map>
#include <omp.h>

#include "filter.h"
#include "support.h"
#include "utils.h"

#include "chain_algos.h"
#include "oi_algos.h"

#include "p4t_native.h"

namespace {

using namespace p4t;

auto map_partition_indices(
        vector<vector<Support>> const& partition, 
        vector<Support> const & supports) -> vector<vector<int>> {

    support_map<int> support2partition{};
    for (auto i = 0u; i < partition.size(); i++) {
        for (auto const& s : partition[i]) {
            support2partition[s] = i;
        }
    }

    vector<vector<int>> result(partition.size());
    for (auto i = 0u; i < supports.size(); i++) {
        if (support2partition.count(supports[i])) {
            result[support2partition[supports[i]]].emplace_back(i);
        }
    }

    return result;
}

auto weight(vector<Support> const& unique_supports, 
        vector<Support> const& all_supports) -> vector<int> {
    support_map<int> support_cnt{};

    for (auto const& support : all_supports) {
        support_cnt[support]++;
    }

    vector<int> result(unique_supports.size());
    for (auto i = 0u; i < unique_supports.size(); i++) {
        result[i] = support_cnt[unique_supports[i]];
    }

    return result;
}

auto select_unique_n_weight(vector<Support> const& supports) 
    -> pair<vector<Support>, vector<int>> {
    auto const unique = select_unique(supports);
    auto const weights = weight(unique, supports);
    return make_pair(unique, weights);
}

auto svmrs2supports(py::object svmrs) {
    vector<vector<Support>> sss(len(svmrs));
    for (auto i = 0; i < len(svmrs); ++i) {
        sss[i] = to_supports(svmr2filters(svmrs[i]));
    }
    return sss;
}

} // namespace 

auto p4t::min_pmgr(py::object svmr) -> py::object {
    if (py::len(svmr) == 0) {
        return py::object();
    }

    auto const filters = svmr2filters(svmr);

    auto const supports = to_supports(filters);
    auto const supports_unique = select_unique(supports);

    auto const partition = find_min_chain_partition(supports_unique);
    auto const partition_indices = map_partition_indices(partition, supports);

    return py::make_tuple(to_python(partition), to_python(partition_indices));
}

auto p4t::min_bmgr(py::object svmrs, int max_num_groups) -> py::object {
    auto const n_supports = svmrs2supports(svmrs);

    vector<vector<Support>> n_unique_supports(n_supports.size());
    vector<vector<int>> n_weights(n_supports.size());
    for (auto i = 0u; i < n_supports.size(); ++i) {
        tie(n_unique_supports[i], n_weights[i]) = select_unique_n_weight(n_supports[i]);
    }
    
    auto const partitions = find_min_bounded_chain_partition(
        n_unique_supports, n_weights, max_num_groups
    );

    vector<vector<vector<int>>> n_partition_indices(len(svmrs));
    for (auto i = 0; i < len(svmrs); i++) {
        n_partition_indices[i] = map_partition_indices(partitions[i], n_supports[i]);
    }

    return py::make_tuple(to_python(partitions), to_python(n_partition_indices));
}

auto p4t::best_subgroup(py::object svmr, int l, bool only_exact, string algo) -> py::object {
    auto const filters = svmr2filters(svmr);

    if (algo == "min_similarity") {
        auto const bits = best_min_similarity_bits(filters, l);
        auto const result = find_maximal_oi_subset(filters, bits);

        return py::make_tuple(to_python(bits), to_python(result));
    } else  if (algo == "icnp_oi" || algo == "icnp_blockers") {
        auto const minme_mode = algo == "icnp_oi" ? MinMEMode::MAX_OI : MinMEMode::BLOCKERS;
        auto const bits_n_result = best_to_stay_minme(filters, l, minme_mode, only_exact);

        return py::make_tuple(to_python(bits_n_result.first), to_python(bits_n_result.second));
    } else {
        return py::object();
    }
}

void p4t::set_num_threads(int num_threads) {
    omp_set_dynamic(false);
    omp_set_num_threads(num_threads);
}


auto p4t::min_pmgr_w_expansions(py::object svmrs, int max_memory) -> py::object {
    if (len(svmrs) == 0) {
        return py::object();
    }

    auto const n_supports = svmrs2supports(svmrs);

    vector<vector<Support>> n_unique_supports(n_supports.size());
    vector<vector<int>> n_weights(n_supports.size());
    for (auto i = 0u; i < n_supports.size(); ++i) {
        tie(n_unique_supports[i], n_weights[i]) = select_unique_n_weight(n_supports[i]);
    }

    vector<vector<Support>> n_exp_unique_supports{};
    vector<support_map<Support>> expansions{};
    tie(n_exp_unique_supports, expansions) = 
        find_min_chain_partition_w_expansion(n_unique_supports, n_weights, max_memory);

    for (auto i = 0u; i < n_supports.size(); ++i) {
        log()->info("for set# {:d}, old size is {:d} and new size is {:d}", i, n_unique_supports[i].size(), n_exp_unique_supports[i].size());
    }

    vector<vector<vector<Support>>> partitions;
    for (auto const& supports : n_exp_unique_supports) {
        partitions.emplace_back(find_min_chain_partition(supports));
    }

    // this is to damn unreadable....
    vector<pair<vector<vector<int>>, vector<Support>>> partition_indices_n_exp;
    for (auto i = 0u; i < n_supports.size(); i++) {
        vector<Support> exp_supports{};
        for (auto const& s : n_supports[i]) {
            exp_supports.emplace_back(expansions[i][s]);
        }
        auto const partition_indices = map_partition_indices(partitions[i], exp_supports);
        partition_indices_n_exp.emplace_back(partition_indices, exp_supports);
    }

    return py::make_tuple(to_python(partitions), to_python(partition_indices_n_exp));
}
