/**
 ******************************************************************************
 * Xenia : Xbox 360 Emulator Research Project                                 *
 ******************************************************************************
 * Code RED experimental netplay helpers.                                      *
 * Released under the BSD license - see LICENSE in the root for more details. *
 ******************************************************************************
 */

#ifndef XENIA_KERNEL_UTIL_NET_UTILS_H_
#define XENIA_KERNEL_UTIL_NET_UTILS_H_

#include <array>
#include <cstdint>
#include <string>

namespace xe {
namespace kernel {
namespace util {

uint32_t ParseIPv4NetworkOrder(const std::string& value,
                               uint32_t fallback_network_order);
uint32_t GetConfiguredIPv4NetworkOrder();
std::string IPv4ToString(uint32_t network_order_ipv4);
uint64_t MakeMachineId(uint32_t network_order_ipv4, uint16_t host_order_port);
std::array<uint8_t, 6> MakeStableMac(uint32_t network_order_ipv4);

}  // namespace util
}  // namespace kernel
}  // namespace xe

#endif  // XENIA_KERNEL_UTIL_NET_UTILS_H_
