#include "common.h"

auto p4t::log() -> std::shared_ptr<spdlog::logger> const& {
    static auto initialized = false;
    static std::shared_ptr<spdlog::logger> logger{};

    if (!initialized) {
        logger = spdlog::basic_logger_mt("logger", "p4t_native.log");
        logger->flush_on(spdlog::level::info);
        initialized = true;
    }
    return logger;
}
