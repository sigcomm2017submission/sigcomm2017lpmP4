#include <numeric>
#include <functional>
#include <parallel/algorithm>

#include "oi_algos.h"

namespace {

using namespace p4t;

auto is_oi(vector<Filter> const& filters, vector<int> const& bits_in_use) {
    vector<int> indices(filters.size());    
    iota(begin(indices), end(indices), 0);
    vector<bool> has_intersection(filters.size());

    __gnu_parallel::for_each(begin(indices), end(indices),
        [&filters, &bits_in_use, &has_intersection] (auto i) {
            for (auto j = 0; j < i; j++) {
                if (intersect(filters[i], filters[j], bits_in_use)) {
                    has_intersection[i] = true;
                    break;
                }
            }
        }
    );

    return std::find(begin(has_intersection), end(has_intersection), true) == end(has_intersection);
}

auto find_blockers(vector<Filter> const& filters, vector<int> const& bits_in_use) {
    assert(!filters.empty());
    vector<vector<bool>> blockers(filters.size(), vector<bool>(filters[0].size(), false));

    vector<int> indices(filters.size());    
    iota(begin(indices), end(indices), 0);

    __gnu_parallel::for_each(begin(indices), end(indices),
        [&filters, &bits_in_use, &blockers] (auto i) {
            auto const& lower = filters[i];
            for (auto j = 0; j < i; j++) {
                auto const& higher = filters[j];

                auto first_difference = -1;
                auto only_difference = true;
                for (auto bit : bits_in_use) {
                    if (higher[bit] != Bit::ANY && lower[bit] != Bit::ANY && higher[bit] != lower[bit]) {
                        if (first_difference != -1) {
                            only_difference = false;
                            break;
                        } else {
                            first_difference = bit;
                        }
                    }
                }
                if (first_difference == -1) {
                    for (auto bit : bits_in_use) {
                        blockers[i][bit] = true;
                    }
                    break;
                } else if (only_difference) {
                    blockers[i][first_difference] = true;
                }
            }
        }
    );

    return blockers;
}

template<class Function, class Cmp>
auto find_best_bit(vector<int> const& all_bits, vector<int> const& bits_to_avoid, Function value, Cmp cmp) -> int {
    auto best_bit = -1;
    auto best_bit_value = -1;

    vector<int> try_first{};
    set_difference(begin(all_bits), end(all_bits), begin(bits_to_avoid), end(bits_to_avoid), back_inserter(try_first));
    vector<int> try_second{};
    set_difference(begin(all_bits), end(all_bits), begin(try_first), end(try_first), back_inserter(try_second));
    
    for (auto const bit : try_first) {
        auto const new_value = value(bit);
        if (best_bit == -1 || cmp(new_value, best_bit_value)) {
            best_bit = bit;
            best_bit_value = new_value;
        }
    }

    if (best_bit == -1) {
        for (auto const bit : bits_to_avoid) {
            auto const new_value = value(bit);
            if (best_bit == -1 || cmp(new_value, best_bit_value)) {
                best_bit = bit;
                best_bit_value = new_value;
            }
        }
    }

    return best_bit;
}

auto remove_bit_w_blockers(vector<Filter> const filters, vector<int> const& bits_in_use, vector<int> const& bits_to_avoid, vector<int> const& bit_num_dontcare, uint l) -> pair<int, vector<int>> {
    auto const blockers = find_blockers(filters, bits_in_use);
    
    vector<int> bit_num_blockers(filters[0].size());

    for (auto const& blocker : blockers) {
        for (auto i = 0u; i < blocker.size(); i++) {
            if (blocker[i]) {
                bit_num_blockers[i]++;
            }
        }
    }

    // for (size_t i : bits_in_use) {
    //     log()->info("blockers[{:d}] = {:d}", i, bit_num_blockers[i]);
    // }

    // simple heuristic: when to choose simply by the number of ANY bits
    bool use_dontcare_heuristic = false;
    if (bits_in_use.size() > 2 * l) {
        vector<int> indices_sorted_by_blockers = bits_in_use;
        std::sort(indices_sorted_by_blockers.begin(), indices_sorted_by_blockers.end(), [&bit_num_blockers](int a, int b) {
            return bit_num_blockers[b] > bit_num_blockers[a];
        });
        log()->info("\t\t\t{:d} {:d} {:d} ... {:d}", bit_num_blockers[ indices_sorted_by_blockers[0] ], bit_num_blockers[ indices_sorted_by_blockers[1] ], bit_num_blockers[ indices_sorted_by_blockers[2] ], bit_num_blockers[ indices_sorted_by_blockers[l] ]);
        if ( bit_num_blockers[ indices_sorted_by_blockers[0] ] >= 0.9 * bit_num_blockers[ indices_sorted_by_blockers[2*l] ] ) {
            use_dontcare_heuristic = true;
        }
    }

    auto const best_bit = find_best_bit(bits_in_use, bits_to_avoid, 
            [&bit_num_blockers, &bit_num_dontcare](auto bit) { return bit_num_blockers[bit] - 0.000001 * bit_num_dontcare[bit]; }, std::less<>());

//    auto const best_bit = find_best_bit(bits_in_use, bits_to_avoid, 
//            [&bit_num_blockers](auto bit) { return bit_num_blockers[bit]; }, std::less<>());

    assert(best_bit >= 0);

    vector<int> result{};

    for (auto i = 0u; i < blockers.size(); i++) {
        if (!blockers[i][best_bit]) {
            result.emplace_back(i);
        }
    }

    log()->info("\t\tBest bit is {:d} with {:d} rules and {:d} ANY bits", best_bit, result.size(), bit_num_dontcare[best_bit]);

    if (use_dontcare_heuristic) {
        return make_pair(best_bit - 100000, result);
    } else {
        return make_pair(best_bit, result);
    }
}

auto find_exact(vector<Filter> const& filters, vector<int> const& bits_in_use) {
    auto exact = bits_in_use;
    for (auto const& filter : filters) {
        for (auto const bit : bits_in_use) {
            assert(bit < int(filter.size()));
            if (filter[bit] == Bit::ANY) {
                exact.erase(remove(begin(exact), end(exact), bit), end(exact));
            }
        }
    }
    return exact;
}

auto remove_bit_oi(vector<Filter> const filters, vector<int> const& bits_in_use, vector<int> const& bits_to_avoid) -> pair<int, vector<int>> {
    auto const best_bit = find_best_bit(bits_in_use, bits_to_avoid,
            [&bits_in_use, &filters] (auto bit) {
                auto cur_in_use = bits_in_use;

                cur_in_use.erase(find(begin(cur_in_use), end(cur_in_use), bit));
                
                return int(find_maximal_oi_subset(filters, cur_in_use).size());
            }, std::greater<>());

    assert(best_bit >= 0);

    return make_pair(best_bit, find_maximal_oi_subset(filters, bits_in_use));
}


} // namespace


auto p4t::best_min_similarity_bits(vector<Filter> const& filters, size_t l) -> vector<int> {
    assert(!filters.empty());

    vector<int> result{};
    while (result.size() < l) {
        auto best_bit = -1;
        auto best_value = -1;
        for (auto i = 0u; i < filters[0].size(); i++) {
            if (find(begin(result), end(result), i) != end(result)) {
                continue;
            }
            auto count_zero = 0;
            auto count_one = 0;
            for (auto const& f : filters) {
                if (f[i] == Bit::ANY || f[i] == Bit::ONE) {
                    count_one++;
                } 
                if (f[i] == Bit::ANY || f[i] == Bit::ZERO) {
                    count_zero++;
                }
            }
            auto const value = std::max(count_zero, count_one);
            if (best_bit == -1 || value < best_value) {
                best_bit = i;
                best_value = value;
            }
        }
        assert(best_bit >= 0);
        result.emplace_back(best_bit);
    }

    return result;
}


auto p4t::best_to_stay_minme(vector<Filter> filters, size_t l, MinMEMode mode, bool only_exact) -> std::pair<vector<int>, vector<int>> {
    assert(!filters.empty());
    log()->info("starting minme; mode: {:d}; only exact: {:b}", mode, only_exact);

    vector<int> bits_in_use{};
    for (auto i = 0u; i < filters[0].size(); i++) {
        bits_in_use.emplace_back(i);
    }

    auto exact_bits_in_use = find_exact(filters, bits_in_use);

    vector<int> indices(filters.size());
    std::iota(begin(indices), end(indices), 0);

    while (bits_in_use.size() > l || (only_exact && bits_in_use != exact_bits_in_use)) {
        int bit_to_remove;
        vector<int> oi_indices;

        auto const bits_to_avoid = only_exact ? exact_bits_in_use : vector<int>();

        vector<int> bit_num_dontcare(filters[0].size(), 0);
        for (auto const& filter : filters) {
            for (auto i : bits_in_use) {
                if (filter[i] == Bit::ANY) {
                    bit_num_dontcare[i]++;
                }
            }
        }

        // for (size_t i=0; i<bit_num_dontcare.size(); i++) {
        //     log()->info("dontcare[{:d}] = {:d}", i, bit_num_dontcare[i]);
        // }

        switch(mode) {
            case MinMEMode::MAX_OI: 
                tie(bit_to_remove, oi_indices) = remove_bit_oi(filters, bits_in_use, bits_to_avoid);
                break;
            case MinMEMode::BLOCKERS:
                tie(bit_to_remove, oi_indices) = remove_bit_w_blockers(filters, bits_in_use, bits_to_avoid, bit_num_dontcare, l);
                break;
        }

        // simple heuristic: choose simply by the number of ANY bits
        bool use_dontcare_heuristic = false;
        if (bit_to_remove < 0) {
            log()->info("Using ANY HEURISTIC!");
            use_dontcare_heuristic = true;
            vector<int> indices_sorted_by_dontcare = bits_in_use;
            std::sort(indices_sorted_by_dontcare.begin(), indices_sorted_by_dontcare.end(), [&bit_num_dontcare](int a, int b) {
                return bit_num_dontcare[b] > bit_num_dontcare[a];
            });
            vector<int> cur_in_use;
            for (uint i=0; i<l; i++) {
                log()->info("\tbit {:d} with {:d} ANY bits", indices_sorted_by_dontcare[i], bit_num_dontcare[indices_sorted_by_dontcare[i]]);
                cur_in_use.emplace_back(indices_sorted_by_dontcare[i]);
            }

            // leave only exact
            vector<size_t> new_exact_indices{};
            for (size_t i=0; i<filters.size(); i++) {
                bool add = true;
                if (only_exact) {
                    for (auto bit : cur_in_use) {
                        if (filters[i][bit] == Bit::ANY) {
                            add = false; break;
                        }
                    }
                }
                if (add) {
                    new_exact_indices.emplace_back(i);
                }
            }

            // check whether the heuristic stopped working
            if (new_exact_indices.size() < 0.001 * filters.size()) {
                log()->info("\tANY HEURISTIC FAILED, FOUND ONLY {:d} INDICES. REVERTING...", new_exact_indices.size());
                use_dontcare_heuristic = false;
                bit_to_remove = bit_to_remove + 100000;
            } else {
                bits_in_use = cur_in_use;
                oi_indices = find_maximal_oi_subset_indices(filters, new_exact_indices, cur_in_use);
                log()->info("\tchecking OI indices with {:d}/{:d} bits, exact {:d}, OI {:d}", bits_in_use.size(), cur_in_use.size(), new_exact_indices.size(), oi_indices.size() );
            }
        } 

        if (!use_dontcare_heuristic) {
            bits_in_use.erase(find(begin(bits_in_use), end(bits_in_use), bit_to_remove));
        }

        // bits_in_use.erase(find(begin(bits_in_use), end(bits_in_use), bit_to_remove));

        vector<int> new_indices{};
        vector<Filter> new_filters{};

        for (auto i : oi_indices) {
            new_indices.emplace_back(indices[i]);
            new_filters.emplace_back(filters[i]);
        }

        std::swap(indices, new_indices);
        std::swap(filters, new_filters);

        exact_bits_in_use = find_exact(filters, bits_in_use);

        log()->info("bit {:d} has been found; bits left: {:d}; exact bits left: {:d}; entries left: {:d}", bit_to_remove, bits_in_use.size(), exact_bits_in_use.size(), filters.size());

        if (use_dontcare_heuristic) {
            break;
        }
    }

    assert(is_oi(filters, bits_in_use));

    return make_pair(bits_in_use, indices);
}


auto p4t::find_maximal_oi_subset(vector<Filter> const& filters, vector<int> const& bits) -> vector<int> {
    vector<int> result{};

    for (auto i = 0u; i < filters.size(); i++) {
        auto intersects = false;
        for (auto j : result) {
            if (intersect(filters[j], filters[i], bits)) {
                intersects = true;
                break;
            }
        }
        if (!intersects) {
            result.emplace_back(i);
        }
    }

    return result;
}

auto p4t::find_maximal_oi_subset_indices(vector<Filter> const& filters, vector<size_t> const& indices, vector<int> const& bits) -> vector<int> {
    vector<int> result{};

    for (auto i : indices) {
        auto intersects = false;
        for (auto j : result) {
            if (intersect(filters[j], filters[i], bits)) {
                intersects = true;
                break;
            }
        }
        if (!intersects) {
            result.emplace_back(i);
        }
    }

    return result;
}

