/**
 ******************************************************************************
 * Xenia : Xbox 360 Emulator Research Project                                 *
 ******************************************************************************
 * Code RED experimental netplay helpers.                                      *
 * Released under the BSD license - see LICENSE in the root for more details. *
 ******************************************************************************
 */

#include "xenia/kernel/util/net_utils.h"

#include "xenia/base/cvar.h"
#include "xenia/base/platform.h"

#ifdef XE_PLATFORM_WIN32
#define _WINSOCK_DEPRECATED_NO_WARNINGS
#include <winsock2.h>
#else
#include <arpa/inet.h>
#endif

DECLARE_string(selected_network_interface);

namespace xe {
namespace kernel {
namespace util {

uint32_t ParseIPv4NetworkOrder(const std::string& value,
                               uint32_t fallback_network_order) {
  if (value.empty()) {
    return fallback_network_order;
  }

  in_addr parsed{};
#ifdef XE_PLATFORM_WIN32
  parsed.s_addr = inet_addr(value.c_str());
  if (parsed.s_addr != INADDR_NONE) {
    return parsed.s_addr;
  }
#else
  if (inet_pton(AF_INET, value.c_str(), &parsed) == 1) {
    return parsed.s_addr;
  }
#endif
  return fallback_network_order;
}

uint32_t GetConfiguredIPv4NetworkOrder() {
  // Conservative default: local same-machine testing. Users can set
  // [Netplay].selected_network_interface to a LAN/VPN IPv4 address for a
  // real multi-PC System Link test.
  return ParseIPv4NetworkOrder(cvars::selected_network_interface,
                               htonl(INADDR_LOOPBACK));
}

std::string IPv4ToString(uint32_t network_order_ipv4) {
  in_addr addr{};
  addr.s_addr = network_order_ipv4;
  const char* result = inet_ntoa(addr);
  return result ? std::string(result) : std::string("0.0.0.0");
}

uint64_t MakeMachineId(uint32_t network_order_ipv4, uint16_t host_order_port) {
  uint64_t ip = static_cast<uint64_t>(ntohl(network_order_ipv4));
  uint64_t port = static_cast<uint64_t>(host_order_port);
  return (ip << 16) | port;
}

std::array<uint8_t, 6> MakeStableMac(uint32_t network_order_ipv4) {
  const uint32_t ip_host = ntohl(network_order_ipv4);
  return {0x02,
          0x58,
          static_cast<uint8_t>((ip_host >> 24) & 0xFF),
          static_cast<uint8_t>((ip_host >> 16) & 0xFF),
          static_cast<uint8_t>((ip_host >> 8) & 0xFF),
          static_cast<uint8_t>(ip_host & 0xFF)};
}

}  // namespace util
}  // namespace kernel
}  // namespace xe
