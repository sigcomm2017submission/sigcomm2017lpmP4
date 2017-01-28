#include <boost/graph/adjacency_list.hpp>
#include <boost/graph/max_cardinality_matching.hpp>
#include <boost/graph/breadth_first_search.hpp>
#include <boost/graph/successive_shortest_path_nonnegative_weights.hpp>

#include "chain_algos.h"

namespace {

using namespace boost;
using namespace p4t;

using p4t::tuple;
using p4t::pair;
using std::begin;
using std::end;

using MaxMatchingGraph = adjacency_list<vecS, vecS, undirectedS>;

using AntichainGraph = adjacency_list<vecS, vecS, directedS>;

using MinCostMaxFlowTraits = adjacency_list_traits<vecS, vecS, directedS>;
using MinCostMaxFlowGraph = adjacency_list<vecS, vecS, directedS, no_property,
        property<edge_capacity_t, int,
            property<edge_residual_capacity_t, int,
                property<edge_reverse_t, MinCostMaxFlowTraits::edge_descriptor,
                    property<edge_weight_t, int>
                >
            >
        >
    >;

template<class VD>
auto calculate_chains(vector<Support> const& ss, vector<VD> const& mate, VD absent) {
    // Note that vertices mapped to itself are not considered start  vertices and, thus, they won't be added to any chain 
    vector<bool> is_chain_start(ss.size(), true);
    for (VD i = 0; i < ss.size(); i++) {
        if (mate[i] != absent) {
            is_chain_start[mate[i] - ss.size()] = false;
        }
    }

    vector<vector<Support>> result{}; 
    for (VD i = 0; i < ss.size(); ++i) {
        if (is_chain_start[i]) {
            vector<Support> chain{};
            for (VD j = i; j != absent; j = mate[j] - ss.size()) {
                chain.emplace_back(ss[j]);
                if (mate[j] == absent) {
                    break;
                }
            }
            result.emplace_back(chain);
        }
    }
    return result;
}

template<class Graph>
auto add_dilworths_edges(vector<Support> const& ss, Graph& g) {
    using VD = graph_traits<MaxMatchingGraph>::vertex_descriptor;

    for (VD i = 0; i < ss.size(); i++) {
        for (VD j = 0; j < ss.size(); j++) {
            if (is_subset(ss[i], ss[j]) && ss[i] != ss[j]) {
                add_edge(i, ss.size() + j, g);
            }
        }
    }
}

auto construct_dilworths_mates(vector<Support> const& ss) {
    using VD = graph_traits<MaxMatchingGraph>::vertex_descriptor;

    MaxMatchingGraph g{2 * ss.size()};

    add_dilworths_edges(ss, g);

    vector<VD> mate(2 * ss.size());
    auto const success = checked_edmonds_maximum_cardinality_matching(g, &mate[0]);
    assert(success);

    return mate;
}

auto find_max_antichain(vector<Support> const& ss) -> vector<size_t> {
    using VD = graph_traits<AntichainGraph>::vertex_descriptor;
    auto const mate = construct_dilworths_mates(ss);

    AntichainGraph g{2 * ss.size() + 1};
    auto const source = 2 * ss.size();

    add_dilworths_edges(ss, g);

    for (VD i = 0; i < ss.size(); i++) {
        // TODO: I don't like that we must know what the type of "no_mate" is.
        if (mate[i] != graph_traits<MaxMatchingGraph>::null_vertex()) {
            remove_edge(i, mate[i], g);
            add_edge(mate[i], i, g);
        } else {
            add_edge(source, i, g);
        }
    }
    
    vector<graph_traits<AntichainGraph>::vertices_size_type> distance(num_vertices(g), 0);
    breadth_first_search(g, source, visitor(make_bfs_visitor(record_distances(&distance[0], on_tree_edge()))));

    vector<size_t> result{};
    for (VD i = 0; i < ss.size(); i++) {
        if (distance[i] != 0 && distance[i + ss.size()] == 0) {
            result.emplace_back(i);
        }
    }

    auto const num_edges = count_if(begin(mate), begin(mate) + ss.size(), [] (auto const x) { return x != graph_traits<MaxMatchingGraph>::null_vertex(); });

    log()->info("for a set of size {:d} with a chain cover of size {:d} antichain of size {:d} is found", ss.size(), ss.size() - num_edges, result.size());

    return result;
}

auto calc_memory_increase(size_t s1_idx, size_t s2_idx, vector<Support> const& ss, vector<int> const& weights) {
    auto const res = get_union(ss[s1_idx], ss[s2_idx]);
    return ((long long) weights[s1_idx]) * ((1ll << (res.size() - ss[s1_idx].size())) - 1)
        + ((long long) weights[s2_idx]) * ((1ll << (res.size() - ss[s2_idx].size())) - 1);
}

struct AntichainReductionResult {
    AntichainReductionResult(int s1_idx, int s2_idx, int md) 
        : s1_idx{s1_idx}, s2_idx{s2_idx}, md{md} {}
    int const s1_idx;
    int const s2_idx;
    int const md;

    auto is_valid() {
        return s1_idx != -1;
    }
};

auto try_reduce_antichain(vector<size_t> const& ac, vector<Support> const& ss, vector<int> const& weights, int max_md) -> AntichainReductionResult  {
    auto first_succeded = false; 
    auto s1_idx_opt = -1; 
    auto s2_idx_opt = -1;
    auto md_opt = -1;

    for (auto const sac_idx : ac) {
        for (auto i = 0u; i < ss.size(); i++) {
            if (is_subset(ss[sac_idx], ss[i]) && ss[sac_idx] != ss[i]) {
                first_succeded = true;

                auto const md = calc_memory_increase(sac_idx, i, ss, weights);
                log()->info("trying to merge {} with {}, memory increase is {:d}", ss[sac_idx], ss[i], md);
                if (md <= max_md && (s1_idx_opt == -1 || md_opt > md)) {
                    s1_idx_opt = sac_idx;
                    s2_idx_opt = i;
                    md_opt = md;
                }
            }
        }
    }

    if (first_succeded) {
       return AntichainReductionResult(s1_idx_opt, s2_idx_opt, md_opt);
    }
    

    for (auto s1_idx : ac) {
        for (auto s2_idx : ac) {
            if (s1_idx != s2_idx) {
                auto const md = calc_memory_increase(s1_idx, s2_idx, ss, weights);
                log()->info("trying to merge {:d} with {:d}, memory increase is {:d}", s1_idx, s2_idx, md);
                if (md <= max_md && (s1_idx_opt == -1 || md_opt > md)) {
                    s1_idx_opt = s1_idx;
                    s2_idx_opt = s2_idx;
                    md_opt = md;
                }
            }
        }
    }

    return AntichainReductionResult(s1_idx_opt, s2_idx_opt, md_opt);
}


auto get_preimage(support_map<Support> const& map, Support const& elem) -> vector<Support> {
    vector<Support> result{};
    for (auto const& ss : map) {
        if (ss.second == elem) {
            result.emplace_back(ss.first);
        }
    }
    return result;
}

auto expand(size_t s1_idx, size_t s2_idx, vector<Support> &ss, vector<int> &weights, support_map<Support> &expansions) {
    if (s2_idx < s1_idx) {
        swap(s1_idx, s2_idx);
    }

    auto const s1_preimage = get_preimage(expansions, ss[s1_idx]);
    auto const s2_preimage = get_preimage(expansions, ss[s2_idx]);
    auto const new_s = get_union(ss[s1_idx], ss[s2_idx]);
    auto const md = calc_memory_increase(s1_idx, s2_idx, ss, weights);
    auto const new_w = weights[s2_idx] + weights[s1_idx] + md;

    log()->info("expanding set #{:d} and set #{:d}, the old size is {:d}", s1_idx, s2_idx, ss.size());

    ss.erase(begin(ss) + s2_idx);
    weights.erase(begin(weights) + s2_idx);
    ss.erase(begin(ss) + s1_idx);
    weights.erase(begin(weights) + s1_idx);

    ss.emplace_back(new_s);
    weights.emplace_back(new_w);

    for (auto const s : s1_preimage) {
        expansions[s] = new_s;
    }
    for (auto const s : s2_preimage) {
        expansions[s] = new_s;
    }

    log()->info("stop expanding, the new size is {:d}", ss.size());

    return md;
}

}

auto p4t::find_min_chain_partition(vector<Support> const& ss) -> vector<vector<Support>> {
    auto const mate = construct_dilworths_mates(ss);
    return calculate_chains(ss, mate, graph_traits<MaxMatchingGraph>::null_vertex());
}


auto p4t::find_min_bounded_chain_partition(
        vector<vector<Support>> const& sss, 
        vector<vector<int>> const& weights, 
        int max_num_chains) -> vector<vector<vector<Support>>> {
    using namespace boost;
    
    using std::begin; // confilcts with boost
    using std::end; // conflicts with boost
    using VD = graph_traits<MinCostMaxFlowGraph>::vertex_descriptor;

    vector<int> ss_offset{};
    auto total_size = 0;
    for (auto const& ss : sss) {
        ss_offset.emplace_back(total_size);
        total_size += ss.size();
    }

    MinCostMaxFlowGraph g(2 * total_size + 3); // source, aux_source, target
    auto const source = 2 * total_size;
    auto const aux_source = 2 * total_size + 1;
    auto const target = 2 * total_size + 2;

    auto capacity = get(edge_capacity, g);
    auto rev = get(edge_reverse, g);
    auto weight = get(edge_weight, g);

    auto add_edge = [&capacity, &rev, &weight, &g]
        (VD u, VD v, int c, int w) {
            auto e = boost::add_edge(u, v, g).first;
            auto er = boost::add_edge(v, u, g).first;
            rev[e] = er;
            rev[er] = e;

            capacity[e] = c;
            capacity[er] = 0;
            weight[e] = w;
            weight[er] = -w;
        };


    for (auto ss_idx = 0; ss_idx < int(sss.size()); ss_idx++) {
        auto const& ss = sss[ss_idx];
        auto const offset = ss_offset[ss_idx];

        for (VD i = 0; i < ss.size(); i++) {
            for (VD j = 0; j < ss.size(); j++) {
                if (is_subset(ss[i], ss[j]) && ss[i] != ss[j]) {
                    add_edge(offset + i, total_size + offset + j, 1, 0);
                }
            }

            add_edge(offset + i, total_size + offset + i, 1, weights[ss_idx][i]);
        }

    }

    for (VD i = 0; int(i) < total_size; i++) {
        add_edge(aux_source, i, 1, 0);
        add_edge(total_size + i, target, 1, 0);
    }

    add_edge(source, aux_source, std::max(0, total_size - max_num_chains), 0);

    successive_shortest_path_nonnegative_weights(g, source, target);

    auto res_capacity = get(edge_residual_capacity, g);

    vector<vector<vector<Support>>> result{};
    for (auto ss_idx = 0; ss_idx < int(sss.size()); ss_idx++) {
        auto const& ss = sss[ss_idx];
        auto const offset = ss_offset[ss_idx];

        vector<VD> mate(ss.size() * 2, graph_traits<MinCostMaxFlowGraph>::null_vertex());

        for (VD i = 0; i < ss.size(); i++) {
            for (VD j = 0; j < ss.size(); j++) {
                auto edge_ok = edge(offset + i, total_size + offset + j, g);
                if (edge_ok.second && res_capacity[edge_ok.first] == 0) {
                    mate[i] = j + ss.size();
                    mate[j + ss.size()] = i;
                }
            }
        }

        result.emplace_back(calculate_chains(ss, mate, graph_traits<MinCostMaxFlowGraph>::null_vertex()));
    }

    return result;
}


auto p4t::find_min_chain_partition_w_expansion(
        vector<vector<Support>> const& init_sss,
        vector<vector<int>> const& init_weights,
        int max_memory) -> pair<vector<vector<Support>>, vector<support_map<Support>>> {
    auto sss = init_sss;
    auto weights = init_weights;

    auto current_memory = 0;
    for (auto const& w : weights) {
        current_memory += accumulate(std::begin(w), std::end(w), 0);
    }

    vector<support_map<Support>> expansions{};
    for (auto const& ss : sss) {
        expansions.emplace_back();
        for (auto const& s : ss) {
            expansions.back()[s] = s;
        }
    }

    while (true) {
        vector<AntichainReductionResult> our_options;

        for (auto i = 0u; i < sss.size(); i++) {
            our_options.emplace_back(try_reduce_antichain(find_max_antichain(sss[i]), sss[i], weights[i], max_memory - current_memory));
        }

        // It should be extracted.. Or is it already?
        auto best_option = -1;
        for (auto i = 0u; i < our_options.size(); i++) {
            if (our_options[i].is_valid() && (best_option == -1 || our_options[i].md < our_options[best_option].md)) {
                best_option = i;
            }
        }

        if (best_option == -1) {
            break;
        } 

        current_memory += expand(our_options[best_option].s1_idx, our_options[best_option].s2_idx, sss[best_option], weights[best_option], expansions[best_option]);
    }

    return make_pair(sss, expansions);
}
