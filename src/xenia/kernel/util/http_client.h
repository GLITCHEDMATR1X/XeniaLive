/**
 ******************************************************************************
 * Xenia : Xbox 360 Emulator Research Project                                 *
 ******************************************************************************
 * Code RED minimal private-host HTTP client.                                  *
 * Released under the BSD license - see LICENSE in the root for more details. *
 ******************************************************************************
 */

#ifndef XENIA_KERNEL_UTIL_HTTP_CLIENT_H_
#define XENIA_KERNEL_UTIL_HTTP_CLIENT_H_

#include <cstdint>
#include <string>

namespace xe {
namespace kernel {
namespace util {

struct HttpResponse {
  bool ok = false;
  int status_code = 0;
  std::string body;
  std::string error;
};

HttpResponse HttpGet(const std::string& url, uint32_t timeout_ms = 1500);
HttpResponse HttpPostJson(const std::string& url, const std::string& json_body,
                          uint32_t timeout_ms = 1500);
HttpResponse HttpDelete(const std::string& url, uint32_t timeout_ms = 1500);

}  // namespace util
}  // namespace kernel
}  // namespace xe

#endif  // XENIA_KERNEL_UTIL_HTTP_CLIENT_H_
