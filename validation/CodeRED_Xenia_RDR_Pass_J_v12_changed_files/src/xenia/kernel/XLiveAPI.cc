/**
 ******************************************************************************
 * Xenia : Xbox 360 Emulator Research Project                                 *
 ******************************************************************************
 * Code RED experimental netplay foundation.                                   *
 * Released under the BSD license - see LICENSE in the root for more details. *
 ******************************************************************************
 */

#include "xenia/kernel/XLiveAPI.h"

#include <algorithm>
#include <array>
#include <cctype>
#include <iomanip>
#include <set>
#include <sstream>

#include "xenia/base/cvar.h"
#include "xenia/base/logging.h"
#include "xenia/kernel/util/http_client.h"
#include "xenia/kernel/util/net_utils.h"

DEFINE_int32(network_mode, 1,
             "Code RED netplay mode: 0=Offline, 1=LAN/System Link, "
             "2=Private Live-like host.",
             "Netplay");
DEFINE_string(netplay_api_address, "http://127.0.0.1:36000/",
              "Private Live-like host API address for experimental netplay.",
              "Netplay");
DEFINE_string(selected_network_interface, "",
              "Preferred LAN/VPN IPv4 address for System Link. Leave empty to "
              "fall back to loopback for local testing.",
              "Netplay");
DEFINE_bool(upnp, true,
            "Allow future netplay code to request UPnP mappings when a private "
            "host mode is active.",
            "Netplay");
DEFINE_bool(xhttp, true,
            "Enable XHTTP/private-service calls for experimental netplay.",
            "Netplay");
DEFINE_bool(net_logging, true,
            "Verbose Code RED netplay/XNet logging for RDR System Link tests.",
            "Netplay");
DEFINE_bool(netplay_udp_bootstrap, true,
            "Inject a tiny local UDP discovery bootstrap packet when a System "
            "Link/private-host receive poll would otherwise return WSAEWOULDBLOCK.",
            "Netplay");
DEFINE_int32(netplay_http_timeout_ms, 1500,
             "Timeout for Code RED private-host HTTP calls in milliseconds.",
             "Netplay");

namespace xe {
namespace kernel {

namespace {
std::string FormatTitleId(uint32_t title_id) {
  std::ostringstream out;
  out << std::uppercase << std::hex << std::setfill('0') << std::setw(8)
      << title_id;
  return out.str();
}

std::string JoinApiPath(const std::string& path) {
  std::string api = XLiveAPI::GetApiAddress();
  while (!api.empty() && api.back() == '/') {
    api.pop_back();
  }
  return api + path;
}

std::string JsonEscape(const std::string& value) {
  std::string escaped;
  escaped.reserve(value.size());
  for (char ch : value) {
    switch (ch) {
      case '\\':
        escaped += "\\\\";
        break;
      case '"':
        escaped += "\\\"";
        break;
      case '\n':
        escaped += "\\n";
        break;
      case '\r':
        escaped += "\\r";
        break;
      case '\t':
        escaped += "\\t";
        break;
      default:
        escaped += ch;
        break;
    }
  }
  return escaped;
}

std::string Hex64(uint64_t value) {
  std::ostringstream out;
  out << std::uppercase << std::hex << std::setfill('0') << std::setw(16)
      << value;
  return out.str();
}

std::string MacToString(const std::array<uint8_t, 6>& mac) {
  std::ostringstream out;
  for (size_t i = 0; i < mac.size(); ++i) {
    if (i) {
      out << ":";
    }
    out << std::uppercase << std::hex << std::setfill('0') << std::setw(2)
        << static_cast<uint32_t>(mac[i]);
  }
  return out.str();
}

std::string BuildXuidArray(const std::vector<uint64_t>& xuids) {
  std::ostringstream out;
  out << "[";
  for (size_t i = 0; i < xuids.size(); ++i) {
    if (i) {
      out << ",";
    }
    out << "\"" << Hex64(xuids[i]) << "\"";
  }
  out << "]";
  return out.str();
}

std::string BuildSessionJson(const XSessionDetails& session,
                             const char* reason) {
  std::ostringstream body;
  body << "{";
  body << "\"sessionId\":\"" << FormatCodeRedSessionId(session.id)
       << "\",";
  body << "\"id\":\"" << FormatCodeRedSessionId(session.id) << "\",";
  body << "\"flags\":" << session.flags << ",";
  body << "\"publicSlotsCount\":" << session.public_slots << ",";
  body << "\"privateSlotsCount\":" << session.private_slots << ",";
  body << "\"openPublicSlotsCount\":" << session.open_public_slots() << ",";
  body << "\"openPrivateSlotsCount\":" << session.open_private_slots() << ",";
  body << "\"filledPublicSlotsCount\":" << session.filled_public_slots()
       << ",";
  body << "\"filledPrivateSlotsCount\":" << session.filled_private_slots()
       << ",";
  body << "\"hostAddress\":\"" << util::IPv4ToString(session.host_address)
       << "\",";
  body << "\"macAddress\":\"" << MacToString(session.mac) << "\",";
  body << "\"keyExchangeKey\":\""
       << FormatCodeRedSessionKey(session.key_exchange) << "\",";
  body << "\"port\":" << session.port << ",";
  body << "\"started\":" << (session.started ? "true" : "false") << ",";
  body << "\"advertised\":" << (session.advertised ? "true" : "false")
       << ",";
  body << "\"reason\":\"" << JsonEscape(reason ? reason : "update")
       << "\",";
  body << "\"players\":[";
  for (size_t i = 0; i < session.players.size(); ++i) {
    if (i) {
      body << ",";
    }
    body << "{\"xuid\":\"" << Hex64(session.players[i].xuid)
         << "\",\"privateSlot\":"
         << (session.players[i].private_slot ? "true" : "false") << "}";
  }
  body << "]";
  body << "}";
  return body.str();
}

std::string ExtractJsonString(const std::string& object,
                              const std::string& key) {
  const std::string marker = "\"" + key + "\"";
  size_t pos = object.find(marker);
  if (pos == std::string::npos) {
    return "";
  }
  pos = object.find(':', pos + marker.size());
  if (pos == std::string::npos) {
    return "";
  }
  pos = object.find('"', pos + 1);
  if (pos == std::string::npos) {
    return "";
  }
  const size_t start = pos + 1;
  size_t end = start;
  while (end < object.size()) {
    if (object[end] == '"' && object[end - 1] != '\\') {
      break;
    }
    ++end;
  }
  return end < object.size() ? object.substr(start, end - start) : "";
}

uint64_t ExtractJsonUInt(const std::string& object, const std::string& key,
                         uint64_t fallback = 0) {
  const std::string marker = "\"" + key + "\"";
  size_t pos = object.find(marker);
  if (pos == std::string::npos) {
    return fallback;
  }
  pos = object.find(':', pos + marker.size());
  if (pos == std::string::npos) {
    return fallback;
  }
  ++pos;
  while (pos < object.size() && std::isspace(static_cast<unsigned char>(object[pos]))) {
    ++pos;
  }
  if (pos < object.size() && object[pos] == '"') {
    const std::string text = ExtractJsonString(object, key);
    if (!text.empty()) {
      return std::stoull(text, nullptr, 16);
    }
    return fallback;
  }
  size_t end = pos;
  while (end < object.size() && std::isdigit(static_cast<unsigned char>(object[end]))) {
    ++end;
  }
  if (end == pos) {
    return fallback;
  }
  return std::stoull(object.substr(pos, end - pos), nullptr, 10);
}

bool ExtractJsonBool(const std::string& object, const std::string& key,
                     bool fallback = false) {
  const std::string marker = "\"" + key + "\"";
  size_t pos = object.find(marker);
  if (pos == std::string::npos) {
    return fallback;
  }
  pos = object.find(':', pos + marker.size());
  if (pos == std::string::npos) {
    return fallback;
  }
  ++pos;
  while (pos < object.size() &&
         std::isspace(static_cast<unsigned char>(object[pos]))) {
    ++pos;
  }
  if (object.compare(pos, 4, "true") == 0) {
    return true;
  }
  if (object.compare(pos, 5, "false") == 0) {
    return false;
  }
  return fallback;
}

std::string ExtractJsonArray(const std::string& object,
                             const std::string& key) {
  const std::string marker = "\"" + key + "\"";
  size_t pos = object.find(marker);
  if (pos == std::string::npos) {
    return "";
  }
  pos = object.find(':', pos + marker.size());
  if (pos == std::string::npos) {
    return "";
  }
  pos = object.find('[', pos + 1);
  if (pos == std::string::npos) {
    return "";
  }
  const size_t start = pos;
  int depth = 0;
  bool in_string = false;
  bool escaped = false;
  for (; pos < object.size(); ++pos) {
    const char ch = object[pos];
    if (in_string) {
      if (escaped) {
        escaped = false;
      } else if (ch == '\\') {
        escaped = true;
      } else if (ch == '"') {
        in_string = false;
      }
      continue;
    }
    if (ch == '"') {
      in_string = true;
      continue;
    }
    if (ch == '[') {
      ++depth;
    } else if (ch == ']') {
      --depth;
      if (depth == 0) {
        return object.substr(start, pos - start + 1);
      }
    }
  }
  return "";
}

std::vector<std::string> ExtractJsonObjects(const std::string& body) {
  std::vector<std::string> objects;
  int depth = 0;
  size_t object_start = std::string::npos;
  bool in_string = false;
  bool escaped = false;

  for (size_t i = 0; i < body.size(); ++i) {
    const char ch = body[i];
    if (in_string) {
      if (escaped) {
        escaped = false;
      } else if (ch == '\\') {
        escaped = true;
      } else if (ch == '"') {
        in_string = false;
      }
      continue;
    }
    if (ch == '"') {
      in_string = true;
      continue;
    }
    if (ch == '{') {
      if (depth == 0) {
        object_start = i;
      }
      ++depth;
    } else if (ch == '}') {
      --depth;
      if (depth == 0 && object_start != std::string::npos) {
        objects.push_back(body.substr(object_start, i - object_start + 1));
        object_start = std::string::npos;
      }
    }
  }
  return objects;
}

std::array<uint8_t, 6> ParseMacOrMakeStable(const std::string& mac_text,
                                            uint32_t host_address) {
  std::array<uint8_t, 6> mac = util::MakeStableMac(host_address);
  if (mac_text.empty()) {
    return mac;
  }

  std::istringstream in(mac_text);
  std::string part;
  size_t index = 0;
  while (std::getline(in, part, ':') && index < mac.size()) {
    mac[index++] = static_cast<uint8_t>(std::stoul(part, nullptr, 16));
  }
  return mac;
}

XSessionDetails ParseSessionObject(const std::string& object,
                                   uint32_t title_id) {
  XSessionDetails session;
  session.title_id = title_id;
  const std::string id_text = ExtractJsonString(object, "id").empty()
                                  ? ExtractJsonString(object, "sessionId")
                                  : ExtractJsonString(object, "id");
  if (!id_text.empty()) {
    session.id = std::stoull(id_text, nullptr, 16);
  }
  session.flags = static_cast<uint32_t>(ExtractJsonUInt(object, "flags"));
  session.public_slots = static_cast<uint32_t>(
      ExtractJsonUInt(object, "publicSlotsCount", ExtractJsonUInt(object, "public_slots")));
  session.private_slots = static_cast<uint32_t>(ExtractJsonUInt(
      object, "privateSlotsCount", ExtractJsonUInt(object, "private_slots")));
  const std::string host = ExtractJsonString(object, "hostAddress").empty()
                               ? ExtractJsonString(object, "host_address")
                               : ExtractJsonString(object, "hostAddress");
  session.host_address = util::ParseIPv4NetworkOrder(host, 0);
  session.port = static_cast<uint16_t>(ExtractJsonUInt(object, "port", 3074));
  session.mac = ParseMacOrMakeStable(ExtractJsonString(object, "macAddress"),
                                     session.host_address);
  session.key_exchange = ParseCodeRedSessionKey(
      ExtractJsonString(object, "keyExchangeKey").empty()
          ? ExtractJsonString(object, "key_exchange")
          : ExtractJsonString(object, "keyExchangeKey"));
  if (std::all_of(session.key_exchange.begin(), session.key_exchange.end(),
                  [](uint8_t byte) { return byte == 0; })) {
    session.key_exchange =
        MakeCodeRedSessionKey(session.id, session.host_address, session.port);
  }
  session.started = ExtractJsonBool(object, "started", false);
  session.advertised = ExtractJsonBool(object, "advertised", true);

  const std::string player_array = ExtractJsonArray(object, "players");
  for (const auto& player_object : ExtractJsonObjects(player_array)) {
    const std::string xuid_text = ExtractJsonString(player_object, "xuid");
    if (xuid_text.empty()) {
      continue;
    }
    XSessionPlayer player;
    player.xuid = std::stoull(xuid_text, nullptr, 16);
    player.private_slot = ExtractJsonBool(player_object, "privateSlot", false) ||
                          ExtractJsonBool(player_object, "private_slot", false);
    session.players.push_back(player);
  }
  return session;
}

}  // namespace

XLiveAPI::XLiveAPI() = default;
XLiveAPI::~XLiveAPI() = default;

void XLiveAPI::Init() {
  network_mode_ = static_cast<uint32_t>(cvars::network_mode);
  init_state_ = InitState::Success;
  XELOGI("CodeRED Netplay: initialized mode={} api={}", network_mode_,
         cvars::netplay_api_address);
}

XLiveAPI::InitState XLiveAPI::GetInitState() const { return init_state_; }

void XLiveAPI::SetNetworkMode(uint32_t mode) {
  network_mode_ = mode;
  cvars::network_mode = static_cast<int32_t>(mode);
}

uint32_t XLiveAPI::GetNetworkMode() const { return network_mode_; }

bool XLiveAPI::IsOfflineMode() const {
  return network_mode_ == static_cast<uint32_t>(NetworkMode::Offline);
}

bool XLiveAPI::IsSystemLinkMode() const {
  return network_mode_ == static_cast<uint32_t>(NetworkMode::SystemLink);
}

bool XLiveAPI::IsPrivateHostMode() const {
  return network_mode_ == static_cast<uint32_t>(NetworkMode::PrivateHost);
}

bool XLiveAPI::IsNetworkEnabled() const { return !IsOfflineMode(); }

std::string XLiveAPI::GetApiAddress() { return cvars::netplay_api_address; }

void XLiveAPI::SetAPIAddress(const std::string& address) {
  cvars::netplay_api_address = address;
}

uint16_t XLiveAPI::GetPlayerPort() const { return player_port_; }

void XLiveAPI::SetPlayerPort(uint16_t port) { player_port_ = port; }

bool XLiveAPI::ShouldUsePrivateHost() const {
  return IsPrivateHostMode() && cvars::xhttp;
}

XSessionDetails XLiveAPI::CreateHostSession(
    uint32_t title_id, uint32_t session_ptr, uint32_t flags,
    uint32_t public_slots, uint32_t private_slots, uint64_t host_xuid,
    uint32_t host_address) {
  if (!host_address) {
    host_address = util::GetConfiguredIPv4NetworkOrder();
  }
  XSessionCreateParams params;
  params.title_id = title_id;
  params.session_ptr = session_ptr;
  params.flags = flags;
  params.public_slots = public_slots;
  params.private_slots = private_slots;
  params.host_xuid = host_xuid;
  params.host_address = host_address;
  params.port = player_port_;
  params.mac = util::MakeStableMac(host_address);

  auto session = sessions_.CreateHostSession(params);
  if (cvars::net_logging) {
    XELOGI(
        "CodeRED Netplay: CreateHostSession title={} session={} flags={:08X} "
        "public={} private={} host={} port={} route={}",
        FormatTitleId(title_id), FormatCodeRedSessionId(session.id), flags,
        public_slots, private_slots, util::IPv4ToString(host_address),
        player_port_, BuildSessionPostPath(title_id));
  }
  if (ShouldUsePrivateHost()) {
    if (host_xuid) {
      RegisterPlayer(host_xuid, title_id, host_address);
    }
    PublishSession(session, "create");
  }
  return session;
}

bool XLiveAPI::DeleteSession(uint32_t session_ptr) {
  const auto session = sessions_.GetSession(session_ptr);
  if (ShouldUsePrivateHost() && session.has_value()) {
    DeleteRemoteSession(session->title_id, session->id);
  }
  const bool removed = sessions_.DeleteSession(session_ptr);
  if (cvars::net_logging) {
    XELOGI("CodeRED Netplay: DeleteSession ptr={:08X} removed={}",
           session_ptr, removed);
  }
  return removed;
}

bool XLiveAPI::JoinLocalUsers(uint32_t session_ptr,
                              const std::vector<uint64_t>& xuids,
                              const std::vector<bool>& private_slots) {
  const bool joined = sessions_.JoinLocalUsers(session_ptr, xuids, private_slots);
  if (joined && ShouldUsePrivateHost()) {
    const auto session = sessions_.GetSession(session_ptr);
    if (session.has_value()) {
      for (uint64_t xuid : xuids) {
        RegisterPlayer(xuid, session->title_id, session->host_address);
      }
      JoinRemoteSession(session->title_id, session->id, xuids);
      PublishSession(*session, "join-local");
    }
  }
  if (cvars::net_logging) {
    XELOGI("CodeRED Netplay: JoinLocalUsers ptr={:08X} users={} joined={}",
           session_ptr, xuids.size(), joined);
  }
  return joined;
}

bool XLiveAPI::LeaveLocalUsers(uint32_t session_ptr,
                               const std::vector<uint64_t>& xuids) {
  const auto session = sessions_.GetSession(session_ptr);
  const bool left = sessions_.LeaveLocalUsers(session_ptr, xuids);
  if (left && ShouldUsePrivateHost() && session.has_value()) {
    LeaveRemoteSession(session->title_id, session->id, xuids);
  }
  return left;
}

bool XLiveAPI::StartSession(uint32_t session_ptr) {
  const bool started = sessions_.StartSession(session_ptr);
  if (started && ShouldUsePrivateHost()) {
    const auto session = sessions_.GetSession(session_ptr);
    if (session.has_value()) {
      PublishSession(*session, "start");
    }
  }
  if (cvars::net_logging) {
    XELOGI("CodeRED Netplay: StartSession ptr={:08X} started={}",
           session_ptr, started);
  }
  return started;
}

bool XLiveAPI::EndSession(uint32_t session_ptr) {
  const bool ended = sessions_.EndSession(session_ptr);
  if (ended && ShouldUsePrivateHost()) {
    const auto session = sessions_.GetSession(session_ptr);
    if (session.has_value()) {
      PublishSession(*session, "end");
    }
  }
  if (cvars::net_logging) {
    XELOGI("CodeRED Netplay: EndSession ptr={:08X} ended={}", session_ptr,
           ended);
  }
  return ended;
}

std::optional<XSessionDetails> XLiveAPI::GetSession(
    uint32_t session_ptr) const {
  return sessions_.GetSession(session_ptr);
}

std::vector<XSessionDetails> XLiveAPI::SearchSessions(
    uint32_t title_id, uint32_t max_results) const {
  auto matches = sessions_.Search(title_id, max_results);
  if (ShouldUsePrivateHost() && matches.size() < max_results) {
    std::set<uint64_t> existing_ids;
    for (const auto& session : matches) {
      existing_ids.insert(session.id);
    }
    auto remote = SearchRemoteSessions(title_id, max_results);
    for (const auto& session : remote) {
      if (existing_ids.insert(session.id).second) {
        matches.push_back(session);
        if (matches.size() >= max_results) {
          break;
        }
      }
    }
  }
  return matches;
}

std::optional<XSessionDetails> XLiveAPI::GetSessionDetails(
    uint32_t title_id, uint64_t session_id) const {
  for (const auto& session : sessions_.Search(title_id, 256)) {
    if (session.id == session_id) {
      return session;
    }
  }
  if (ShouldUsePrivateHost()) {
    return GetRemoteSessionDetails(title_id, session_id);
  }
  return std::nullopt;
}

bool XLiveAPI::RegisterPlayer(uint64_t xuid, uint32_t title_id,
                              uint32_t host_address) const {
  if (!ShouldUsePrivateHost()) {
    return false;
  }
  if (!host_address) {
    host_address = util::GetConfiguredIPv4NetworkOrder();
  }
  const auto mac = util::MakeStableMac(host_address);
  std::ostringstream body;
  body << "{";
  body << "\"xuid\":\"" << Hex64(xuid) << "\",";
  body << "\"machineId\":\""
       << Hex64(util::MakeMachineId(host_address, player_port_)) << "\",";
  body << "\"hostAddress\":\"" << util::IPv4ToString(host_address)
       << "\",";
  body << "\"macAddress\":\"" << MacToString(mac) << "\",";
  body << "\"port\":" << player_port_ << ",";
  body << "\"titleId\":\"" << FormatTitleId(title_id) << "\"";
  body << "}";

  const auto response = util::HttpPostJson(BuildPlayerPostPath(), body.str(),
                                           cvars::netplay_http_timeout_ms);
  if (cvars::net_logging) {
    XELOGI("CodeRED Netplay: RegisterPlayer xuid={} status={} ok={} error={}",
           Hex64(xuid), response.status_code, response.ok, response.error);
  }
  return response.ok;
}

bool XLiveAPI::PublishSession(const XSessionDetails& session,
                              const char* reason) const {
  if (!ShouldUsePrivateHost()) {
    return false;
  }
  const auto response = util::HttpPostJson(
      BuildSessionPostPath(session.title_id), BuildSessionJson(session, reason),
      cvars::netplay_http_timeout_ms);
  if (cvars::net_logging) {
    XELOGI("CodeRED Netplay: PublishSession session={} status={} ok={} error={}",
           FormatCodeRedSessionId(session.id), response.status_code,
           response.ok, response.error);
  }
  return response.ok;
}

bool XLiveAPI::JoinRemoteSession(uint32_t title_id, uint64_t session_id,
                                 const std::vector<uint64_t>& xuids) const {
  if (!ShouldUsePrivateHost()) {
    return false;
  }
  const std::string body = "{\"xuids\":" + BuildXuidArray(xuids) + "}";
  const auto response = util::HttpPostJson(BuildSessionJoinPath(title_id, session_id),
                                           body, cvars::netplay_http_timeout_ms);
  if (cvars::net_logging) {
    XELOGI("CodeRED Netplay: JoinRemoteSession session={} status={} ok={} error={}",
           FormatCodeRedSessionId(session_id), response.status_code,
           response.ok, response.error);
  }
  return response.ok;
}

bool XLiveAPI::LeaveRemoteSession(uint32_t title_id, uint64_t session_id,
                                  const std::vector<uint64_t>& xuids) const {
  if (!ShouldUsePrivateHost()) {
    return false;
  }
  const std::string body = "{\"xuids\":" + BuildXuidArray(xuids) + "}";
  const auto response = util::HttpPostJson(
      BuildSessionLeavePath(title_id, session_id), body,
      cvars::netplay_http_timeout_ms);
  return response.ok;
}

bool XLiveAPI::DeleteRemoteSession(uint32_t title_id, uint64_t session_id) const {
  if (!ShouldUsePrivateHost()) {
    return false;
  }
  const auto response = util::HttpDelete(BuildSessionPath(title_id, session_id),
                                         cvars::netplay_http_timeout_ms);
  return response.ok || response.status_code == 404;
}

bool XLiveAPI::PostQos(const XSessionDetails& session,
                       const std::string& payload) const {
  if (!ShouldUsePrivateHost()) {
    return false;
  }
  const auto response = util::HttpPostJson(BuildQosPath(session.title_id, session.id),
                                           payload, cvars::netplay_http_timeout_ms);
  return response.ok;
}

std::vector<XSessionDetails> XLiveAPI::SearchRemoteSessions(
    uint32_t title_id, uint32_t max_results) const {
  std::vector<XSessionDetails> sessions;
  if (!ShouldUsePrivateHost()) {
    return sessions;
  }
  std::ostringstream body;
  body << "{\"searchIndex\":0,\"resultsCount\":" << max_results << "}";
  const auto response = util::HttpPostJson(BuildSessionSearchPath(title_id),
                                           body.str(),
                                           cvars::netplay_http_timeout_ms);
  if (cvars::net_logging) {
    XELOGI("CodeRED Netplay: SearchRemoteSessions title={} status={} ok={} bytes={}",
           FormatTitleId(title_id), response.status_code, response.ok,
           response.body.size());
  }
  if (!response.ok) {
    return sessions;
  }
  for (const auto& object : ExtractJsonObjects(response.body)) {
    auto parsed = ParseSessionObject(object, title_id);
    if (parsed.id != 0 && parsed.host_address != 0) {
      auto details = GetRemoteSessionDetails(title_id, parsed.id);
      sessions.push_back(details.has_value() ? *details : parsed);
      if (sessions.size() >= max_results) {
        break;
      }
    }
  }
  return sessions;
}

std::optional<XSessionDetails> XLiveAPI::GetRemoteSessionDetails(
    uint32_t title_id, uint64_t session_id) const {
  if (!ShouldUsePrivateHost()) {
    return std::nullopt;
  }
  const auto response = util::HttpGet(BuildSessionDetailsPath(title_id, session_id),
                                      cvars::netplay_http_timeout_ms);
  if (cvars::net_logging) {
    XELOGI("CodeRED Netplay: GetRemoteSessionDetails session={} status={} ok={} bytes={}",
           FormatCodeRedSessionId(session_id), response.status_code,
           response.ok, response.body.size());
  }
  if (!response.ok) {
    return std::nullopt;
  }
  auto parsed = ParseSessionObject(response.body, title_id);
  if (!parsed.id) {
    parsed.id = session_id;
  }
  return parsed.id ? std::optional<XSessionDetails>(parsed) : std::nullopt;
}

std::string XLiveAPI::BuildPlayerPostPath() const {
  return JoinApiPath("/players");
}

std::string XLiveAPI::BuildSessionPostPath(uint32_t title_id) const {
  return JoinApiPath("/title/" + FormatTitleId(title_id) + "/sessions");
}

std::string XLiveAPI::BuildSessionPath(uint32_t title_id,
                                       uint64_t session_id) const {
  return BuildSessionPostPath(title_id) + "/" +
         FormatCodeRedSessionId(session_id);
}

std::string XLiveAPI::BuildSessionSearchPath(uint32_t title_id) const {
  return BuildSessionPostPath(title_id) + "/search";
}

std::string XLiveAPI::BuildSessionDetailsPath(uint32_t title_id,
                                              uint64_t session_id) const {
  return BuildSessionPath(title_id, session_id) + "/details";
}

std::string XLiveAPI::BuildSessionJoinPath(uint32_t title_id,
                                           uint64_t session_id) const {
  return BuildSessionPath(title_id, session_id) + "/join";
}

std::string XLiveAPI::BuildSessionLeavePath(uint32_t title_id,
                                            uint64_t session_id) const {
  return BuildSessionPath(title_id, session_id) + "/leave";
}

std::string XLiveAPI::BuildQosPath(uint32_t title_id,
                                   uint64_t session_id) const {
  return BuildSessionPath(title_id, session_id) + "/qos";
}

XLiveAPI& GetCodeRedXLiveAPI() {
  static XLiveAPI api;
  return api;
}

}  // namespace kernel
}  // namespace xe
