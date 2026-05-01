/**
 ******************************************************************************
 * Xenia : Xbox 360 Emulator Research Project                                 *
 ******************************************************************************
 * Copyright 2026 Xenia Canary. All rights reserved.                          *
 * Released under the BSD license - see LICENSE in the root for more details. *
 ******************************************************************************
 */

#ifndef XENIA_KERNEL_XSESSION_H_
#define XENIA_KERNEL_XSESSION_H_

#include <array>
#include <cstdint>
#include <optional>
#include <string>
#include <vector>

namespace xe {

class Memory;

namespace kernel {

enum SessionFlags {
  HOST = 0x01,
  PRESENCE = 0x02,
  STATS = 0x04,
  MATCHMAKING = 0x08,
  ARBITRATION = 0x10,
  PEER_NETWORK = 0x20,
  SOCIAL_MATCHMAKING_ALLOWED = 0x80,
  INVITES_DISABLED = 0x0100,
  JOIN_VIA_PRESENCE_DISABLED = 0x0200,
  JOIN_IN_PROGRESS_DISABLED = 0x0400,
  JOIN_VIA_PRESENCE_FRIENDS_ONLY = 0x0800,
  UNKNOWN = 0x1000,

  SINGLEPLAYER_WITH_STATS = PRESENCE | STATS | INVITES_DISABLED |
                            JOIN_VIA_PRESENCE_DISABLED |
                            JOIN_IN_PROGRESS_DISABLED,

  LIVE_MULTIPLAYER_STANDARD = PRESENCE | STATS | MATCHMAKING | PEER_NETWORK,
  LIVE_MULTIPLAYER_RANKED = LIVE_MULTIPLAYER_STANDARD | ARBITRATION,
  SYSTEMLINK = PEER_NETWORK,
  GROUP_LOBBY = PRESENCE | PEER_NETWORK,
  GROUP_GAME = STATS | MATCHMAKING | PEER_NETWORK,

  SYSTEMLINK_FEATURES = HOST | SYSTEMLINK,
  LIVE_FEATURES = PRESENCE | STATS | MATCHMAKING | ARBITRATION
};

inline bool IsOfflineSession(const SessionFlags flags) { return !flags; }

inline bool IsXboxLiveSession(const SessionFlags flags) {
  return !IsOfflineSession(flags) && flags & SessionFlags::LIVE_FEATURES;
}

inline bool IsSystemlinkSession(const SessionFlags flags) {
  return !IsOfflineSession(flags) && (flags & SessionFlags::SYSTEMLINK);
}

inline bool IsNetworkSession(const SessionFlags flags) {
  return IsXboxLiveSession(flags) || IsSystemlinkSession(flags);
}

struct XSessionPlayer {
  uint64_t xuid = 0;
  bool private_slot = false;
};

struct XSessionDetails {
  uint64_t id = 0;
  uint32_t title_id = 0;
  uint32_t session_ptr = 0;
  uint32_t flags = 0;
  uint32_t public_slots = 0;
  uint32_t private_slots = 0;
  uint32_t host_address = 0;
  uint16_t port = 3074;
  std::array<uint8_t, 6> mac = {};
  std::array<uint8_t, 16> key_exchange = {};
  bool started = false;
  bool advertised = true;
  std::vector<XSessionPlayer> players;

  uint32_t filled_public_slots() const;
  uint32_t filled_private_slots() const;
  uint32_t open_public_slots() const;
  uint32_t open_private_slots() const;
};

struct XSessionCreateParams {
  uint32_t title_id = 0;
  uint32_t session_ptr = 0;
  uint32_t flags = 0;
  uint32_t public_slots = 0;
  uint32_t private_slots = 0;
  uint64_t host_xuid = 0;
  uint32_t host_address = 0;
  uint16_t port = 3074;
  std::array<uint8_t, 6> mac = {};
};

class XSessionRegistry {
 public:
  XSessionDetails CreateHostSession(const XSessionCreateParams& params);
  bool DeleteSession(uint32_t session_ptr);
  bool JoinLocalUsers(uint32_t session_ptr, const std::vector<uint64_t>& xuids,
                      const std::vector<bool>& private_slots);
  bool LeaveLocalUsers(uint32_t session_ptr, const std::vector<uint64_t>& xuids);
  bool StartSession(uint32_t session_ptr);
  bool EndSession(uint32_t session_ptr);
  std::optional<XSessionDetails> GetSession(uint32_t session_ptr) const;
  std::vector<XSessionDetails> Search(uint32_t title_id,
                                      uint32_t max_results) const;
  void Clear();

 private:
  std::vector<XSessionDetails> sessions_;
};

uint64_t MakeCodeRedSessionId(uint32_t title_id, uint32_t session_ptr,
                              uint32_t flags, uint16_t port);
std::string FormatCodeRedSessionId(uint64_t session_id);
std::array<uint8_t, 16> MakeCodeRedSessionKey(uint64_t session_id,
                                               uint32_t host_address,
                                               uint16_t port);
std::string FormatCodeRedSessionKey(
    const std::array<uint8_t, 16>& key_exchange);
std::array<uint8_t, 16> ParseCodeRedSessionKey(const std::string& hex);

struct XSessionSearchFillResult {
  bool wrote = false;
  uint32_t result_count = 0;
  uint32_t bytes_written = 0;
  uint32_t result_buffer_ptr = 0;
  std::string note;
};

struct XSessionDetailsFillResult {
  bool wrote = false;
  uint32_t bytes_written = 0;
  uint32_t details_buffer_ptr = 0;
  std::string note;
};

constexpr uint32_t kCodeRedXSessionInfoSize = 0x3C;
constexpr uint32_t kCodeRedXSessionSearchResultHeaderSize = 0x8;
constexpr uint32_t kCodeRedXSessionSearchResultSize = 0x5C;
constexpr uint32_t kCodeRedXSessionLocalDetailsSize = 0x80;

XSessionSearchFillResult FillCodeRedSessionSearchResults(
    Memory* memory, uint32_t result_buffer_ptr, uint32_t result_buffer_size,
    const std::vector<XSessionDetails>& sessions);

std::string DescribeCodeRedSessionSearchLayout();

XSessionDetailsFillResult FillCodeRedSessionDetails(
    Memory* memory, uint32_t details_buffer_ptr, uint32_t details_buffer_size,
    const XSessionDetails& session, uint64_t nonce = 0);

std::string DescribeCodeRedSessionDetailsLayout();

}  // namespace kernel
}  // namespace xe

#endif  // XENIA_KERNEL_XSESSION_H_
