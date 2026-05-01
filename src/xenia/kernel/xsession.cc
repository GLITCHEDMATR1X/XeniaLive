/**
 ******************************************************************************
 * Xenia : Xbox 360 Emulator Research Project                                 *
 ******************************************************************************
 * Code RED experimental session registry.                                    *
 * Released under the BSD license - see LICENSE in the root for more details. *
 ******************************************************************************
 */

#include "xenia/kernel/xsession.h"

#include <algorithm>
#include <cctype>
#include <cstring>
#include <iomanip>
#include <sstream>

#include "xenia/base/memory.h"
#include "xenia/memory.h"

namespace xe {
namespace kernel {

namespace {
uint64_t Mix64(uint64_t value) {
  value ^= value >> 33;
  value *= 0xff51afd7ed558ccdULL;
  value ^= value >> 33;
  value *= 0xc4ceb9fe1a85ec53ULL;
  value ^= value >> 33;
  return value;
}
}  // namespace

uint32_t XSessionDetails::filled_public_slots() const {
  uint32_t count = 0;
  for (const auto& player : players) {
    if (!player.private_slot) {
      ++count;
    }
  }
  return count;
}

uint32_t XSessionDetails::filled_private_slots() const {
  uint32_t count = 0;
  for (const auto& player : players) {
    if (player.private_slot) {
      ++count;
    }
  }
  return count;
}

uint32_t XSessionDetails::open_public_slots() const {
  const uint32_t filled = filled_public_slots();
  return filled >= public_slots ? 0 : public_slots - filled;
}

uint32_t XSessionDetails::open_private_slots() const {
  const uint32_t filled = filled_private_slots();
  return filled >= private_slots ? 0 : private_slots - filled;
}

uint64_t MakeCodeRedSessionId(uint32_t title_id, uint32_t session_ptr,
                              uint32_t flags, uint16_t port) {
  uint64_t seed = static_cast<uint64_t>(title_id) << 32;
  seed ^= static_cast<uint64_t>(session_ptr);
  seed ^= static_cast<uint64_t>(flags) << 17;
  seed ^= static_cast<uint64_t>(port) << 48;
  return Mix64(seed);
}

std::string FormatCodeRedSessionId(uint64_t session_id) {
  std::ostringstream out;
  out << std::uppercase << std::hex << std::setfill('0') << std::setw(16)
      << session_id;
  return out.str();
}

std::array<uint8_t, 16> MakeCodeRedSessionKey(uint64_t session_id,
                                               uint32_t host_address,
                                               uint16_t port) {
  std::array<uint8_t, 16> key = {};
  const uint64_t high = Mix64(session_id ^ 0xC0DEF00D36000000ULL);
  const uint64_t low = Mix64((static_cast<uint64_t>(host_address) << 32) |
                             static_cast<uint64_t>(port) ^ session_id);
  for (size_t i = 0; i < 8; ++i) {
    key[i] = static_cast<uint8_t>((high >> ((7 - i) * 8)) & 0xFF);
    key[8 + i] = static_cast<uint8_t>((low >> ((7 - i) * 8)) & 0xFF);
  }
  return key;
}

std::string FormatCodeRedSessionKey(
    const std::array<uint8_t, 16>& key_exchange) {
  std::ostringstream out;
  out << std::uppercase << std::hex << std::setfill('0');
  for (uint8_t byte : key_exchange) {
    out << std::setw(2) << static_cast<uint32_t>(byte);
  }
  return out.str();
}

std::array<uint8_t, 16> ParseCodeRedSessionKey(const std::string& hex) {
  std::array<uint8_t, 16> key = {};
  if (hex.size() < 32) {
    return key;
  }
  for (size_t i = 0; i < key.size(); ++i) {
    const char hi = hex[i * 2];
    const char lo = hex[i * 2 + 1];
    if (!std::isxdigit(static_cast<unsigned char>(hi)) ||
        !std::isxdigit(static_cast<unsigned char>(lo))) {
      return {};
    }
    key[i] = static_cast<uint8_t>(std::stoul(hex.substr(i * 2, 2), nullptr, 16));
  }
  return key;
}


XSessionDetails XSessionRegistry::CreateHostSession(
    const XSessionCreateParams& params) {
  DeleteSession(params.session_ptr);

  XSessionDetails session;
  session.id = MakeCodeRedSessionId(params.title_id, params.session_ptr,
                                    params.flags, params.port);
  session.title_id = params.title_id;
  session.session_ptr = params.session_ptr;
  session.flags = params.flags | SessionFlags::HOST;
  session.public_slots = params.public_slots;
  session.private_slots = params.private_slots;
  session.host_address = params.host_address;
  session.port = params.port;
  session.mac = params.mac;
  session.key_exchange =
      MakeCodeRedSessionKey(session.id, session.host_address, session.port);
  session.advertised = IsNetworkSession(static_cast<SessionFlags>(params.flags));
  if (params.host_xuid) {
    session.players.push_back({params.host_xuid, false});
  }

  sessions_.push_back(session);
  return session;
}

bool XSessionRegistry::DeleteSession(uint32_t session_ptr) {
  const auto old_size = sessions_.size();
  sessions_.erase(std::remove_if(sessions_.begin(), sessions_.end(),
                                 [session_ptr](const XSessionDetails& item) {
                                   return item.session_ptr == session_ptr;
                                 }),
                  sessions_.end());
  return sessions_.size() != old_size;
}

bool XSessionRegistry::JoinLocalUsers(uint32_t session_ptr,
                                      const std::vector<uint64_t>& xuids,
                                      const std::vector<bool>& private_slots) {
  for (auto& session : sessions_) {
    if (session.session_ptr != session_ptr) {
      continue;
    }

    for (size_t i = 0; i < xuids.size(); ++i) {
      const uint64_t xuid = xuids[i];
      const bool private_slot = i < private_slots.size() ? private_slots[i] : false;
      auto existing = std::find_if(session.players.begin(), session.players.end(),
                                   [xuid](const XSessionPlayer& player) {
                                     return player.xuid == xuid;
                                   });
      if (existing == session.players.end()) {
        session.players.push_back({xuid, private_slot});
      } else {
        existing->private_slot = private_slot;
      }
    }
    return true;
  }
  return false;
}

bool XSessionRegistry::LeaveLocalUsers(uint32_t session_ptr,
                                       const std::vector<uint64_t>& xuids) {
  for (auto& session : sessions_) {
    if (session.session_ptr != session_ptr) {
      continue;
    }
    session.players.erase(
        std::remove_if(session.players.begin(), session.players.end(),
                       [&xuids](const XSessionPlayer& player) {
                         return std::find(xuids.begin(), xuids.end(),
                                          player.xuid) != xuids.end();
                       }),
        session.players.end());
    return true;
  }
  return false;
}

bool XSessionRegistry::StartSession(uint32_t session_ptr) {
  for (auto& session : sessions_) {
    if (session.session_ptr == session_ptr) {
      session.started = true;
      return true;
    }
  }
  return false;
}

bool XSessionRegistry::EndSession(uint32_t session_ptr) {
  for (auto& session : sessions_) {
    if (session.session_ptr == session_ptr) {
      session.started = false;
      return true;
    }
  }
  return false;
}

std::optional<XSessionDetails> XSessionRegistry::GetSession(
    uint32_t session_ptr) const {
  for (const auto& session : sessions_) {
    if (session.session_ptr == session_ptr) {
      return session;
    }
  }
  return std::nullopt;
}

std::vector<XSessionDetails> XSessionRegistry::Search(uint32_t title_id,
                                                       uint32_t max_results) const {
  std::vector<XSessionDetails> matches;
  for (const auto& session : sessions_) {
    if (session.title_id != title_id || !session.advertised) {
      continue;
    }
    matches.push_back(session);
    if (matches.size() >= max_results) {
      break;
    }
  }
  return matches;
}

void XSessionRegistry::Clear() { sessions_.clear(); }

namespace {

void StoreBe16(uint8_t* base, uint32_t offset, uint16_t value) {
  xe::store_and_swap<uint16_t>(base + offset, value);
}

void StoreBe32(uint8_t* base, uint32_t offset, uint32_t value) {
  xe::store_and_swap<uint32_t>(base + offset, value);
}

void StoreBe64(uint8_t* base, uint32_t offset, uint64_t value) {
  xe::store_and_swap<uint64_t>(base + offset, value);
}

void StoreZeroBytes(uint8_t* base, uint32_t offset, uint32_t size) {
  std::memset(base + offset, 0, size);
}

void StoreCodeRedXnAddr(uint8_t* base, const XSessionDetails& session) {
  // XNADDR, 0x24 bytes. The IP fields are stored as guest-visible big-endian
  // values. This mirrors the XNADDR layout used by the netplay fork while
  // avoiding a hard dependency on its heavier xnet.h integration layer.
  const uint32_t host_address = session.host_address;
  StoreBe32(base, 0x00, host_address);  // ina
  StoreBe32(base, 0x04, host_address);  // inaOnline for private-host mode
  StoreBe16(base, 0x08, session.port);  // wPortOnline
  std::memcpy(base + 0x0A, session.mac.data(), session.mac.size());

  // SGADDR abOnline, 0x14 bytes. Keep it deterministic and conservative: IP,
  // a stable pseudo SPI, session id as the machine/xbox id, and Xbox360-like
  // platform value. RDR mainly needs the session id + XNADDR route to be stable.
  StoreBe32(base, 0x10, host_address);
  StoreBe32(base, 0x14, static_cast<uint32_t>(session.id & 0xFFFFFFFFu));
  StoreBe64(base, 0x18, session.id);
  base[0x20] = 1;
  StoreZeroBytes(base, 0x21, 3);
}

void StoreCodeRedXSessionInfo(uint8_t* base, const XSessionDetails& session) {
  // XSESSION_INFO, 0x3C bytes:
  //   XNKID   sessionID       0x00..0x07
  //   XNADDR  hostAddress     0x08..0x2B
  //   XNKEY   keyExchangeKey  0x2C..0x3B
  StoreBe64(base, 0x00, session.id);
  StoreCodeRedXnAddr(base + 0x08, session);

  const auto fallback_key =
      MakeCodeRedSessionKey(session.id, session.host_address, session.port);
  const auto& key = std::any_of(session.key_exchange.begin(),
                                session.key_exchange.end(),
                                [](uint8_t byte) { return byte != 0; })
                        ? session.key_exchange
                        : fallback_key;
  std::memcpy(base + 0x2C, key.data(), key.size());
}

void StoreCodeRedXSessionSearchResult(uint8_t* base,
                                      const XSessionDetails& session) {
  // XSESSION_SEARCHRESULT, 0x5C bytes.
  StoreCodeRedXSessionInfo(base, session);
  StoreBe32(base, 0x3C, session.open_public_slots());
  StoreBe32(base, 0x40, session.open_private_slots());
  StoreBe32(base, 0x44, session.filled_public_slots());
  StoreBe32(base, 0x48, session.filled_private_slots());
  StoreBe32(base, 0x4C, 0);  // properties_count
  StoreBe32(base, 0x50, 0);  // contexts_count
  StoreBe32(base, 0x54, 0);  // properties_ptr
  StoreBe32(base, 0x58, 0);  // contexts_ptr
}

}  // namespace

XSessionSearchFillResult FillCodeRedSessionSearchResults(
    Memory* memory, uint32_t result_buffer_ptr, uint32_t result_buffer_size,
    const std::vector<XSessionDetails>& sessions) {
  XSessionSearchFillResult result;
  result.result_buffer_ptr = result_buffer_ptr;
  if (!memory || !result_buffer_ptr) {
    result.note = "missing result buffer";
    return result;
  }
  if (result_buffer_size < kCodeRedXSessionSearchResultHeaderSize) {
    result.note = "result buffer too small";
    return result;
  }

  const uint32_t capacity =
      (result_buffer_size - kCodeRedXSessionSearchResultHeaderSize) /
      kCodeRedXSessionSearchResultSize;
  const uint32_t count =
      static_cast<uint32_t>(std::min<size_t>(sessions.size(), capacity));
  const uint32_t bytes_to_clear =
      kCodeRedXSessionSearchResultHeaderSize +
      capacity * kCodeRedXSessionSearchResultSize;
  uint8_t* buffer = memory->TranslateVirtual<uint8_t*>(result_buffer_ptr);
  std::memset(buffer, 0, bytes_to_clear);

  StoreBe32(buffer, 0x00, count);
  StoreBe32(buffer, 0x04,
            result_buffer_ptr + kCodeRedXSessionSearchResultHeaderSize);

  for (uint32_t i = 0; i < count; ++i) {
    StoreCodeRedXSessionSearchResult(
        buffer + kCodeRedXSessionSearchResultHeaderSize +
            i * kCodeRedXSessionSearchResultSize,
        sessions[i]);
  }

  result.wrote = true;
  result.result_count = count;
  result.bytes_written = kCodeRedXSessionSearchResultHeaderSize +
                         count * kCodeRedXSessionSearchResultSize;
  result.note = "XSESSION_SEARCHRESULT header=0x8 result=0x5C";
  return result;
}

std::string DescribeCodeRedSessionSearchLayout() {
  std::ostringstream out;
  out << "XSESSION_SEARCHRESULT_HEADER=0x" << std::hex
      << kCodeRedXSessionSearchResultHeaderSize
      << " {count, results_ptr}; XSESSION_SEARCHRESULT=0x"
      << kCodeRedXSessionSearchResultSize
      << " {XSESSION_INFO=0x" << kCodeRedXSessionInfoSize
      << ", open/filled public/private slots, property/context counts+ptrs}";
  return out.str();
}

XSessionDetailsFillResult FillCodeRedSessionDetails(
    Memory* memory, uint32_t details_buffer_ptr, uint32_t details_buffer_size,
    const XSessionDetails& session, uint64_t nonce) {
  XSessionDetailsFillResult result;
  result.details_buffer_ptr = details_buffer_ptr;
  if (!memory || !details_buffer_ptr) {
    result.note = "missing details buffer";
    return result;
  }
  if (details_buffer_size < kCodeRedXSessionLocalDetailsSize) {
    result.note = "details buffer too small";
    return result;
  }

  uint8_t* buffer = memory->TranslateVirtual<uint8_t*>(details_buffer_ptr);
  std::memset(buffer, 0, details_buffer_size);

  // XSESSION_LOCAL_DETAILS, 0x80 bytes. GameType/GameMode are left zero until
  // the per-title SPA/context layer is ported.
  StoreBe32(buffer, 0x00, 0);  // UserIndexHost
  StoreBe32(buffer, 0x04, 0);  // GameType
  StoreBe32(buffer, 0x08, 0);  // GameMode
  StoreBe32(buffer, 0x0C, session.flags);
  StoreBe32(buffer, 0x10, session.public_slots);
  StoreBe32(buffer, 0x14, session.private_slots);
  StoreBe32(buffer, 0x18, session.open_public_slots());
  StoreBe32(buffer, 0x1C, session.open_private_slots());
  StoreBe32(buffer, 0x20, session.filled_public_slots() +
                              session.filled_private_slots());
  StoreBe32(buffer, 0x24, session.filled_public_slots() +
                              session.filled_private_slots());
  StoreBe32(buffer, 0x28, session.started ? 2 : 0);  // LOBBY/INGAME-ish
  StoreBe64(buffer, 0x2C, nonce ? nonce : session.id);
  StoreCodeRedXSessionInfo(buffer + 0x34, session);
  StoreBe64(buffer, 0x70, session.id);
  StoreBe32(buffer, 0x78, 0);  // SessionMembers_ptr

  result.wrote = true;
  result.bytes_written = kCodeRedXSessionLocalDetailsSize;
  result.note = "XSESSION_LOCAL_DETAILS=0x80";
  return result;
}

std::string DescribeCodeRedSessionDetailsLayout() {
  std::ostringstream out;
  out << "XSESSION_LOCAL_DETAILS=0x" << std::hex
      << kCodeRedXSessionLocalDetailsSize
      << " with embedded XSESSION_INFO at +0x34";
  return out.str();
}

}  // namespace kernel
}  // namespace xe
