/**
 ******************************************************************************
 * Xenia : Xbox 360 Emulator Research Project                                 *
 ******************************************************************************
 * Code RED experimental network adapter manager.                              *
 * Released under the BSD license - see LICENSE in the root for more details. *
 ******************************************************************************
 */

#include "xenia/kernel/util/network_adapter_manager.h"

#include "xenia/kernel/util/net_utils.h"

namespace xe {
namespace kernel {
namespace util {

std::vector<NetworkAdapterInfo> NetworkAdapterManager::GetConfiguredAdapters() {
  const uint32_t ip = GetConfiguredIPv4NetworkOrder();
  return {{"CodeRED configured adapter", IPv4ToString(ip), ip, true}};
}

}  // namespace util
}  // namespace kernel
}  // namespace xe
