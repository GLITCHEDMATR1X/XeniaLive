/**
 ******************************************************************************
 * Xenia : Xbox 360 Emulator Research Project                                 *
 ******************************************************************************
 * Code RED experimental netplay foundation.                                   *
 * Released under the BSD license - see LICENSE in the root for more details. *
 ******************************************************************************
 */

#ifndef XENIA_KERNEL_XLIVEAPI_H_
#define XENIA_KERNEL_XLIVEAPI_H_

#include <cstdint>
#include <optional>
#include <string>
#include <vector>

#include "xenia/kernel/xsession.h"

namespace xe {
namespace kernel {

class XLiveAPI {
 public:
  enum class NetworkMode : uint32_t {
    Offline = 0,
    SystemLink = 1,
    PrivateHost = 2,
    SinglePlayerHost = 3,
  };

  enum class InitState {
    Success,
    Failed,
    Pending,
  };

  XLiveAPI();
  ~XLiveAPI();

  void Init();
  InitState GetInitState() const;

  void SetNetworkMode(uint32_t mode);
  uint32_t GetNetworkMode() const;
  bool IsOfflineMode() const;
  bool IsSystemLinkMode() const;
  bool IsPrivateHostMode() const;
  bool IsSinglePlayerHostMode() const;
  bool IsSinglePlayerHostEnabled() const;
  bool IsNetworkEnabled() const;

  static std::string GetApiAddress();
  void SetAPIAddress(const std::string& address);

  uint16_t GetPlayerPort() const;
  void SetPlayerPort(uint16_t port);

  XSessionDetails CreateHostSession(uint32_t title_id, uint32_t session_ptr,
                                    uint32_t flags, uint32_t public_slots,
                                    uint32_t private_slots, uint64_t host_xuid,
                                    uint32_t host_address);
  XSessionDetails EnsureSinglePlayerHostSession(uint32_t title_id,
                                                uint64_t host_xuid = 0,
                                                uint32_t host_address = 0);
  bool DeleteSession(uint32_t session_ptr);
  bool JoinLocalUsers(uint32_t session_ptr, const std::vector<uint64_t>& xuids,
                      const std::vector<bool>& private_slots);
  bool LeaveLocalUsers(uint32_t session_ptr, const std::vector<uint64_t>& xuids);
  bool StartSession(uint32_t session_ptr);
  bool EndSession(uint32_t session_ptr);
  std::optional<XSessionDetails> GetSession(uint32_t session_ptr) const;
  std::vector<XSessionDetails> SearchSessions(uint32_t title_id,
                                              uint32_t max_results) const;
  std::optional<XSessionDetails> GetSessionDetails(uint32_t title_id,
                                                   uint64_t session_id) const;

  bool RegisterPlayer(uint64_t xuid, uint32_t title_id,
                      uint32_t host_address = 0) const;
  bool PublishSession(const XSessionDetails& session,
                      const char* reason = "update") const;
  bool JoinRemoteSession(uint32_t title_id, uint64_t session_id,
                         const std::vector<uint64_t>& xuids) const;
  bool LeaveRemoteSession(uint32_t title_id, uint64_t session_id,
                          const std::vector<uint64_t>& xuids) const;
  bool DeleteRemoteSession(uint32_t title_id, uint64_t session_id) const;
  bool PostQos(const XSessionDetails& session, const std::string& payload) const;

  std::string BuildPlayerPostPath() const;
  std::string BuildSessionPostPath(uint32_t title_id) const;
  std::string BuildSessionPath(uint32_t title_id, uint64_t session_id) const;
  std::string BuildSessionSearchPath(uint32_t title_id) const;
  std::string BuildSessionDetailsPath(uint32_t title_id,
                                      uint64_t session_id) const;
  std::string BuildSessionJoinPath(uint32_t title_id,
                                   uint64_t session_id) const;
  std::string BuildSessionLeavePath(uint32_t title_id,
                                    uint64_t session_id) const;
  std::string BuildQosPath(uint32_t title_id, uint64_t session_id) const;

 private:
  bool ShouldUsePrivateHost() const;
  std::vector<XSessionDetails> SearchRemoteSessions(uint32_t title_id,
                                                    uint32_t max_results) const;
  std::optional<XSessionDetails> GetRemoteSessionDetails(
      uint32_t title_id, uint64_t session_id) const;

  InitState init_state_ = InitState::Pending;
  uint32_t network_mode_ = 1;
  uint16_t player_port_ = 3074;
  XSessionRegistry sessions_;
};

XLiveAPI& GetCodeRedXLiveAPI();

}  // namespace kernel
}  // namespace xe

#endif  // XENIA_KERNEL_XLIVEAPI_H_
