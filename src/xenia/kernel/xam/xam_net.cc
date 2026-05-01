/**
 ******************************************************************************
 * Xenia : Xbox 360 Emulator Research Project                                 *
 ******************************************************************************
 * Copyright 2022 Ben Vanik. All rights reserved.                             *
 * Released under the BSD license - see LICENSE in the root for more details. *
 ******************************************************************************
 */

#include <algorithm>
#include <array>
#include <cstring>
#include <iomanip>
#include <limits>
#include <random>
#include <sstream>
#include <vector>

#include "xenia/base/cvar.h"
#include "xenia/base/logging.h"
#include "xenia/kernel/XLiveAPI.h"
#include "xenia/kernel/kernel_state.h"
#include "xenia/kernel/util/net_utils.h"
#include "xenia/kernel/util/shim_utils.h"
#include "xenia/kernel/xam/xam_module.h"
#include "xenia/kernel/xam/xam_private.h"
#include "xenia/kernel/xboxkrnl/xboxkrnl_error.h"
#include "xenia/kernel/xboxkrnl/xboxkrnl_threading.h"
#include "xenia/kernel/xevent.h"
#include "xenia/kernel/xsocket.h"
#include "xenia/kernel/xthread.h"
#include "xenia/xbox.h"

#ifdef XE_PLATFORM_WIN32
// NOTE: must be included last as it expects windows.h to already be included.
#define _WINSOCK_DEPRECATED_NO_WARNINGS  // inet_addr
#include <winsock2.h>                    // NOLINT(build/include_order)
#else
#include <arpa/inet.h>
#include <netinet/in.h>
#include <netinet/ip.h>
#include <sys/select.h>
#include <sys/socket.h>
#endif

DECLARE_int32(network_mode);
DECLARE_bool(net_logging);
DECLARE_bool(netplay_udp_bootstrap);
DECLARE_int32(netplay_udp_bootstrap_interval);
DECLARE_string(selected_network_interface);

namespace xe {
namespace kernel {
namespace xam {

// https://github.com/G91/TitanOffLine/blob/1e692d9bb9dfac386d08045ccdadf4ae3227bb5e/xkelib/xam/xamNet.h
enum {
  XNCALLER_INVALID = 0x0,
  XNCALLER_TITLE = 0x1,
  XNCALLER_SYSAPP = 0x2,
  XNCALLER_XBDM = 0x3,
  XNCALLER_TEST = 0x4,
  NUM_XNCALLER_TYPES = 0x4,
};

// https://github.com/pmrowla/hl2sdk-csgo/blob/master/common/xbox/xboxstubs.h
typedef struct {
  // FYI: IN_ADDR should be in network-byte order.
  in_addr ina;                   // IP address (zero if not static/DHCP)
  in_addr inaOnline;             // Online IP address (zero if not online)
  xe::be<uint16_t> wPortOnline;  // Online port
  uint8_t abEnet[6];             // Ethernet MAC address
  uint8_t abOnline[20];          // Online identification
} XNADDR;

struct XNDNS {
  xe::be<int32_t> status;
  xe::be<uint32_t> cina;
  in_addr aina[8];
};
static_assert_size(XNDNS, 0x28);

struct XNQOSINFO {
  uint8_t flags;
  uint8_t reserved;
  xe::be<uint16_t> probes_xmit;
  xe::be<uint16_t> probes_recv;
  xe::be<uint16_t> data_len;
  xe::be<uint32_t> data_ptr;
  xe::be<uint16_t> rtt_min_in_msecs;
  xe::be<uint16_t> rtt_med_in_msecs;
  xe::be<uint32_t> up_bits_per_sec;
  xe::be<uint32_t> down_bits_per_sec;
};
static_assert_size(XNQOSINFO, 0x18);

struct XNQOS {
  xe::be<uint32_t> count;
  xe::be<uint32_t> count_pending;
  XNQOSINFO info[1];
};

struct Xsockaddr_t {
  xe::be<uint16_t> sa_family;
  char sa_data[14];
};
static_assert_size(XNQOS, 0x20);

struct X_WSADATA {
  xe::be<uint16_t> version;
  xe::be<uint16_t> version_high;
  char description[256 + 1];
  char system_status[128 + 1];
  xe::be<uint16_t> max_sockets;
  xe::be<uint16_t> max_udpdg;
  xe::be<uint32_t> vendor_info_ptr;
};
static_assert_size(X_WSADATA, 0x190);

struct XWSABUF {
  xe::be<uint32_t> len;
  xe::be<uint32_t> buf_ptr;
};

struct XWSAOVERLAPPED {
  xe::be<uint32_t> internal;
  xe::be<uint32_t> internal_high;
  union {
    struct {
      xe::be<uint32_t> low;
      xe::be<uint32_t> high;
    } offset;  // must be named to avoid GCC error
    xe::be<uint32_t> pointer;
  };
  xe::be<uint32_t> event_handle;
};

void LoadSockaddr(const uint8_t* ptr, sockaddr* out_addr) {
  out_addr->sa_family = xe::load_and_swap<uint16_t>(ptr + 0);
  switch (out_addr->sa_family) {
    case AF_INET: {
      auto in_addr = reinterpret_cast<sockaddr_in*>(out_addr);
      in_addr->sin_port = xe::load_and_swap<uint16_t>(ptr + 2);
      // Maybe? Depends on type.
      in_addr->sin_addr.s_addr = *(uint32_t*)(ptr + 4);
      break;
    }
    default:
      assert_unhandled_case(out_addr->sa_family);
      break;
  }
}

void StoreSockaddr(const sockaddr& addr, uint8_t* ptr) {
  switch (addr.sa_family) {
    case AF_UNSPEC:
      std::memset(ptr, 0, sizeof(addr));
      break;
    case AF_INET: {
      auto& in_addr = reinterpret_cast<const sockaddr_in&>(addr);
      xe::store_and_swap<uint16_t>(ptr + 0, in_addr.sin_family);
      xe::store_and_swap<uint16_t>(ptr + 2, in_addr.sin_port);
      // Maybe? Depends on type.
      xe::store_and_swap<uint32_t>(ptr + 4, in_addr.sin_addr.s_addr);
      break;
    }
    default:
      assert_unhandled_case(addr.sa_family);
      break;
  }
}

// https://github.com/joolswills/mameox/blob/master/MAMEoX/Sources/xbox_Network.cpp#L136
struct XNetStartupParams {
  uint8_t cfgSizeOfStruct;
  uint8_t cfgFlags;
  uint8_t cfgSockMaxDgramSockets;
  uint8_t cfgSockMaxStreamSockets;
  uint8_t cfgSockDefaultRecvBufsizeInK;
  uint8_t cfgSockDefaultSendBufsizeInK;
  uint8_t cfgKeyRegMax;
  uint8_t cfgSecRegMax;
  uint8_t cfgQosDataLimitDiv4;
  uint8_t cfgQosProbeTimeoutInSeconds;
  uint8_t cfgQosProbeRetries;
  uint8_t cfgQosSrvMaxSimultaneousResponses;
  uint8_t cfgQosPairWaitTimeInSeconds;
};
static_assert_size(XNetStartupParams, 0xD);

XNetStartupParams xnet_startup_params = {0};

namespace {
constexpr uint32_t kWSAEWOULDBLOCK = 0x2733;
constexpr uint32_t kQosListenEnable = 0x01;
constexpr uint32_t kQosListenDisable = 0x02;
constexpr uint32_t kQosListenSetData = 0x04;
constexpr uint32_t kQosListenRelease = 0x10;
constexpr uint32_t kQosInfoComplete = 0x01;
constexpr uint32_t kQosInfoTargetContacted = 0x02;
constexpr uint32_t kQosInfoDataReceived = 0x08;

struct CodeRedQosListenState {
  bool active = false;
  std::vector<uint8_t> data;
};

uint16_t system_link_port = 3074;
CodeRedQosListenState qos_listen_state;

struct CodeRedRegisteredKey {
  uint64_t id = 0;
  std::array<uint8_t, 16> exchange_key = {};
  uint32_t host_address = 0;
  uint16_t port = 3074;
  std::array<uint8_t, 6> mac = {};
};

std::vector<CodeRedRegisteredKey> registered_keys;

uint64_t ReadGuestBe64(uint32_t guest_address) {
  if (!guest_address) {
    return 0;
  }
  return xe::load_and_swap<uint64_t>(
      kernel_memory()->TranslateVirtual<const uint8_t*>(guest_address));
}

std::array<uint8_t, 16> ReadGuestKey(uint32_t guest_address) {
  std::array<uint8_t, 16> key = {};
  if (!guest_address) {
    return key;
  }
  std::memcpy(key.data(), kernel_memory()->TranslateVirtual(guest_address),
              key.size());
  return key;
}

void WriteGuestBe64(uint32_t guest_address, uint64_t value) {
  if (!guest_address) {
    return;
  }
  xe::store_and_swap<uint64_t>(
      kernel_memory()->TranslateVirtual<uint8_t*>(guest_address), value);
}

void WriteGuestKey(uint32_t guest_address, const std::array<uint8_t, 16>& key) {
  if (!guest_address) {
    return;
  }
  std::memcpy(kernel_memory()->TranslateVirtual(guest_address), key.data(),
              key.size());
}

bool IsZeroKey(const std::array<uint8_t, 16>& key) {
  return std::all_of(key.begin(), key.end(),
                     [](uint8_t byte) { return byte == 0; });
}

CodeRedRegisteredKey* FindRegisteredKey(uint64_t id) {
  for (auto& key : registered_keys) {
    if (key.id == id) {
      return &key;
    }
  }
  return nullptr;
}

const CodeRedRegisteredKey* FindRegisteredKeyConst(uint64_t id) {
  for (const auto& key : registered_keys) {
    if (key.id == id) {
      return &key;
    }
  }
  return nullptr;
}

void UpsertRegisteredKey(const CodeRedRegisteredKey& registered_key) {
  if (auto* existing = FindRegisteredKey(registered_key.id)) {
    *existing = registered_key;
    return;
  }
  registered_keys.push_back(registered_key);
}

void FillXnAddrFromRegisteredKey(XNADDR* addr, const CodeRedRegisteredKey& key) {
  std::memset(addr, 0, sizeof(XNADDR));
  addr->ina.s_addr = key.host_address;
  addr->inaOnline.s_addr =
      (cvars::network_mode == 2 || cvars::network_mode == 3)
          ? key.host_address
          : 0;
  addr->wPortOnline = key.port;
  std::memcpy(addr->abEnet, key.mac.data(), key.mac.size());
  xe::store_and_swap<uint32_t>(addr->abOnline + 0x00, key.host_address);
  xe::store_and_swap<uint32_t>(addr->abOnline + 0x04,
                               static_cast<uint32_t>(key.id & 0xFFFFFFFFu));
  xe::store_and_swap<uint64_t>(addr->abOnline + 0x08, key.id);
  addr->abOnline[0x10] = 1;
}

uint64_t MakeCreatedKeyId() {
  static uint64_t counter = 0xC0DE000000000001ULL;
  return counter++;
}

std::string HexPreview(const uint8_t* data, size_t size, size_t max_bytes = 16) {
  if (!data || !size) {
    return "";
  }
  std::ostringstream out;
  const size_t count = std::min<size_t>(size, max_bytes);
  for (size_t i = 0; i < count; ++i) {
    if (i) {
      out << ' ';
    }
    out << std::uppercase << std::hex << std::setfill('0') << std::setw(2)
        << static_cast<uint32_t>(data[i]);
  }
  if (size > count) {
    out << " ...";
  }
  return out.str();
}

std::string HexPreviewGuest(uint32_t guest_address, uint32_t size,
                            uint32_t max_bytes = 16) {
  if (!guest_address || !size) {
    return "";
  }
  return HexPreview(kernel_memory()->TranslateVirtual<const uint8_t*>(guest_address),
                    size, max_bytes);
}

bool ShouldLogEvery(uint32_t& counter, uint32_t interval) {
  ++counter;
  return counter == 1 || (interval && (counter % interval) == 0);
}

uint32_t GetConfiguredTitleIp();

bool ShouldInjectUdpBootstrap(uint32_t& counter) {
  ++counter;
  const uint32_t interval = static_cast<uint32_t>(
      std::max(1, cvars::netplay_udp_bootstrap_interval));
  return cvars::netplay_udp_bootstrap && cvars::network_mode != 0 &&
         (counter == 1 || (counter % interval) == 0);
}

std::vector<uint8_t> BuildUdpBootstrapPacket(uint32_t socket_handle,
                                             const char* source) {
  static uint32_t serial = 0;
  const uint32_t ip = GetConfiguredTitleIp();
  const uint64_t session_id = registered_keys.empty()
                                  ? 0xC0DE120000000001ULL
                                  : registered_keys.front().id;
  std::ostringstream body;
  body << "CODERED_RDR_V12;source=" << source << ";serial=" << ++serial
       << ";socket=" << std::uppercase << std::hex << std::setfill('0')
       << std::setw(8) << socket_handle << ";session="
       << FormatCodeRedSessionId(session_id) << ";ip="
       << util::IPv4ToString(ip) << ";port=" << std::dec << system_link_port
       << ";mp=freemode,mp_idle,multiplayer_system_thread,"
          "multiplayer_update_thread,deathmatch,ctf;";
  const std::string text = body.str();
  return std::vector<uint8_t>(text.begin(), text.end());
}

void FillUdpBootstrapFrom(N_XSOCKADDR_IN* from, uint32_t* from_len) {
  if (from) {
    from->sin_family = AF_INET;
    from->sin_port = htons(system_link_port);
    from->sin_addr = GetConfiguredTitleIp();
    std::memset(from->x_sin_zero, 0, sizeof(from->x_sin_zero));
  }
  if (from_len) {
    *from_len = sizeof(N_XSOCKADDR_IN);
  }
}

void StoreUdpBootstrapFrom(pointer_t<XSOCKADDR_IN> from_addr) {
  if (!from_addr) {
    return;
  }
  from_addr->sin_family = AF_INET;
  from_addr->sin_port = htons(system_link_port);
  from_addr->sin_addr = GetConfiguredTitleIp();
  std::memset(from_addr->x_sin_zero, 0, sizeof(from_addr->x_sin_zero));
}

int InjectUdpBootstrapPacket(dword_t socket_handle, lpvoid_t buf_ptr,
                             dword_t buf_len, N_XSOCKADDR_IN* from,
                             uint32_t* from_len, const char* source) {
  const auto packet = BuildUdpBootstrapPacket(socket_handle.value(), source);
  const uint32_t copied =
      std::min<uint32_t>(buf_len.value(), static_cast<uint32_t>(packet.size()));
  if (!copied || !buf_ptr) {
    return -1;
  }
  std::memcpy(kernel_memory()->TranslateVirtual(buf_ptr.guest_address()),
              packet.data(), copied);
  FillUdpBootstrapFrom(from, from_len);
  XThread::SetLastError(0);
  if (cvars::net_logging) {
    XELOGI(
        "CodeRED Netplay: UDP bootstrap injected api={} socket={:08X} "
        "bytes={} from={}:{} preview={}",
        source, socket_handle.value(), copied,
        util::IPv4ToString(GetConfiguredTitleIp()), system_link_port,
        HexPreview(packet.data(), copied));
    XELOGI(
        "CodeRED MP correlation: bootstrap packet advertises candidates="
        "freemode,mp_idle,multiplayer_system_thread,"
        "multiplayer_update_thread,deathmatch,ctf");
  }
  return static_cast<int>(copied);
}

int InjectUdpBootstrapPacketWSA(dword_t socket_handle,
                                pointer_t<XWSABUF> buffers_ptr,
                                dword_t buffer_count,
                                lpdword_t num_bytes_recv,
                                lpdword_t flags_ptr,
                                pointer_t<XSOCKADDR_IN> from_addr,
                                const char* source) {
  const auto packet = BuildUdpBootstrapPacket(socket_handle.value(), source);
  uint32_t copied = 0;
  for (uint32_t i = 0; i < buffer_count && copied < packet.size(); ++i) {
    const uint32_t to_copy = std::min<uint32_t>(
        buffers_ptr[i].len, static_cast<uint32_t>(packet.size()) - copied);
    if (!to_copy || !buffers_ptr[i].buf_ptr) {
      continue;
    }
    std::memcpy(kernel_memory()->TranslateVirtual(buffers_ptr[i].buf_ptr),
                packet.data() + copied, to_copy);
    copied += to_copy;
  }
  if (!copied) {
    return -1;
  }
  if (num_bytes_recv) {
    *num_bytes_recv = copied;
  }
  if (flags_ptr) {
    *flags_ptr = 0;
  }
  StoreUdpBootstrapFrom(from_addr);
  XThread::SetLastError(0);
  if (cvars::net_logging) {
    XELOGI(
        "CodeRED Netplay: UDP bootstrap injected api={} socket={:08X} "
        "bytes={} from={}:{} preview={}",
        source, socket_handle.value(), copied,
        util::IPv4ToString(GetConfiguredTitleIp()), system_link_port,
        HexPreview(packet.data(), copied));
    XELOGI(
        "CodeRED MP correlation: bootstrap packet advertises candidates="
        "freemode,mp_idle,multiplayer_system_thread,"
        "multiplayer_update_thread,deathmatch,ctf");
  }
  return static_cast<int>(copied);
}


bool IsSocketReadable(const XSocket& socket) {
  fd_set readfds;
  FD_ZERO(&readfds);
#ifdef XE_PLATFORM_WIN32
  SOCKET native_socket = static_cast<SOCKET>(socket.native_handle());
  FD_SET(native_socket, &readfds);
  timeval timeout{};
  const int ret = select(0, &readfds, nullptr, nullptr, &timeout);
#else
  int native_socket = static_cast<int>(socket.native_handle());
  FD_SET(native_socket, &readfds);
  timeval timeout{};
  const int ret = select(native_socket + 1, &readfds, nullptr, nullptr, &timeout);
#endif
  return ret > 0;
}

void SignalOverlappedEvent(pointer_t<XWSAOVERLAPPED> overlapped_ptr) {
  if (!overlapped_ptr || !overlapped_ptr->event_handle) {
    return;
  }
  auto evt = kernel_state()->object_table()->LookupObject<XEvent>(
      overlapped_ptr->event_handle);
  if (evt) {
    evt->Set(0, false);
  }
}

void SignalEventHandle(dword_t event_handle) {
  if (!event_handle) {
    return;
  }
  auto ev = kernel_state()->object_table()->LookupObject<XEvent>(event_handle);
  if (ev) {
    ev->Set(0, false);
  }
}

uint32_t GetConfiguredTitleIp() {
  return util::GetConfiguredIPv4NetworkOrder();
}

void FillTitleXnAddr(XNADDR* addr) {
  const uint32_t ip = GetConfiguredTitleIp();
  addr->ina.s_addr = ip;
  addr->inaOnline.s_addr =
      (cvars::network_mode == 2 || cvars::network_mode == 3) ? ip : 0;
  addr->wPortOnline = system_link_port;

  auto mac = util::MakeStableMac(ip);
  std::memcpy(addr->abEnet, mac.data(), mac.size());
  std::memset(addr->abOnline, 0, sizeof(addr->abOnline));
}
}  // namespace

dword_result_t NetDll_XNetStartup_entry(dword_t caller,
                                        pointer_t<XNetStartupParams> params) {
  if (params) {
    assert_true(params->cfgSizeOfStruct == sizeof(XNetStartupParams));
    std::memcpy(&xnet_startup_params, params, sizeof(XNetStartupParams));
  }

  auto& xlive_api = GetCodeRedXLiveAPI();
  if (xlive_api.GetInitState() == XLiveAPI::InitState::Pending) {
    xlive_api.Init();
  }
  xlive_api.SetPlayerPort(system_link_port);

  auto xam = kernel_state()->GetKernelModule<XamModule>("xam.xex");

  /*
  if (!xam->xnet()) {
    auto xnet = new XNet(kernel_state());
    xnet->Initialize();

    xam->set_xnet(xnet);
  }
  */

  return 0;
}
DECLARE_XAM_EXPORT1(NetDll_XNetStartup, kNetworking, kImplemented);

// https://github.com/jogolden/testdev/blob/master/xkelib/syssock.h#L46
dword_result_t NetDll_XNetStartupEx_entry(dword_t caller,
                                          pointer_t<XNetStartupParams> params,
                                          dword_t versionReq) {
  // versionReq
  // MW3, Ghosts: 0x20501400

  return NetDll_XNetStartup_entry(caller, params);
}
DECLARE_XAM_EXPORT1(NetDll_XNetStartupEx, kNetworking, kImplemented);

dword_result_t NetDll_XNetCleanup_entry(dword_t caller, lpvoid_t params) {
  auto xam = kernel_state()->GetKernelModule<XamModule>("xam.xex");
  // auto xnet = xam->xnet();
  // xam->set_xnet(nullptr);

  // TODO: Shut down and delete.
  // delete xnet;

  return 0;
}
DECLARE_XAM_EXPORT1(NetDll_XNetCleanup, kNetworking, kImplemented);

dword_result_t NetDll_XNetGetOpt_entry(dword_t one, dword_t option_id,
                                       lpvoid_t buffer_ptr,
                                       lpdword_t buffer_size) {
  assert_true(one == 1);
  switch (option_id) {
    case 1:
      if (*buffer_size < sizeof(XNetStartupParams)) {
        *buffer_size = sizeof(XNetStartupParams);
        return uint32_t(X_WSAError::X_WSAEMSGSIZE);
      }
      std::memcpy(buffer_ptr, &xnet_startup_params, sizeof(XNetStartupParams));
      return 0;
    default:
      XELOGE("NetDll_XNetGetOpt: option {} unimplemented",
             static_cast<uint32_t>(option_id));
      return uint32_t(X_WSAError::X_WSAEINVAL);
  }
}
DECLARE_XAM_EXPORT1(NetDll_XNetGetOpt, kNetworking, kSketchy);

dword_result_t NetDll_XNetRandom_entry(dword_t caller, lpvoid_t buffer_ptr,
                                       dword_t length) {
  uint8_t* buffer_data_ptr = buffer_ptr.as<uint8_t*>();

  if (buffer_data_ptr == nullptr || length == 0) {
    return X_ERROR_SUCCESS;
  }

  std::random_device rnd;
  std::mt19937_64 gen(rnd());
  std::uniform_int_distribution<int> dist(0,
                                          std::numeric_limits<uint8_t>::max());

  std::generate(buffer_data_ptr, buffer_data_ptr + length,
                [&]() { return static_cast<uint8_t>(dist(gen)); });

  return X_ERROR_SUCCESS;
}
DECLARE_XAM_EXPORT1(NetDll_XNetRandom, kNetworking, kImplemented);

dword_result_t NetDll_WSAStartup_entry(dword_t caller, word_t version,
                                       pointer_t<X_WSADATA> data_ptr) {
  auto& xlive_api = GetCodeRedXLiveAPI();
  if (xlive_api.GetInitState() == XLiveAPI::InitState::Pending) {
    xlive_api.Init();
  }

  // TODO(benvanik): abstraction layer needed.
  int ret = 0;

#ifdef XE_PLATFORM_WIN32
  WSADATA wsaData = {};

  ret = WSAStartup(version, &wsaData);
#endif

  if (data_ptr) {
    data_ptr.Zero();

#ifdef XE_PLATFORM_WIN32
    data_ptr->version = wsaData.wVersion;
    data_ptr->version_high = wsaData.wHighVersion;
#else
    data_ptr->version = version.value();
    data_ptr->version_high = 0x0202;
#endif
  }

  // DEBUG
  /*
  auto xam = kernel_state()->GetKernelModule<XamModule>("xam.xex");
  if (!xam->xnet()) {
    auto xnet = new XNet(kernel_state());
    xnet->Initialize();

    xam->set_xnet(xnet);
  }
  */

  return ret;
}
DECLARE_XAM_EXPORT1(NetDll_WSAStartup, kNetworking, kImplemented);

dword_result_t NetDll_WSAStartupEx_entry(dword_t caller, word_t version,
                                         pointer_t<X_WSADATA> data_ptr,
                                         dword_t versionReq) {
  return NetDll_WSAStartup_entry(caller, version, data_ptr);
}
DECLARE_XAM_EXPORT1(NetDll_WSAStartupEx, kNetworking, kImplemented);

dword_result_t NetDll_WSACleanup_entry(dword_t caller) {
  // This does nothing. Xenia needs WSA running.
  return 0;
}
DECLARE_XAM_EXPORT1(NetDll_WSACleanup, kNetworking, kImplemented);

// Instead of using dedicated storage for WSA error like on OS.
// Xbox shares space between normal error codes and WSA errors.
// This under the hood returns directly value received from RtlGetLastError.
dword_result_t NetDll_WSAGetLastError_entry() {
  uint32_t last_error = XThread::GetLastError();
  XELOGD("NetDll_WSAGetLastError: {}", last_error);
  return last_error;
}
DECLARE_XAM_EXPORT1(NetDll_WSAGetLastError, kNetworking, kImplemented);

dword_result_t NetDll_WSARecvFrom_entry(
    dword_t caller, dword_t socket_handle, pointer_t<XWSABUF> buffers_ptr,
    dword_t buffer_count, lpdword_t num_bytes_recv, lpdword_t flags_ptr,
    pointer_t<XSOCKADDR_IN> from_addr, pointer_t<XWSAOVERLAPPED> overlapped_ptr,
    lpvoid_t completion_routine_ptr) {
  assert(!completion_routine_ptr);

  auto socket =
      kernel_state()->object_table()->LookupObject<XSocket>(socket_handle);
  if (!socket) {
    XThread::SetLastError(uint32_t(X_WSAError::X_WSAENOTSOCK));
    SignalOverlappedEvent(overlapped_ptr);
    return -1;
  }

  if (!buffers_ptr || !buffer_count) {
    XThread::SetLastError(uint32_t(X_WSAError::X_WSA_INVALID_PARAMETER));
    SignalOverlappedEvent(overlapped_ptr);
    return -1;
  }

  // Keep the emulator from freezing if a title probes a blocking socket with no
  // packet ready. Most System Link traffic is poll-driven, so a fast would-block
  // is safer than the old permanent receive stub and safer than blocking here.
  if (!IsSocketReadable(*socket)) {
    static uint32_t wouldblock_log_count = 0;
    static uint32_t bootstrap_inject_count = 0;
    if (ShouldInjectUdpBootstrap(bootstrap_inject_count)) {
      const int injected = InjectUdpBootstrapPacketWSA(
          socket_handle, buffers_ptr, buffer_count, num_bytes_recv, flags_ptr,
          from_addr, "WSARecvFrom");
      if (injected > 0) {
        SignalOverlappedEvent(overlapped_ptr);
        return 0;
      }
    }
    XThread::SetLastError(kWSAEWOULDBLOCK);
    if (num_bytes_recv) {
      *num_bytes_recv = 0;
    }
    if (cvars::net_logging && ShouldLogEvery(wouldblock_log_count, 120)) {
      XELOGD(
          "CodeRED Netplay: WSARecvFrom would-block socket={:08X} buffers={} "
          "mode={} port={}",
          socket_handle.value(), buffer_count.value(), cvars::network_mode,
          system_link_port);
    }
    SignalOverlappedEvent(overlapped_ptr);
    return -1;
  }

  uint32_t combined_buffer_size = 0;
  for (uint32_t i = 0; i < buffer_count; ++i) {
    combined_buffer_size += buffers_ptr[i].len;
  }
  std::vector<uint8_t> combined_buffer(combined_buffer_size);

  N_XSOCKADDR_IN native_from{};
  uint32_t native_from_len = sizeof(native_from);
  const uint32_t native_flags = flags_ptr ? uint32_t(*flags_ptr) : 0;
  int ret = socket->RecvFrom(combined_buffer.data(), combined_buffer_size,
                             native_flags, from_addr ? &native_from : nullptr,
                             &native_from_len);
  if (ret < 0) {
    XThread::SetLastError(socket->GetLastWSAError());
    SignalOverlappedEvent(overlapped_ptr);
    return -1;
  }

  uint32_t copied = 0;
  for (uint32_t i = 0; i < buffer_count && copied < uint32_t(ret); ++i) {
    const uint32_t to_copy = std::min<uint32_t>(buffers_ptr[i].len,
                                               uint32_t(ret) - copied);
    std::memcpy(kernel_memory()->TranslateVirtual(buffers_ptr[i].buf_ptr),
                combined_buffer.data() + copied, to_copy);
    copied += to_copy;
  }

  if (num_bytes_recv) {
    *num_bytes_recv = static_cast<uint32_t>(ret);
  }
  if (flags_ptr) {
    *flags_ptr = 0;
  }
  if (from_addr) {
    from_addr->sin_family = native_from.sin_family;
    from_addr->sin_port = native_from.sin_port;
    from_addr->sin_addr = native_from.sin_addr;
    std::memset(from_addr->x_sin_zero, 0, sizeof(from_addr->x_sin_zero));
  }
  SignalOverlappedEvent(overlapped_ptr);

  if (cvars::net_logging) {
    XELOGD(
        "CodeRED Netplay: WSARecvFrom socket={:08X} bytes={} from={}:{} "
        "preview={}",
        socket_handle.value(), ret, util::IPv4ToString(native_from.sin_addr),
        ntohs(uint16_t(native_from.sin_port)),
        HexPreview(combined_buffer.data(), static_cast<size_t>(ret)));
  }
  return 0;
}
DECLARE_XAM_EXPORT2(NetDll_WSARecvFrom, kNetworking, kImplemented,
                    kHighFrequency);

// If the socket is a VDP socket, buffer 0 is the game data length, and buffer 1
// is the unencrypted game data.
dword_result_t NetDll_WSASendTo_entry(
    dword_t caller, dword_t socket_handle, pointer_t<XWSABUF> buffers,
    dword_t num_buffers, lpdword_t num_bytes_sent, dword_t flags,
    pointer_t<XSOCKADDR_IN> to_ptr, dword_t to_len,
    pointer_t<XWSAOVERLAPPED> overlapped, lpvoid_t completion_routine) {
  assert(!overlapped);
  assert(!completion_routine);

  auto socket =
      kernel_state()->object_table()->LookupObject<XSocket>(socket_handle);
  if (!socket) {
    XThread::SetLastError(uint32_t(X_WSAError::X_WSAENOTSOCK));
    return -1;
  }

  // Our sockets implementation doesn't support multiple buffers, so we need
  // to combine the buffers the game has given us!
  std::vector<uint8_t> combined_buffer_mem;
  uint32_t combined_buffer_size = 0;
  uint32_t combined_buffer_offset = 0;
  for (uint32_t i = 0; i < num_buffers; i++) {
    combined_buffer_size += buffers[i].len;
    combined_buffer_mem.resize(combined_buffer_size);
    uint8_t* combined_buffer = combined_buffer_mem.data();

    std::memcpy(combined_buffer + combined_buffer_offset,
                kernel_memory()->TranslateVirtual(buffers[i].buf_ptr),
                buffers[i].len);
    combined_buffer_offset += buffers[i].len;
  }

  N_XSOCKADDR_IN native_to(to_ptr);
  const int ret = socket->SendTo(combined_buffer_mem.data(), combined_buffer_size, flags,
                                 &native_to, to_len);
  if (ret < 0) {
    XThread::SetLastError(socket->GetLastWSAError());
    return -1;
  }

  if (num_bytes_sent) {
    *num_bytes_sent = combined_buffer_size;
  }

  if (cvars::net_logging) {
    XELOGD(
        "CodeRED Netplay: WSASendTo socket={:08X} bytes={} to={}:{} "
        "preview={}",
        socket_handle.value(), combined_buffer_size,
        util::IPv4ToString(native_to.sin_addr), ntohs(uint16_t(native_to.sin_port)),
        HexPreview(combined_buffer_mem.data(), combined_buffer_mem.size()));
  }

  // TODO: Instantly complete overlapped

  return 0;
}
DECLARE_XAM_EXPORT1(NetDll_WSASendTo, kNetworking, kImplemented);

dword_result_t NetDll_WSAWaitForMultipleEvents_entry(dword_t num_events,
                                                     lpdword_t events,
                                                     dword_t wait_all,
                                                     dword_t timeout,
                                                     dword_t alertable) {
  if (num_events > 64) {
    XThread::SetLastError(uint32_t(X_WSAError::X_WSA_INVALID_PARAMETER));
    return ~0u;
  }

  uint64_t timeout_wait = (uint64_t)timeout;

  X_STATUS result = 0;
  do {
    result = xboxkrnl::xeNtWaitForMultipleObjectsEx(
        num_events, events, wait_all, 1, alertable,
        timeout != -1 ? &timeout_wait : nullptr);
  } while (result == X_STATUS_ALERTED);

  if (XFAILED(result)) {
    uint32_t error = xboxkrnl::xeRtlNtStatusToDosError(result);
    XThread::SetLastError(error);
    return ~0u;
  }
  return 0;
}
DECLARE_XAM_EXPORT2(NetDll_WSAWaitForMultipleEvents, kNetworking, kImplemented,
                    kBlocking);

dword_result_t NetDll_WSACreateEvent_entry() {
  XEvent* ev = new XEvent(kernel_state());
  ev->Initialize(true, false);
  return ev->handle();
}
DECLARE_XAM_EXPORT1(NetDll_WSACreateEvent, kNetworking, kImplemented);

dword_result_t NetDll_WSACloseEvent_entry(dword_t event_handle) {
  X_STATUS result = kernel_state()->object_table()->ReleaseHandle(event_handle);
  if (XFAILED(result)) {
    uint32_t error = xboxkrnl::xeRtlNtStatusToDosError(result);
    XThread::SetLastError(error);
    return 0;
  }
  return 1;
}
DECLARE_XAM_EXPORT1(NetDll_WSACloseEvent, kNetworking, kImplemented);

dword_result_t NetDll_WSAResetEvent_entry(dword_t event_handle) {
  X_STATUS result = xboxkrnl::xeNtClearEvent(event_handle);
  if (XFAILED(result)) {
    uint32_t error = xboxkrnl::xeRtlNtStatusToDosError(result);
    XThread::SetLastError(error);
    return 0;
  }
  return 1;
}
DECLARE_XAM_EXPORT1(NetDll_WSAResetEvent, kNetworking, kImplemented);

dword_result_t NetDll_WSASetEvent_entry(dword_t event_handle) {
  X_STATUS result = xboxkrnl::xeNtSetEvent(event_handle, nullptr);
  if (XFAILED(result)) {
    uint32_t error = xboxkrnl::xeRtlNtStatusToDosError(result);
    XThread::SetLastError(error);
    return 0;
  }
  return 1;
}
DECLARE_XAM_EXPORT1(NetDll_WSASetEvent, kNetworking, kImplemented);

struct XnAddrStatus {
  // Address acquisition is not yet complete
  static constexpr uint32_t XNET_GET_XNADDR_PENDING = 0x00000000;
  // XNet is uninitialized or no debugger found
  static constexpr uint32_t XNET_GET_XNADDR_NONE = 0x00000001;
  // Host has ethernet address (no IP address)
  static constexpr uint32_t XNET_GET_XNADDR_ETHERNET = 0x00000002;
  // Host has statically assigned IP address
  static constexpr uint32_t XNET_GET_XNADDR_STATIC = 0x00000004;
  // Host has DHCP assigned IP address
  static constexpr uint32_t XNET_GET_XNADDR_DHCP = 0x00000008;
  // Host has PPPoE assigned IP address
  static constexpr uint32_t XNET_GET_XNADDR_PPPOE = 0x00000010;
  // Host has one or more gateways configured
  static constexpr uint32_t XNET_GET_XNADDR_GATEWAY = 0x00000020;
  // Host has one or more DNS servers configured
  static constexpr uint32_t XNET_GET_XNADDR_DNS = 0x00000040;
  // Host is currently connected to online service
  static constexpr uint32_t XNET_GET_XNADDR_ONLINE = 0x00000080;
  // Network configuration requires troubleshooting
  static constexpr uint32_t XNET_GET_XNADDR_TROUBLESHOOT = 0x00008000;
};

dword_result_t NetDll_XNetGetTitleXnAddr_entry(dword_t caller,
                                               pointer_t<XNADDR> addr_ptr) {
  if (!addr_ptr) {
    return XnAddrStatus::XNET_GET_XNADDR_NONE;
  }

  FillTitleXnAddr(addr_ptr);
  auto& xlive_api = GetCodeRedXLiveAPI();
  if (xlive_api.GetInitState() == XLiveAPI::InitState::Pending) {
    xlive_api.Init();
  }
  if (xlive_api.IsSinglePlayerHostEnabled()) {
    xlive_api.SetPlayerPort(system_link_port);
    xlive_api.EnsureSinglePlayerHostSession(kernel_state()->title_id(), 0,
                                            addr_ptr->ina.s_addr);
  }
  if (cvars::net_logging) {
    XELOGI(
        "CodeRED Netplay: XNetGetTitleXnAddr mode={} ip={} online_ip={} "
        "port={} guest_port={}",
        cvars::network_mode, util::IPv4ToString(addr_ptr->ina.s_addr),
        util::IPv4ToString(addr_ptr->inaOnline.s_addr), system_link_port,
        static_cast<uint16_t>(addr_ptr->wPortOnline));
  }

  return XnAddrStatus::XNET_GET_XNADDR_STATIC |
         XnAddrStatus::XNET_GET_XNADDR_ETHERNET;
}
DECLARE_XAM_EXPORT1(NetDll_XNetGetTitleXnAddr, kNetworking, kImplemented);

dword_result_t NetDll_XNetGetDebugXnAddr_entry(dword_t caller,
                                               pointer_t<XNADDR> addr_ptr) {
  addr_ptr.Zero();

  // XNET_GET_XNADDR_NONE causes caller to gracefully return.
  return XnAddrStatus::XNET_GET_XNADDR_NONE;
}
DECLARE_XAM_EXPORT1(NetDll_XNetGetDebugXnAddr, kNetworking, kStub);

dword_result_t NetDll_XNetXnAddrToMachineId_entry(dword_t caller,
                                                  pointer_t<XNADDR> addr_ptr,
                                                  lpdword_t id_ptr) {
  if (!addr_ptr || !id_ptr) {
    return X_ERROR_INVALID_PARAMETER;
  }

  *id_ptr = static_cast<uint32_t>(
      util::MakeMachineId(addr_ptr->ina.s_addr, system_link_port));
  return X_STATUS_SUCCESS;
}
DECLARE_XAM_EXPORT1(NetDll_XNetXnAddrToMachineId, kNetworking, kImplemented);

void NetDll_XNetInAddrToString_entry(dword_t caller, dword_t in_addr,
                                     lpstring_t string_out,
                                     dword_t string_size) {
  const uint32_t network_order_ip = xe::byte_swap(uint32_t(in_addr));
  const std::string value = util::IPv4ToString(network_order_ip);
  strncpy(string_out, value.c_str(), string_size);
}
DECLARE_XAM_EXPORT1(NetDll_XNetInAddrToString, kNetworking, kImplemented);

// This converts a XNet address to an IN_ADDR. The IN_ADDR is used for
// subsequent socket calls (like a handle to a XNet address)
dword_result_t NetDll_XNetXnAddrToInAddr_entry(dword_t caller,
                                               pointer_t<XNADDR> xn_addr,
                                               lpvoid_t xid, lpvoid_t in_addr) {
  if (!xn_addr || !in_addr) {
    return X_ERROR_INVALID_PARAMETER;
  }
  uint32_t target_ip = xn_addr->inaOnline.s_addr ? xn_addr->inaOnline.s_addr
                                                 : xn_addr->ina.s_addr;
  const uint64_t key_id = xid ? ReadGuestBe64(xid.guest_address()) : 0;
  const auto* registered_key = FindRegisteredKeyConst(key_id);
  if (registered_key) {
    target_ip = registered_key->host_address;
  }
  xe::store_and_swap<uint32_t>(in_addr.as<uint8_t*>(), target_ip);
  if (cvars::net_logging) {
    XELOGI("CodeRED Netplay: XNetXnAddrToInAddr key={} ip={} registered={}",
           FormatCodeRedSessionId(key_id), util::IPv4ToString(target_ip),
           registered_key != nullptr);
  }
  return X_STATUS_SUCCESS;
}
DECLARE_XAM_EXPORT1(NetDll_XNetXnAddrToInAddr, kNetworking, kImplemented);

// Does the reverse of the above.
// FIXME: Arguments may not be correct.
dword_result_t NetDll_XNetInAddrToXnAddr_entry(dword_t caller, lpvoid_t in_addr,
                                               pointer_t<XNADDR> xn_addr,
                                               lpvoid_t xid) {
  if (!in_addr || !xn_addr) {
    return X_ERROR_INVALID_PARAMETER;
  }
  const uint32_t network_order_ip =
      xe::load_and_swap<uint32_t>(in_addr.as<const uint8_t*>());
  const uint64_t key_id = xid ? ReadGuestBe64(xid.guest_address()) : 0;
  xn_addr.Zero();
  if (const auto* registered_key = FindRegisteredKeyConst(key_id)) {
    FillXnAddrFromRegisteredKey(xn_addr, *registered_key);
    if (cvars::net_logging) {
      XELOGI("CodeRED Netplay: XNetInAddrToXnAddr key={} ip={} registered=1",
             FormatCodeRedSessionId(key_id),
             util::IPv4ToString(registered_key->host_address));
    }
    return X_STATUS_SUCCESS;
  }
  xn_addr->ina.s_addr = network_order_ip;
  xn_addr->inaOnline.s_addr =
      (cvars::network_mode == 2 || cvars::network_mode == 3)
          ? network_order_ip
          : 0;
  xn_addr->wPortOnline = system_link_port;
  auto mac = util::MakeStableMac(network_order_ip);
  std::memcpy(xn_addr->abEnet, mac.data(), mac.size());
  if (cvars::net_logging) {
    XELOGI("CodeRED Netplay: XNetInAddrToXnAddr key={} ip={} registered=0",
           FormatCodeRedSessionId(key_id), util::IPv4ToString(network_order_ip));
  }
  return X_STATUS_SUCCESS;
}
DECLARE_XAM_EXPORT1(NetDll_XNetInAddrToXnAddr, kNetworking, kImplemented);

// https://www.google.com/patents/WO2008112448A1?cl=en
// Reserves a port for use by system link
dword_result_t NetDll_XNetSetSystemLinkPort_entry(dword_t caller,
                                                  dword_t port) {
  system_link_port = static_cast<uint16_t>(port);
  GetCodeRedXLiveAPI().SetPlayerPort(system_link_port);
  if (cvars::net_logging) {
    XELOGI("CodeRED Netplay: System Link port set to {}", system_link_port);
  }
  return X_STATUS_SUCCESS;
}
DECLARE_XAM_EXPORT1(NetDll_XNetSetSystemLinkPort, kNetworking, kImplemented);

// https://github.com/ILOVEPIE/Cxbx-Reloaded/blob/master/src/CxbxKrnl/EmuXOnline.h#L39
struct XEthernetStatus {
  static constexpr uint32_t XNET_ETHERNET_LINK_ACTIVE = 0x01;
  static constexpr uint32_t XNET_ETHERNET_LINK_100MBPS = 0x02;
  static constexpr uint32_t XNET_ETHERNET_LINK_10MBPS = 0x04;
  static constexpr uint32_t XNET_ETHERNET_LINK_FULL_DUPLEX = 0x08;
  static constexpr uint32_t XNET_ETHERNET_LINK_HALF_DUPLEX = 0x10;
};

dword_result_t NetDll_XNetGetEthernetLinkStatus_entry(dword_t caller) {
  return XEthernetStatus::XNET_ETHERNET_LINK_ACTIVE |
         XEthernetStatus::XNET_ETHERNET_LINK_100MBPS |
         XEthernetStatus::XNET_ETHERNET_LINK_FULL_DUPLEX;
}
DECLARE_XAM_EXPORT1(NetDll_XNetGetEthernetLinkStatus, kNetworking, kImplemented);

dword_result_t NetDll_XNetDnsLookup_entry(dword_t caller, lpstring_t host,
                                          dword_t event_handle,
                                          lpdword_t pdns) {
  // TODO(gibbed): actually implement this
  if (pdns) {
    auto dns_guest = kernel_memory()->SystemHeapAlloc(sizeof(XNDNS));
    auto dns = kernel_memory()->TranslateVirtual<XNDNS*>(dns_guest);
    dns->status = 1;  // non-zero = error
    *pdns = dns_guest;
  }
  if (event_handle) {
    auto ev =
        kernel_state()->object_table()->LookupObject<XEvent>(event_handle);
    assert_not_null(ev);
    ev->Set(0, false);
  }
  return 0;
}
DECLARE_XAM_EXPORT1(NetDll_XNetDnsLookup, kNetworking, kStub);

dword_result_t NetDll_XNetDnsRelease_entry(dword_t caller,
                                           pointer_t<XNDNS> dns) {
  if (!dns) {
    return X_STATUS_INVALID_PARAMETER;
  }
  kernel_memory()->SystemHeapFree(dns.guest_address());
  return 0;
}
DECLARE_XAM_EXPORT1(NetDll_XNetDnsRelease, kNetworking, kStub);

dword_result_t NetDll_XNetQosServiceLookup_entry(dword_t caller, dword_t flags,
                                                 dword_t event_handle,
                                                 lpdword_t pqos) {
  if (pqos) {
    const bool has_qos = qos_listen_state.active;
    auto qos_guest = kernel_memory()->SystemHeapAlloc(sizeof(XNQOS));
    auto qos = kernel_memory()->TranslateVirtual<XNQOS*>(qos_guest);
    std::memset(qos, 0, sizeof(XNQOS));
    qos->count = has_qos ? 1 : 0;
    qos->count_pending = 0;
    if (has_qos) {
      qos->info[0].flags = kQosInfoComplete | kQosInfoTargetContacted |
                           (qos_listen_state.data.empty() ? 0
                                                           : kQosInfoDataReceived);
      qos->info[0].probes_xmit = 1;
      qos->info[0].probes_recv = 1;
      qos->info[0].rtt_min_in_msecs = 1;
      qos->info[0].rtt_med_in_msecs = 1;
      qos->info[0].up_bits_per_sec = 100000000;
      qos->info[0].down_bits_per_sec = 100000000;
      if (!qos_listen_state.data.empty()) {
        auto data_guest = kernel_memory()->SystemHeapAlloc(
            static_cast<uint32_t>(qos_listen_state.data.size()));
        std::memcpy(kernel_memory()->TranslateVirtual(data_guest),
                    qos_listen_state.data.data(), qos_listen_state.data.size());
        qos->info[0].data_len =
            static_cast<uint16_t>(qos_listen_state.data.size());
        qos->info[0].data_ptr = data_guest;
      }
    }
    *pqos = qos_guest;
  }
  SignalEventHandle(event_handle);
  if (cvars::net_logging) {
    XELOGI("CodeRED Netplay: QosServiceLookup active={} flags={:08X}",
           qos_listen_state.active, flags.value());
  }
  return X_STATUS_SUCCESS;
}
DECLARE_XAM_EXPORT1(NetDll_XNetQosServiceLookup, kNetworking, kImplemented);

dword_result_t NetDll_XNetQosRelease_entry(dword_t caller,
                                           pointer_t<XNQOS> qos) {
  if (!qos) {
    return X_STATUS_INVALID_PARAMETER;
  }
  kernel_memory()->SystemHeapFree(qos.guest_address());
  return 0;
}
DECLARE_XAM_EXPORT1(NetDll_XNetQosRelease, kNetworking, kStub);

dword_result_t NetDll_XNetQosListen_entry(dword_t caller, lpvoid_t id,
                                          lpvoid_t data, dword_t data_size,
                                          dword_t r7, dword_t flags) {
  if (flags & kQosListenRelease || flags & kQosListenDisable) {
    qos_listen_state.active = false;
    qos_listen_state.data.clear();
  }
  if (flags & kQosListenSetData) {
    qos_listen_state.data.resize(data_size);
    if (data && data_size) {
      std::memcpy(qos_listen_state.data.data(), data.as<const uint8_t*>(),
                  data_size);
    }
  }
  if (flags & kQosListenEnable) {
    qos_listen_state.active = true;
  }

  if (cvars::net_logging) {
    XELOGI("CodeRED Netplay: QosListen flags={:08X} active={} data_size={}",
           flags.value(), qos_listen_state.active, qos_listen_state.data.size());
  }
  return X_STATUS_SUCCESS;
}
DECLARE_XAM_EXPORT1(NetDll_XNetQosListen, kNetworking, kImplemented);

dword_result_t NetDll_inet_addr_entry(lpstring_t addr_ptr) {
  if (!addr_ptr) {
    return -1;
  }

  uint32_t addr = inet_addr(addr_ptr);
  // https://docs.microsoft.com/en-us/windows/win32/api/winsock2/nf-winsock2-inet_addr#return-value
  // Based on console research it seems like x360 uses old version of inet_addr
  // In case of empty string it return 0 instead of -1
  if (addr == -1 && !addr_ptr.value().length()) {
    return 0;
  }

  return xe::byte_swap(addr);
}
DECLARE_XAM_EXPORT1(NetDll_inet_addr, kNetworking, kImplemented);

dword_result_t NetDll_socket_entry(dword_t caller, dword_t af, dword_t type,
                                   dword_t protocol) {
  XSocket* socket = new XSocket(kernel_state());
  X_STATUS result = socket->Initialize(XSocket::AddressFamily((uint32_t)af),
                                       XSocket::Type((uint32_t)type),
                                       XSocket::Protocol((uint32_t)protocol));

  if (XFAILED(result)) {
    socket->Release();

    XThread::SetLastError(socket->GetLastWSAError());
    XELOGE("NetDll_socket: failed with error {:08X}",
           socket->GetLastWSAError());
    return -1;
  }

  return socket->handle();
}
DECLARE_XAM_EXPORT1(NetDll_socket, kNetworking, kImplemented);

dword_result_t NetDll_closesocket_entry(dword_t caller, dword_t socket_handle) {
  auto socket =
      kernel_state()->object_table()->LookupObject<XSocket>(socket_handle);
  if (!socket) {
    XThread::SetLastError(uint32_t(X_WSAError::X_WSAENOTSOCK));
    return -1;
  }

  // TODO: Absolutely delete this object. It is no longer valid after calling
  // closesocket.
  socket->Close();
  socket->ReleaseHandle();
  return 0;
}
DECLARE_XAM_EXPORT1(NetDll_closesocket, kNetworking, kImplemented);

int_result_t NetDll_shutdown_entry(dword_t caller, dword_t socket_handle,
                                   int_t how) {
  auto socket =
      kernel_state()->object_table()->LookupObject<XSocket>(socket_handle);
  if (!socket) {
    XThread::SetLastError(uint32_t(X_WSAError::X_WSAENOTSOCK));
    return -1;
  }

  auto ret = socket->Shutdown(how);
  if (ret == -1) {
    XThread::SetLastError(socket->GetLastWSAError());
  }
  return ret;
}
DECLARE_XAM_EXPORT1(NetDll_shutdown, kNetworking, kImplemented);

dword_result_t NetDll_setsockopt_entry(dword_t caller, dword_t socket_handle,
                                       dword_t level, dword_t optname,
                                       lpvoid_t optval_ptr, dword_t optlen) {
  auto socket =
      kernel_state()->object_table()->LookupObject<XSocket>(socket_handle);
  if (!socket) {
    XThread::SetLastError(uint32_t(X_WSAError::X_WSAENOTSOCK));
    return -1;
  }

  X_STATUS status = socket->SetOption(level, optname, optval_ptr, optlen);
  return XSUCCEEDED(status) ? 0 : -1;
}
DECLARE_XAM_EXPORT1(NetDll_setsockopt, kNetworking, kImplemented);

dword_result_t NetDll_getsockopt_entry(dword_t caller, dword_t socket_handle,
                                       dword_t level, dword_t optname,
                                       lpvoid_t optval_ptr, lpdword_t optlen) {
  auto socket =
      kernel_state()->object_table()->LookupObject<XSocket>(socket_handle);
  if (!socket) {
    XThread::SetLastError(uint32_t(X_WSAError::X_WSAENOTSOCK));
    return -1;
  }

  uint32_t native_len = *optlen;
  X_STATUS status = socket->GetOption(level, optname, optval_ptr, &native_len);
  return XSUCCEEDED(status) ? 0 : -1;
}
DECLARE_XAM_EXPORT1(NetDll_getsockopt, kNetworking, kImplemented);

dword_result_t NetDll_ioctlsocket_entry(dword_t caller, dword_t socket_handle,
                                        dword_t cmd, lpvoid_t arg_ptr) {
  auto socket =
      kernel_state()->object_table()->LookupObject<XSocket>(socket_handle);
  if (!socket) {
    XThread::SetLastError(uint32_t(X_WSAError::X_WSAENOTSOCK));
    return -1;
  }

  X_STATUS status = socket->IOControl(cmd, arg_ptr);
  if (XFAILED(status)) {
    XThread::SetLastError(socket->GetLastWSAError());
    XELOGE("NetDll_ioctlsocket: failed with error {:08X}",
           socket->GetLastWSAError());
    return -1;
  }

  // TODO
  return 0;
}
DECLARE_XAM_EXPORT1(NetDll_ioctlsocket, kNetworking, kImplemented);

dword_result_t NetDll_bind_entry(dword_t caller, dword_t socket_handle,
                                 pointer_t<XSOCKADDR_IN> name,
                                 dword_t namelen) {
  auto socket =
      kernel_state()->object_table()->LookupObject<XSocket>(socket_handle);
  if (!socket) {
    XThread::SetLastError(uint32_t(X_WSAError::X_WSAENOTSOCK));
    return -1;
  }

  N_XSOCKADDR_IN native_name(name);
  X_STATUS status = socket->Bind(&native_name, namelen);
  if (XFAILED(status)) {
    XThread::SetLastError(socket->GetLastWSAError());
    XELOGE("NetDll_bind: failed with error {:08X}", socket->GetLastWSAError());
    return -1;
  }

  return 0;
}
DECLARE_XAM_EXPORT1(NetDll_bind, kNetworking, kImplemented);

dword_result_t NetDll_connect_entry(dword_t caller, dword_t socket_handle,
                                    pointer_t<XSOCKADDR> name,
                                    dword_t namelen) {
  auto socket =
      kernel_state()->object_table()->LookupObject<XSocket>(socket_handle);
  if (!socket) {
    XThread::SetLastError(uint32_t(X_WSAError::X_WSAENOTSOCK));
    return -1;
  }

  N_XSOCKADDR native_name(name);
  X_STATUS status = socket->Connect(&native_name, namelen);
  if (XFAILED(status)) {
    XThread::SetLastError(socket->GetLastWSAError());
    return -1;
  }

  return 0;
}
DECLARE_XAM_EXPORT1(NetDll_connect, kNetworking, kImplemented);

dword_result_t NetDll_listen_entry(dword_t caller, dword_t socket_handle,
                                   int_t backlog) {
  auto socket =
      kernel_state()->object_table()->LookupObject<XSocket>(socket_handle);
  if (!socket) {
    XThread::SetLastError(uint32_t(X_WSAError::X_WSAENOTSOCK));
    return -1;
  }

  X_STATUS status = socket->Listen(backlog);
  if (XFAILED(status)) {
    XThread::SetLastError(socket->GetLastWSAError());
    return -1;
  }

  return 0;
}
DECLARE_XAM_EXPORT1(NetDll_listen, kNetworking, kImplemented);

dword_result_t NetDll_accept_entry(dword_t caller, dword_t socket_handle,
                                   pointer_t<XSOCKADDR> addr_ptr,
                                   lpdword_t addrlen_ptr) {
  if (!addr_ptr) {
    XThread::SetLastError(uint32_t(X_WSAError::X_WSAEFAULT));
    return -1;
  }

  auto socket =
      kernel_state()->object_table()->LookupObject<XSocket>(socket_handle);
  if (!socket) {
    XThread::SetLastError(uint32_t(X_WSAError::X_WSAENOTSOCK));
    return -1;
  }

  N_XSOCKADDR native_addr(addr_ptr);
  int native_len = *addrlen_ptr;
  auto new_socket = socket->Accept(&native_addr, &native_len);
  if (new_socket) {
    addr_ptr->address_family = native_addr.address_family;
    std::memcpy(addr_ptr->sa_data, native_addr.sa_data, *addrlen_ptr - 2);
    *addrlen_ptr = native_len;

    return new_socket->handle();
  } else {
    return -1;
  }
}
DECLARE_XAM_EXPORT1(NetDll_accept, kNetworking, kImplemented);

struct x_fd_set {
  xe::be<uint32_t> fd_count;
  xe::be<uint32_t> fd_array[64];
};

struct host_set {
  uint32_t count;
  object_ref<XSocket> sockets[64];

  void Load(const x_fd_set* guest_set) {
    assert_true(guest_set->fd_count < 64);
    this->count = guest_set->fd_count;
    for (uint32_t i = 0; i < this->count; ++i) {
      auto socket_handle = static_cast<X_HANDLE>(guest_set->fd_array[i]);
      if (socket_handle == -1) {
        this->count = i;
        break;
      }
      // Convert from Xenia -> native
      auto socket =
          kernel_state()->object_table()->LookupObject<XSocket>(socket_handle);
      assert_not_null(socket);
      this->sockets[i] = socket;
    }
  }

  void Store(x_fd_set* guest_set) {
    guest_set->fd_count = 0;
    for (uint32_t i = 0; i < this->count; ++i) {
      auto socket = this->sockets[i];
      guest_set->fd_array[guest_set->fd_count++] = socket->handle();
    }
  }

  void Store(fd_set* native_set) {
    FD_ZERO(native_set);
    for (uint32_t i = 0; i < this->count; ++i) {
      FD_SET(this->sockets[i]->native_handle(), native_set);
    }
  }

  void UpdateFrom(fd_set* native_set) {
    uint32_t new_count = 0;
    for (uint32_t i = 0; i < this->count; ++i) {
      auto socket = this->sockets[i];
      if (FD_ISSET(socket->native_handle(), native_set)) {
        this->sockets[new_count++] = socket;
      }
    }
    this->count = new_count;
  }
};

int_result_t NetDll_select_entry(dword_t caller, dword_t nfds,
                                 pointer_t<x_fd_set> readfds,
                                 pointer_t<x_fd_set> writefds,
                                 pointer_t<x_fd_set> exceptfds,
                                 lpvoid_t timeout_ptr) {
  host_set host_readfds = {0};
  fd_set native_readfds = {0};
  if (readfds) {
    host_readfds.Load(readfds);
    host_readfds.Store(&native_readfds);
  }
  host_set host_writefds = {0};
  fd_set native_writefds = {0};
  if (writefds) {
    host_writefds.Load(writefds);
    host_writefds.Store(&native_writefds);
  }
  host_set host_exceptfds = {0};
  fd_set native_exceptfds = {0};
  if (exceptfds) {
    host_exceptfds.Load(exceptfds);
    host_exceptfds.Store(&native_exceptfds);
  }
  timeval* timeout_in = nullptr;
  timeval timeout;
  if (timeout_ptr) {
    timeout = {static_cast<int32_t>(timeout_ptr.as_array<int32_t>()[0]),
               static_cast<int32_t>(timeout_ptr.as_array<int32_t>()[1])};
    Clock::ScaleGuestDurationTimeval(
        reinterpret_cast<int32_t*>(&timeout.tv_sec),
        reinterpret_cast<int32_t*>(&timeout.tv_usec));
    timeout_in = &timeout;
  }
  int ret = select(nfds, readfds ? &native_readfds : nullptr,
                   writefds ? &native_writefds : nullptr,
                   exceptfds ? &native_exceptfds : nullptr, timeout_in);
  if (readfds) {
    host_readfds.UpdateFrom(&native_readfds);
    host_readfds.Store(readfds);
  }
  if (writefds) {
    host_writefds.UpdateFrom(&native_writefds);
    host_writefds.Store(writefds);
  }
  if (exceptfds) {
    host_exceptfds.UpdateFrom(&native_exceptfds);
    host_exceptfds.Store(exceptfds);
  }

  // TODO(gibbed): modify ret to be what's actually copied to the guest fd_sets?
  return ret;
}
DECLARE_XAM_EXPORT1(NetDll_select, kNetworking, kImplemented);

dword_result_t NetDll_recv_entry(dword_t caller, dword_t socket_handle,
                                 lpvoid_t buf_ptr, dword_t buf_len,
                                 dword_t flags) {
  auto socket =
      kernel_state()->object_table()->LookupObject<XSocket>(socket_handle);
  if (!socket) {
    XThread::SetLastError(uint32_t(X_WSAError::X_WSAENOTSOCK));
    return -1;
  }

  return socket->Recv(buf_ptr, buf_len, flags);
}
DECLARE_XAM_EXPORT1(NetDll_recv, kNetworking, kImplemented);

dword_result_t NetDll_recvfrom_entry(dword_t caller, dword_t socket_handle,
                                     lpvoid_t buf_ptr, dword_t buf_len,
                                     dword_t flags,
                                     pointer_t<XSOCKADDR_IN> from_ptr,
                                     lpdword_t fromlen_ptr) {
  auto socket =
      kernel_state()->object_table()->LookupObject<XSocket>(socket_handle);
  if (!socket) {
    XThread::SetLastError(uint32_t(X_WSAError::X_WSAENOTSOCK));
    return -1;
  }

  N_XSOCKADDR_IN native_from;
  if (from_ptr) {
    native_from = *from_ptr;
  }
  uint32_t native_fromlen = fromlen_ptr ? fromlen_ptr.value() : 0;
  int ret = socket->RecvFrom(buf_ptr, buf_len, flags, &native_from,
                             fromlen_ptr ? &native_fromlen : 0);

  if (from_ptr) {
    from_ptr->sin_family = native_from.sin_family;
    from_ptr->sin_port = native_from.sin_port;
    from_ptr->sin_addr = native_from.sin_addr;
    std::memset(from_ptr->x_sin_zero, 0, sizeof(from_ptr->x_sin_zero));
  }
  if (fromlen_ptr) {
    *fromlen_ptr = native_fromlen;
  }

  if (ret == -1) {
    static uint32_t recvfrom_wouldblock_log_count = 0;
    static uint32_t recvfrom_bootstrap_inject_count = 0;
    const uint32_t error = socket->GetLastWSAError();
    if (error == kWSAEWOULDBLOCK &&
        ShouldInjectUdpBootstrap(recvfrom_bootstrap_inject_count)) {
      const int injected =
          InjectUdpBootstrapPacket(socket_handle, buf_ptr, buf_len,
                                   from_ptr ? &native_from : nullptr,
                                   fromlen_ptr ? &native_fromlen : nullptr,
                                   "recvfrom");
      if (injected > 0) {
        if (from_ptr) {
          from_ptr->sin_family = native_from.sin_family;
          from_ptr->sin_port = native_from.sin_port;
          from_ptr->sin_addr = native_from.sin_addr;
          std::memset(from_ptr->x_sin_zero, 0, sizeof(from_ptr->x_sin_zero));
        }
        if (fromlen_ptr) {
          *fromlen_ptr = native_fromlen;
        }
        return injected;
      }
    }
    XThread::SetLastError(error);
    if (cvars::net_logging &&
        (error != kWSAEWOULDBLOCK ||
         ShouldLogEvery(recvfrom_wouldblock_log_count, 120))) {
      XELOGD(
          "CodeRED Netplay: recvfrom socket={:08X} len={} flags={} mode={} "
          "port={} error={}",
          socket_handle.value(), buf_len.value(), flags.value(),
          cvars::network_mode, system_link_port, error);
    }
  } else if (cvars::net_logging) {
    XELOGD(
        "CodeRED Netplay: recvfrom socket={:08X} bytes={} from={}:{} "
        "preview={}",
        socket_handle.value(), ret, util::IPv4ToString(native_from.sin_addr),
        ntohs(uint16_t(native_from.sin_port)),
        HexPreviewGuest(buf_ptr.guest_address(), static_cast<uint32_t>(ret)));
  }

  return ret;
}
DECLARE_XAM_EXPORT1(NetDll_recvfrom, kNetworking, kImplemented);

dword_result_t NetDll_send_entry(dword_t caller, dword_t socket_handle,
                                 lpvoid_t buf_ptr, dword_t buf_len,
                                 dword_t flags) {
  auto socket =
      kernel_state()->object_table()->LookupObject<XSocket>(socket_handle);
  if (!socket) {
    XThread::SetLastError(uint32_t(X_WSAError::X_WSAENOTSOCK));
    return -1;
  }

  return socket->Send(buf_ptr, buf_len, flags);
}
DECLARE_XAM_EXPORT1(NetDll_send, kNetworking, kImplemented);

dword_result_t NetDll_sendto_entry(dword_t caller, dword_t socket_handle,
                                   lpvoid_t buf_ptr, dword_t buf_len,
                                   dword_t flags,
                                   pointer_t<XSOCKADDR_IN> to_ptr,
                                   dword_t to_len) {
  auto socket =
      kernel_state()->object_table()->LookupObject<XSocket>(socket_handle);
  if (!socket) {
    XThread::SetLastError(uint32_t(X_WSAError::X_WSAENOTSOCK));
    return -1;
  }

  N_XSOCKADDR_IN native_to(to_ptr);
  int ret = socket->SendTo(buf_ptr, buf_len, flags, &native_to, to_len);
  if (ret == -1) {
    XThread::SetLastError(socket->GetLastWSAError());
    if (cvars::net_logging) {
      XELOGD("CodeRED Netplay: sendto socket={:08X} len={} error={}",
             socket_handle.value(), buf_len.value(), socket->GetLastWSAError());
    }
  } else if (cvars::net_logging) {
    XELOGD(
        "CodeRED Netplay: sendto socket={:08X} bytes={} to={}:{} preview={}",
        socket_handle.value(), ret, util::IPv4ToString(native_to.sin_addr),
        ntohs(uint16_t(native_to.sin_port)),
        HexPreviewGuest(buf_ptr.guest_address(), buf_len.value()));
  }
  return ret;
}
DECLARE_XAM_EXPORT1(NetDll_sendto, kNetworking, kImplemented);

dword_result_t NetDll___WSAFDIsSet_entry(dword_t socket_handle,
                                         pointer_t<x_fd_set> fd_set) {
  const uint8_t max_fd_count =
      std::min((uint32_t)fd_set->fd_count, uint32_t(64));
  for (uint8_t i = 0; i < max_fd_count; i++) {
    if (fd_set->fd_array[i] == socket_handle) {
      return 1;
    }
  }
  return 0;
}
DECLARE_XAM_EXPORT1(NetDll___WSAFDIsSet, kNetworking, kImplemented);

void NetDll_WSASetLastError_entry(dword_t error_code) {
  XThread::SetLastError(error_code);
}
DECLARE_XAM_EXPORT1(NetDll_WSASetLastError, kNetworking, kImplemented);

dword_result_t NetDll_getsockname_entry(dword_t caller, dword_t socket_handle,
                                        lpvoid_t buf_ptr, lpdword_t len_ptr) {
  auto socket =
      kernel_state()->object_table()->LookupObject<XSocket>(socket_handle);
  if (!socket) {
    XThread::SetLastError(uint32_t(X_WSAError::X_WSAENOTSOCK));
    return -1;
  }

  int buffer_len = *len_ptr;

  X_STATUS status = socket->GetSockName(buf_ptr, &buffer_len);
  if (XFAILED(status)) {
    XThread::SetLastError(socket->GetLastWSAError());
    return -1;
  }

  *len_ptr = buffer_len;
  return 0;
}
DECLARE_XAM_EXPORT1(NetDll_getsockname, kNetworking, kImplemented);

dword_result_t NetDll_XNetCreateKey_entry(dword_t caller, lpdword_t key_id,
                                          lpdword_t exchange_key) {
  if (!key_id || !exchange_key) {
    return X_ERROR_INVALID_PARAMETER;
  }

  const uint64_t id = MakeCreatedKeyId();
  const uint32_t host_ip = GetConfiguredTitleIp();
  const auto key = MakeCodeRedSessionKey(id, host_ip, system_link_port);
  WriteGuestBe64(key_id.guest_address(), id);
  WriteGuestKey(exchange_key.guest_address(), key);

  if (cvars::net_logging) {
    XELOGI("CodeRED Netplay: XNetCreateKey id={} ip={} port={}",
           FormatCodeRedSessionId(id), util::IPv4ToString(host_ip),
           system_link_port);
  }
  return X_STATUS_SUCCESS;
}
DECLARE_XAM_EXPORT1(NetDll_XNetCreateKey, kNetworking, kImplemented);

dword_result_t NetDll_XNetRegisterKey_entry(dword_t caller, lpdword_t key_id,
                                            lpdword_t exchange_key) {
  if (!key_id || !exchange_key) {
    return X_ERROR_INVALID_PARAMETER;
  }

  CodeRedRegisteredKey registered_key;
  registered_key.id = ReadGuestBe64(key_id.guest_address());
  registered_key.exchange_key = ReadGuestKey(exchange_key.guest_address());
  registered_key.host_address = GetConfiguredTitleIp();
  registered_key.port = system_link_port;
  registered_key.mac = util::MakeStableMac(registered_key.host_address);

  if (const auto session = GetCodeRedXLiveAPI().GetSessionDetails(
          kernel_state()->title_id(), registered_key.id)) {
    registered_key.host_address = session->host_address;
    registered_key.port = session->port;
    registered_key.mac = session->mac;
    if (IsZeroKey(registered_key.exchange_key)) {
      registered_key.exchange_key = session->key_exchange;
    }
  }
  if (IsZeroKey(registered_key.exchange_key)) {
    registered_key.exchange_key = MakeCodeRedSessionKey(
        registered_key.id, registered_key.host_address, registered_key.port);
  }

  UpsertRegisteredKey(registered_key);
  if (cvars::net_logging) {
    XELOGI(
        "CodeRED Netplay: XNetRegisterKey id={} ip={} port={} keys={}",
        FormatCodeRedSessionId(registered_key.id),
        util::IPv4ToString(registered_key.host_address), registered_key.port,
        registered_keys.size());
  }
  return X_STATUS_SUCCESS;
}
DECLARE_XAM_EXPORT1(NetDll_XNetRegisterKey, kNetworking, kImplemented);

dword_result_t NetDll_XNetUnregisterKey_entry(dword_t caller,
                                              lpdword_t key_id) {
  if (!key_id) {
    return X_ERROR_INVALID_PARAMETER;
  }
  const uint64_t id = ReadGuestBe64(key_id.guest_address());
  const auto old_size = registered_keys.size();
  registered_keys.erase(
      std::remove_if(registered_keys.begin(), registered_keys.end(),
                     [id](const CodeRedRegisteredKey& key) {
                       return key.id == id;
                     }),
      registered_keys.end());
  if (cvars::net_logging) {
    XELOGI("CodeRED Netplay: XNetUnregisterKey id={} removed={}",
           FormatCodeRedSessionId(id), old_size != registered_keys.size());
  }
  return X_STATUS_SUCCESS;
}
DECLARE_XAM_EXPORT1(NetDll_XNetUnregisterKey, kNetworking, kImplemented);

}  // namespace xam
}  // namespace kernel
}  // namespace xe

DECLARE_XAM_EMPTY_REGISTER_EXPORTS(Net);
