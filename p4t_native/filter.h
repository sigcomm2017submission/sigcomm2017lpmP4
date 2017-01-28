#ifndef FILTER_H
#define FILTER_H

#include <iterator>
#include <algorithm>

#include "common.h"

namespace p4t {

enum class Bit {
    ONE, ZERO, ANY 
};

class Filter {
public:
    Filter() = default;

    Filter(bitarray const& value, bitarray const& mask)
        : value_(value), mask_(mask), width_(value.size()) {
    }

    Filter(py::object svmr)
        : value_{}, mask_{}, width_{size_t(len(svmr.attr("value")))} {
        assert(width_ <= value_.size());

        for (auto i = 0u; i < width_; i++) {
            value_[i] = py::extract<bool>(svmr.attr("value")[i]);
            mask_[i] = py::extract<bool>(svmr.attr("mask")[i]);
        }
    }

    auto const& get_value() const {
        return value_;
    }

    auto const& get_mask() const {
        return mask_;
    }

    auto size() const {
        return width_;
    }

    auto operator[](size_t i) const -> Bit {
        return mask_[i] ? (value_[i] ? Bit::ONE : Bit::ZERO) : Bit::ANY;
    }

private:
    bitarray value_;
    bitarray mask_;
    size_t width_;
};

template<class Bits>
inline auto intersect(Filter const& lhs, Filter const& rhs, Bits const& bits) {
    assert(lhs.size() == rhs.size());

    for (auto i : bits) {
        if (rhs.get_mask()[i] && lhs.get_mask()[i] && rhs.get_value()[i] != lhs.get_value()[i]) {
            return false;
        }
    }

    return true;
}


}

#endif
