/**
 ******************************************************************************
 * Xenia : Xbox 360 Emulator Research Project                                 *
 ******************************************************************************
 * Code RED experimental network adapter manager.                              *
 * Released under the BSD license - see LICENSE in the root for more details. *
 ******************************************************************************
 */

#ifndef XENIA_KERNEL_UTIL_NETWORK_ADAPTER_MANAGER_H_
#define XENIA_KERNEL_UTIL_NETWORK_ADAPTER_MANAGER_H_

#include <cstdint>
#include <string>
#include <vector>

namespace xe {
namespace kernel {
namespace util {

struct NetworkAdapterInfo {
  std::string name;
  std::string ipv4;
  uint32_t ipv4_network_order = 0;
  bool selected = false;
};

class NetworkAdapterManager {
 public:
  static std::vector<NetworkAdapterInfo> GetConfiguredAdapters();
};

}  // namespace util
}  // namespace kernel
}  // namespace xe

#endif  // XENIA_KERNEL_UTIL_NETWORK_ADAPTER_MANAGER_H_
