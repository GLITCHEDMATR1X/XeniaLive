/**
 ******************************************************************************
 * Xenia : Xbox 360 Emulator Research Project                                 *
 ******************************************************************************
 * Code RED minimal private-host HTTP client.                                  *
 * Released under the BSD license - see LICENSE in the root for more details. *
 ******************************************************************************
 */

#include "xenia/kernel/util/http_client.h"

#include <algorithm>
#include <cctype>
#include <cstring>
#include <sstream>
#include <string>
#include <vector>

#include "xenia/base/platform.h"

#ifdef XE_PLATFORM_WIN32
#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <ws2tcpip.h>
#else
#include <cerrno>
#include <netdb.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>
#endif

namespace xe {
namespace kernel {
namespace util {

namespace {

#ifdef XE_PLATFORM_WIN32
using SocketHandle = SOCKET;
constexpr SocketHandle kInvalidSocket = INVALID_SOCKET;
void CloseSocket(SocketHandle socket) { closesocket(socket); }
#else
using SocketHandle = int;
constexpr SocketHandle kInvalidSocket = -1;
void CloseSocket(SocketHandle socket) { close(socket); }
#endif

struct ParsedUrl {
  std::string host;
  std::string port = "80";
  std::string path = "/";
};

bool ParseHttpUrl(const std::string& url, ParsedUrl* out,
                  std::string* error) {
  constexpr char kScheme[] = "http://";
  if (url.rfind(kScheme, 0) != 0) {
    *error = "only plain http:// private-host URLs are supported";
    return false;
  }

  const size_t authority_start = sizeof(kScheme) - 1;
  const size_t path_start = url.find('/', authority_start);
  const std::string authority = path_start == std::string::npos
                                    ? url.substr(authority_start)
                                    : url.substr(authority_start,
                                                 path_start - authority_start);
  out->path = path_start == std::string::npos ? "/" : url.substr(path_start);
  if (authority.empty()) {
    *error = "empty HTTP host";
    return false;
  }

  const size_t colon = authority.rfind(':');
  if (colon != std::string::npos) {
    out->host = authority.substr(0, colon);
    out->port = authority.substr(colon + 1);
  } else {
    out->host = authority;
  }

  if (out->host.empty() || out->port.empty()) {
    *error = "invalid HTTP host or port";
    return false;
  }
  return true;
}

bool SendAll(SocketHandle socket, const std::string& data) {
  size_t sent_total = 0;
  while (sent_total < data.size()) {
#ifdef XE_PLATFORM_WIN32
    const int sent = send(socket, data.data() + sent_total,
                          static_cast<int>(data.size() - sent_total), 0);
#else
    const ssize_t sent = send(socket, data.data() + sent_total,
                              data.size() - sent_total, 0);
#endif
    if (sent <= 0) {
      return false;
    }
    sent_total += static_cast<size_t>(sent);
  }
  return true;
}

std::string TrimLeft(std::string value) {
  value.erase(value.begin(), std::find_if(value.begin(), value.end(),
                                          [](unsigned char ch) {
                                            return !std::isspace(ch);
                                          }));
  return value;
}

HttpResponse DoHttpRequest(const std::string& method, const std::string& url,
                           const std::string& body, const char* content_type,
                           uint32_t timeout_ms) {
  ParsedUrl parsed;
  HttpResponse response;
  if (!ParseHttpUrl(url, &parsed, &response.error)) {
    return response;
  }

#ifdef XE_PLATFORM_WIN32
  WSADATA wsa_data;
  WSAStartup(MAKEWORD(2, 2), &wsa_data);
#endif

  addrinfo hints{};
  hints.ai_family = AF_UNSPEC;
  hints.ai_socktype = SOCK_STREAM;
  hints.ai_protocol = IPPROTO_TCP;

  addrinfo* results = nullptr;
  const int gai_result = getaddrinfo(parsed.host.c_str(), parsed.port.c_str(),
                                     &hints, &results);
  if (gai_result != 0 || !results) {
    response.error = "getaddrinfo failed for " + parsed.host + ":" + parsed.port;
    return response;
  }

  SocketHandle socket = kInvalidSocket;
  for (addrinfo* item = results; item; item = item->ai_next) {
    socket = ::socket(item->ai_family, item->ai_socktype, item->ai_protocol);
    if (socket == kInvalidSocket) {
      continue;
    }

#ifdef XE_PLATFORM_WIN32
    const DWORD timeout = timeout_ms;
    setsockopt(socket, SOL_SOCKET, SO_RCVTIMEO,
               reinterpret_cast<const char*>(&timeout), sizeof(timeout));
    setsockopt(socket, SOL_SOCKET, SO_SNDTIMEO,
               reinterpret_cast<const char*>(&timeout), sizeof(timeout));
#else
    timeval timeout{};
    timeout.tv_sec = static_cast<long>(timeout_ms / 1000);
    timeout.tv_usec = static_cast<long>((timeout_ms % 1000) * 1000);
    setsockopt(socket, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));
    setsockopt(socket, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout));
#endif

    if (connect(socket, item->ai_addr,
                static_cast<int>(item->ai_addrlen)) == 0) {
      break;
    }

    CloseSocket(socket);
    socket = kInvalidSocket;
  }
  freeaddrinfo(results);

  if (socket == kInvalidSocket) {
    response.error = "connect failed for " + parsed.host + ":" + parsed.port;
    return response;
  }

  std::ostringstream request;
  request << method << " " << parsed.path << " HTTP/1.1\r\n";
  request << "Host: " << parsed.host << ":" << parsed.port << "\r\n";
  request << "User-Agent: Xenia-CodeRED-Netplay/1\r\n";
  request << "Connection: close\r\n";
  if (!body.empty()) {
    request << "Content-Type: " << (content_type ? content_type : "text/plain")
            << "\r\n";
    request << "Content-Length: " << body.size() << "\r\n";
  }
  request << "\r\n";
  request << body;

  if (!SendAll(socket, request.str())) {
    CloseSocket(socket);
    response.error = "send failed";
    return response;
  }

  std::string raw;
  char buffer[4096];
  for (;;) {
#ifdef XE_PLATFORM_WIN32
    const int read = recv(socket, buffer, sizeof(buffer), 0);
#else
    const ssize_t read = recv(socket, buffer, sizeof(buffer), 0);
#endif
    if (read <= 0) {
      break;
    }
    raw.append(buffer, buffer + read);
  }
  CloseSocket(socket);

  const size_t status_end = raw.find("\r\n");
  if (status_end == std::string::npos) {
    response.error = "malformed HTTP response";
    return response;
  }

  std::istringstream status_line(raw.substr(0, status_end));
  std::string http_version;
  status_line >> http_version >> response.status_code;

  const size_t header_end = raw.find("\r\n\r\n");
  if (header_end != std::string::npos) {
    response.body = raw.substr(header_end + 4);
  }

  response.ok = response.status_code >= 200 && response.status_code < 300;
  if (!response.ok && response.error.empty()) {
    response.error = "HTTP " + std::to_string(response.status_code) + ": " +
                     TrimLeft(response.body);
  }
  return response;
}

}  // namespace

HttpResponse HttpGet(const std::string& url, uint32_t timeout_ms) {
  return DoHttpRequest("GET", url, "", nullptr, timeout_ms);
}

HttpResponse HttpPostJson(const std::string& url, const std::string& json_body,
                          uint32_t timeout_ms) {
  return DoHttpRequest("POST", url, json_body, "application/json", timeout_ms);
}

HttpResponse HttpDelete(const std::string& url, uint32_t timeout_ms) {
  return DoHttpRequest("DELETE", url, "", nullptr, timeout_ms);
}

}  // namespace util
}  // namespace kernel
}  // namespace xe
