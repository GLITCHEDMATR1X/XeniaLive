/**
 ******************************************************************************
 * Xenia : Xbox 360 Emulator Research Project                                 *
 ******************************************************************************
 * Copyright 2021 Ben Vanik. All rights reserved.                             *
 * Released under the BSD license - see LICENSE in the root for more details. *
 ******************************************************************************
 */

#include "xenia/kernel/xam/apps/xgi_app.h"
#include "xenia/kernel/XLiveAPI.h"
#include "xenia/kernel/xsession.h"

#include "xenia/base/logging.h"

#include <algorithm>
#include <array>

namespace xe {
namespace kernel {
namespace xam {
namespace apps {
/*
 * Most of the structs below were found in the Source SDK, provided as stubs.
 * Specifically, they can be found in the Source 2007 SDK and the Alien Swarm
 * Source SDK. Both are available on Steam for free. A GitHub mirror of the
 * Alien Swarm SDK can be found here:
 * https://github.com/NicolasDe/AlienSwarm/blob/master/src/common/xbox/xboxstubs.h
 */

struct XGI_XUSER_ACHIEVEMENT {
  xe::be<uint32_t> user_index;
  xe::be<uint32_t> achievement_id;
};
static_assert_size(XGI_XUSER_ACHIEVEMENT, 0x8);

struct XGI_XUSER_GET_PROPERTY {
  xe::be<uint32_t> user_index;
  xe::be<uint32_t> unused;
  xe::be<uint64_t> xuid;  // If xuid is 0 then user_index is used.
  xe::be<uint32_t>
      property_size_ptr;  // Normally filled with sizeof(XUSER_PROPERTY), with
                          // exception of binary and wstring type.
  xe::be<uint32_t> context_address;
  xe::be<uint32_t> property_address;
};
static_assert_size(XGI_XUSER_GET_PROPERTY, 0x20);

struct XGI_XUSER_SET_CONTEXT {
  xe::be<uint32_t> user_index;
  xe::be<uint32_t> unused;
  xe::be<uint64_t> xuid;
  XUSER_CONTEXT context;
};
static_assert_size(XGI_XUSER_SET_CONTEXT, 0x18);

struct XGI_XUSER_SET_PROPERTY {
  xe::be<uint32_t> user_index;
  xe::be<uint32_t> unused;
  xe::be<uint64_t> xuid;
  xe::be<uint32_t> property_id;
  xe::be<uint32_t> data_size;
  xe::be<uint32_t> data_address;
};
static_assert_size(XGI_XUSER_SET_PROPERTY, 0x20);

struct XUSER_STATS_VIEW {
  xe::be<uint32_t> ViewId;
  xe::be<uint32_t> TotalViewRows;
  xe::be<uint32_t> NumRows;
  xe::be<uint32_t> pRows;
};

struct XUSER_STATS_COLUMN {
  xe::be<uint16_t> ColumnId;
  X_USER_DATA Value;
};

struct XUSER_STATS_RESET {
  xe::be<uint32_t> user_index;
  xe::be<uint32_t> view_id;
};

struct XUSER_ANID {
  xe::be<uint32_t> user_index;
  xe::be<uint32_t> cchAnIdBuffer;
  xe::be<uint32_t> pszAnIdBuffer;
  xe::be<uint32_t> value_const;  // 1
};


namespace {
struct CodeRedGuestResultBuffer {
  bool valid = false;
  uint32_t ptr = 0;
  uint32_t size = 0;
  uint32_t max_results = 16;
  const char* source = "fallback";
};

struct CodeRedGuestDetailsBuffer {
  bool valid = false;
  uint32_t session_ptr = 0;
  uint32_t ptr = 0;
  uint32_t size = 0;
  const char* source = "unknown";
};

bool LooksLikeGuestPtr(uint32_t value) {
  return value >= 0x10000 && value < 0xE0000000;
}

bool LooksLikeResultSize(uint32_t value) {
  return value >= kCodeRedXSessionSearchResultHeaderSize && value <= 0x40000;
}

uint32_t ReadU32(uint8_t* buffer, uint32_t offset, uint32_t buffer_length) {
  if (!buffer || offset + sizeof(uint32_t) > buffer_length) {
    return 0;
  }
  return xe::load_and_swap<uint32_t>(buffer + offset);
}

uint32_t ReadGuestU32OrValue(Memory* memory, uint32_t value) {
  if (!memory || !LooksLikeGuestPtr(value)) {
    return value;
  }
  auto value_ptr = memory->TranslateVirtual<xe::be<uint32_t>*>(value);
  return value_ptr ? static_cast<uint32_t>(*value_ptr) : value;
}

CodeRedGuestResultBuffer GuessResultBuffer(uint8_t* buffer,
                                           uint32_t buffer_length) {
  CodeRedGuestResultBuffer guess;
  if (!buffer || buffer_length < 8) {
    return guess;
  }

  const uint32_t word_count = std::min<uint32_t>(buffer_length / 4, 16);
  std::array<uint32_t, 16> words{};
  for (uint32_t i = 0; i < word_count; ++i) {
    words[i] = xe::load_and_swap<uint32_t>(buffer + i * 4);
    if (words[i] > 0 && words[i] <= 64) {
      guess.max_results = words[i];
    }
  }

  for (uint32_t i = 0; i + 1 < word_count; ++i) {
    if (LooksLikeGuestPtr(words[i]) && LooksLikeResultSize(words[i + 1])) {
      guess.valid = true;
      guess.ptr = words[i];
      guess.size = words[i + 1];
      return guess;
    }
    if (LooksLikeResultSize(words[i]) && LooksLikeGuestPtr(words[i + 1])) {
      guess.valid = true;
      guess.ptr = words[i + 1];
      guess.size = words[i];
      return guess;
    }
  }
  return guess;
}

CodeRedGuestResultBuffer ReadXSessionSearchBuffer(uint8_t* buffer,
                                                  uint32_t buffer_length) {
  // XGI_SESSION_SEARCH, 0x20:
  //   +0x08 num_results
  //   +0x18 results_buffer_size
  //   +0x1C search_results_ptr
  if (buffer && buffer_length >= 0x20) {
    CodeRedGuestResultBuffer exact;
    exact.max_results = std::max<uint32_t>(1, ReadU32(buffer, 0x08, buffer_length));
    exact.size = ReadU32(buffer, 0x18, buffer_length);
    exact.ptr = ReadU32(buffer, 0x1C, buffer_length);
    exact.source = "XGI_SESSION_SEARCH";
    exact.valid = LooksLikeGuestPtr(exact.ptr) && LooksLikeResultSize(exact.size);
    if (exact.valid) {
      return exact;
    }
  }
  return GuessResultBuffer(buffer, buffer_length);
}

CodeRedGuestResultBuffer ReadXSessionSearchByIdsOrWeightedBuffer(
    uint8_t* buffer, uint32_t buffer_length) {
  // XGI_SESSION_SEARCH_WEIGHTED, 0x34:
  //   +0x08 num_results
  //   +0x28 results_buffer_size
  //   +0x2C search_results_ptr
  if (buffer && buffer_length >= 0x34) {
    CodeRedGuestResultBuffer exact;
    exact.max_results = std::max<uint32_t>(1, ReadU32(buffer, 0x08, buffer_length));
    exact.size = ReadU32(buffer, 0x28, buffer_length);
    exact.ptr = ReadU32(buffer, 0x2C, buffer_length);
    exact.source = "XGI_SESSION_SEARCH_WEIGHTED";
    exact.valid = LooksLikeGuestPtr(exact.ptr) && LooksLikeResultSize(exact.size);
    if (exact.valid) {
      return exact;
    }
  }

  // XGI_SESSION_SEARCH_BYIDS, 0x20:
  //   +0x04 num_session_ids
  //   +0x0C results_buffer_size
  //   +0x10 search_results_ptr
  if (buffer && buffer_length >= 0x20) {
    CodeRedGuestResultBuffer exact;
    exact.max_results = std::max<uint32_t>(1, ReadU32(buffer, 0x04, buffer_length));
    exact.size = ReadU32(buffer, 0x0C, buffer_length);
    exact.ptr = ReadU32(buffer, 0x10, buffer_length);
    exact.source = "XGI_SESSION_SEARCH_BYIDS";
    exact.valid = LooksLikeGuestPtr(exact.ptr) && LooksLikeResultSize(exact.size);
    if (exact.valid) {
      return exact;
    }
  }

  return GuessResultBuffer(buffer, buffer_length);
}

CodeRedGuestDetailsBuffer ReadXSessionDetailsBuffer(Memory* memory,
                                                    uint8_t* buffer,
                                                    uint32_t buffer_length) {
  CodeRedGuestDetailsBuffer details;
  // XGI_SESSION_DETAILS, 0x18:
  //   +0x00 obj_ptr/session object pointer
  //   +0x04 details_buffer_size or pointer to size
  //   +0x08 session_details_ptr
  if (!buffer || buffer_length < 0x0C) {
    return details;
  }
  details.session_ptr = ReadU32(buffer, 0x00, buffer_length);
  details.size = ReadGuestU32OrValue(memory, ReadU32(buffer, 0x04, buffer_length));
  details.ptr = ReadU32(buffer, 0x08, buffer_length);
  details.source = "XGI_SESSION_DETAILS";
  details.valid = LooksLikeGuestPtr(details.ptr) &&
                  details.size >= kCodeRedXSessionLocalDetailsSize &&
                  details.size <= 0x40000;
  return details;
}
}  // namespace
XgiApp::XgiApp(KernelState* kernel_state) : App(kernel_state, 0xFB) {}

// http://mb.mirage.org/bugzilla/xliveless/main.c

X_HRESULT XgiApp::DispatchMessageSync(uint32_t message, uint32_t buffer_ptr,
                                      uint32_t buffer_length) {
  // NOTE: buffer_length may be zero or valid.
  auto buffer = memory_->TranslateVirtual(buffer_ptr);
  switch (message) {
    case 0x000B0006: {
      assert_true(!buffer_length ||
                  buffer_length == sizeof(XGI_XUSER_SET_CONTEXT));
      const XGI_XUSER_SET_CONTEXT* xgi_context =
          reinterpret_cast<const XGI_XUSER_SET_CONTEXT*>(buffer);

      XELOGD("XGIUserSetContext({:08X}, ID: {:08X}, Value: {:08X})",
             xgi_context->user_index.get(),
             xgi_context->context.context_id.get(),
             xgi_context->context.value.get());

      UserProfile* user = nullptr;
      if (xgi_context->xuid != 0) {
        user = kernel_state_->xam_state()->GetUserProfile(xgi_context->xuid);
      } else {
        user =
            kernel_state_->xam_state()->GetUserProfile(xgi_context->user_index);
      }

      if (user) {
        kernel_state_->xam_state()->user_tracker()->UpdateContext(
            user->xuid(), xgi_context->context.context_id,
            xgi_context->context.value);
      }
      return X_E_SUCCESS;
    }
    case 0x000B0007: {
      assert_true(!buffer_length ||
                  buffer_length == sizeof(XGI_XUSER_SET_PROPERTY));
      const XGI_XUSER_SET_PROPERTY* xgi_property =
          reinterpret_cast<const XGI_XUSER_SET_PROPERTY*>(buffer);

      XELOGD("XGIUserSetPropertyEx({:08X}, {:08X}, {}, {:08X})",
             xgi_property->user_index.get(), xgi_property->property_id.get(),
             xgi_property->data_size.get(), xgi_property->data_address.get());

      UserProfile* user = nullptr;
      if (xgi_property->xuid != 0) {
        user = kernel_state_->xam_state()->GetUserProfile(xgi_property->xuid);
      } else {
        user = kernel_state_->xam_state()->GetUserProfile(
            xgi_property->user_index);
      }

      if (user) {
        Property property(
            xgi_property->property_id,
            Property::get_valid_data_size(xgi_property->property_id,
                                          xgi_property->data_size),
            memory_->TranslateVirtual<uint8_t*>(xgi_property->data_address));

        kernel_state_->xam_state()->user_tracker()->AddProperty(user->xuid(),
                                                                &property);
      }
      return X_E_SUCCESS;
    }
    case 0x000B0008: {
      assert_true(!buffer_length ||
                  buffer_length == sizeof(XGI_XUSER_ACHIEVEMENT));
      uint32_t achievement_count = xe::load_and_swap<uint32_t>(buffer + 0);
      uint32_t achievements_ptr = xe::load_and_swap<uint32_t>(buffer + 4);
      XELOGD("XGIUserWriteAchievements({:08X}, {:08X})", achievement_count,
             achievements_ptr);

      auto* achievement =
          memory_->TranslateVirtual<XGI_XUSER_ACHIEVEMENT*>(achievements_ptr);
      for (uint32_t i = 0; i < achievement_count; i++, achievement++) {
        kernel_state_->achievement_manager()->EarnAchievement(
            achievement->user_index, kernel_state_->title_id(),
            achievement->achievement_id);
      }
      return X_E_SUCCESS;
    }
    case 0x000B0010: {
      XELOGD("XSessionCreate({:08X}, {:08X}), implemented in netplay",
             buffer_ptr, buffer_length);
      assert_true(!buffer_length || buffer_length == 28);
      // Sequence:
      // - XamSessionCreateHandle
      // - XamSessionRefObjByHandle
      // - [this]
      // - CloseHandle
      uint32_t session_ptr = xe::load_and_swap<uint32_t>(buffer + 0x0);
      uint32_t flags = xe::load_and_swap<uint32_t>(buffer + 0x4);
      uint32_t num_slots_public = xe::load_and_swap<uint32_t>(buffer + 0x8);
      uint32_t num_slots_private = xe::load_and_swap<uint32_t>(buffer + 0xC);
      uint32_t user_xuid = xe::load_and_swap<uint32_t>(buffer + 0x10);
      uint32_t session_info_ptr = xe::load_and_swap<uint32_t>(buffer + 0x14);
      uint32_t nonce_ptr = xe::load_and_swap<uint32_t>(buffer + 0x18);

      XELOGD(
          "XGISessionCreateImpl({:08X}, {:08X}, {}, {}, {:08X}, {:08X}, "
          "{:08X})",
          session_ptr, flags, num_slots_public, num_slots_private, user_xuid,
          session_info_ptr, nonce_ptr);

      auto& xlive_api = GetCodeRedXLiveAPI();
      if (xlive_api.GetInitState() == XLiveAPI::InitState::Pending) {
        xlive_api.Init();
      }

      const auto session_flags = static_cast<SessionFlags>(flags);
      if (IsXboxLiveSession(session_flags) && !xlive_api.IsPrivateHostMode()) {
        return 0x80155209;  // X_ONLINE_E_SESSION_NOT_LOGGED_ON
      }

      if (IsNetworkSession(session_flags) || xlive_api.IsNetworkEnabled()) {
        auto session = xlive_api.CreateHostSession(
            kernel_state_->title_id(), session_ptr, flags, num_slots_public,
            num_slots_private, user_xuid, 0);
        XELOGI("CodeRED Netplay: XSessionCreate accepted title={:08X} "
               "session={} info={:08X} nonce={:08X}",
               kernel_state_->title_id(), FormatCodeRedSessionId(session.id),
               session_info_ptr, nonce_ptr);
      }

      return X_E_SUCCESS;
    }
    case 0x000B0011: {
      XELOGD("XGISessionDelete({:08X}, {:08X}), implemented in netplay",
             buffer_ptr, buffer_length);
      if (buffer_length >= 4) {
        uint32_t session_ptr = xe::load_and_swap<uint32_t>(buffer + 0x0);
        GetCodeRedXLiveAPI().DeleteSession(session_ptr);
      }
      return X_STATUS_SUCCESS;
    }
    case 0x000B0012: {
      assert_true(buffer_length == 0x14);
      uint32_t session_ptr = xe::load_and_swap<uint32_t>(buffer + 0x0);
      uint32_t user_count = xe::load_and_swap<uint32_t>(buffer + 0x4);
      uint32_t unk_0 = xe::load_and_swap<uint32_t>(buffer + 0x8);
      uint32_t user_index_array = xe::load_and_swap<uint32_t>(buffer + 0xC);
      uint32_t private_slots_array = xe::load_and_swap<uint32_t>(buffer + 0x10);

      assert_zero(unk_0);
      XELOGD("XGISessionJoinLocal({:08X}, {}, {}, {:08X}, {:08X})", session_ptr,
             user_count, unk_0, user_index_array, private_slots_array);

      std::vector<uint64_t> xuids;
      std::vector<bool> private_slots;
      for (uint32_t i = 0; i < user_count; ++i) {
        uint32_t user_index = i;
        if (user_index_array) {
          user_index = xe::load_and_swap<uint32_t>(
              memory_->TranslateVirtual<uint8_t*>(user_index_array + i * 4));
        }
        UserProfile* user = kernel_state_->xam_state()->GetUserProfile(user_index);
        xuids.push_back(user ? user->xuid() : user_index);

        bool private_slot = false;
        if (private_slots_array) {
          private_slot = xe::load_and_swap<uint32_t>(
                             memory_->TranslateVirtual<uint8_t*>(
                                 private_slots_array + i * 4)) != 0;
        }
        private_slots.push_back(private_slot);
      }
      GetCodeRedXLiveAPI().JoinLocalUsers(session_ptr, xuids, private_slots);
      return X_E_SUCCESS;
    }
    case 0x000B0013: {
      uint32_t session_ptr = buffer_length >= 4
                                 ? xe::load_and_swap<uint32_t>(buffer + 0x0)
                                 : 0;
      uint32_t user_count = buffer_length >= 8
                                ? xe::load_and_swap<uint32_t>(buffer + 0x4)
                                : 0;
      uint32_t user_index_array = buffer_length >= 0x10
                                      ? xe::load_and_swap<uint32_t>(buffer + 0xC)
                                      : 0;
      XELOGD("XGISessionLeaveLocal({:08X}, {}, {:08X})", session_ptr,
             user_count, user_index_array);
      std::vector<uint64_t> xuids;
      for (uint32_t i = 0; i < user_count; ++i) {
        uint32_t user_index = i;
        if (user_index_array) {
          user_index = xe::load_and_swap<uint32_t>(
              memory_->TranslateVirtual<uint8_t*>(user_index_array + i * 4));
        }
        UserProfile* user = kernel_state_->xam_state()->GetUserProfile(user_index);
        xuids.push_back(user ? user->xuid() : user_index);
      }
      GetCodeRedXLiveAPI().LeaveLocalUsers(session_ptr, xuids);
      return X_E_SUCCESS;
    }
    case 0x000B0014: {
      // Gets 584107FB in game.
      // get high score table?
      XELOGD("XSessionStart({:08X}), implemented in netplay", buffer_ptr);
      uint32_t session_ptr = buffer_length >= 4
                                 ? xe::load_and_swap<uint32_t>(buffer + 0x0)
                                 : buffer_ptr;
      GetCodeRedXLiveAPI().StartSession(session_ptr);
      return X_STATUS_SUCCESS;
    }
    case 0x000B0015: {
      // send high scores?
      XELOGD("XSessionEnd({:08X}, {:08X}), implemented in netplay", buffer_ptr,
             buffer_length);
      uint32_t session_ptr = buffer_length >= 4
                                 ? xe::load_and_swap<uint32_t>(buffer + 0x0)
                                 : buffer_ptr;
      GetCodeRedXLiveAPI().EndSession(session_ptr);
      return X_STATUS_SUCCESS;
    }
    case 0x000B0016: {
      XELOGD("XSessionSearch({:08X}, {:08X}), CodeRED private-host bridge",
             buffer_ptr, buffer_length);
      auto& xlive_api = GetCodeRedXLiveAPI();
      if (xlive_api.GetInitState() == XLiveAPI::InitState::Pending) {
        xlive_api.Init();
      }
      auto search_buffer = ReadXSessionSearchBuffer(buffer, buffer_length);
      auto sessions = xlive_api.SearchSessions(kernel_state_->title_id(),
                                               search_buffer.max_results);
      if (search_buffer.valid) {
        auto fill = FillCodeRedSessionSearchResults(
            memory_, search_buffer.ptr, search_buffer.size, sessions);
        XELOGI("CodeRED Netplay: XSessionSearch source={} filled={} count={} ptr={:08X} size={} note={}",
               search_buffer.source, fill.wrote, fill.result_count,
               search_buffer.ptr, search_buffer.size, fill.note);
      } else {
        XELOGI("CodeRED Netplay: XSessionSearch found {} sessions but no safe result buffer was detected. layout={}",
               sessions.size(), DescribeCodeRedSessionSearchLayout());
      }
      return X_E_SUCCESS;
    }
    case 0x000B0017: {
      XELOGD("XSessionGetDetails({:08X}, {:08X}), CodeRED private-host bridge",
             buffer_ptr, buffer_length);
      auto& xlive_api = GetCodeRedXLiveAPI();
      if (xlive_api.GetInitState() == XLiveAPI::InitState::Pending) {
        xlive_api.Init();
      }
      auto details_buffer = ReadXSessionDetailsBuffer(memory_, buffer,
                                                      buffer_length);
      auto session = xlive_api.GetSession(details_buffer.session_ptr);
      if (!session.has_value()) {
        auto sessions = xlive_api.SearchSessions(kernel_state_->title_id(), 1);
        if (!sessions.empty()) {
          session = sessions.front();
        }
      }
      if (details_buffer.valid && session.has_value()) {
        auto fill = FillCodeRedSessionDetails(
            memory_, details_buffer.ptr, details_buffer.size, *session);
        XELOGI("CodeRED Netplay: XSessionGetDetails source={} filled={} ptr={:08X} size={} note={}",
               details_buffer.source, fill.wrote, details_buffer.ptr,
               details_buffer.size, fill.note);
      } else {
        XELOGI("CodeRED Netplay: XSessionGetDetails no safe details buffer/session. valid={} session={} layout={}",
               details_buffer.valid, session.has_value(),
               DescribeCodeRedSessionDetailsLayout());
      }
      return X_E_SUCCESS;
    }
    case 0x000B0018: {
      XELOGD("XSessionSearchByIDs/Weighted({:08X}, {:08X}), CodeRED bridge",
             buffer_ptr, buffer_length);
      auto& xlive_api = GetCodeRedXLiveAPI();
      if (xlive_api.GetInitState() == XLiveAPI::InitState::Pending) {
        xlive_api.Init();
      }
      auto search_buffer =
          ReadXSessionSearchByIdsOrWeightedBuffer(buffer, buffer_length);
      auto sessions = xlive_api.SearchSessions(kernel_state_->title_id(),
                                               search_buffer.max_results);
      if (search_buffer.valid) {
        auto fill = FillCodeRedSessionSearchResults(
            memory_, search_buffer.ptr, search_buffer.size, sessions);
        XELOGI("CodeRED Netplay: XSessionSearchByIDs/Weighted source={} filled={} count={} ptr={:08X} size={}",
               search_buffer.source, fill.wrote, fill.result_count,
               search_buffer.ptr, search_buffer.size);
      } else {
        XELOGI("CodeRED Netplay: XSessionSearchByIDs/Weighted found {} sessions but no safe result buffer was detected. layout={}",
               sessions.size(), DescribeCodeRedSessionSearchLayout());
      }
      return X_E_SUCCESS;
    }
    case 0x000B0021: {
      XELOGD("XUserReadStats");

      struct XUserReadStats {
        xe::be<uint32_t> titleId;
        xe::be<uint32_t> xuids_count;
        xe::be<uint32_t> xuids_guest_address;
        xe::be<uint32_t> specs_count;
        xe::be<uint32_t> specs_guest_address;
        xe::be<uint32_t> results_size;
        xe::be<uint32_t> results_guest_address;
      }* data = reinterpret_cast<XUserReadStats*>(buffer);

      return 0x80151802;  // X_ONLINE_E_LOGON_NOT_LOGGED_ON
    }
    case 0x000B0036: {
      // Called after opening xbox live arcade and clicking on xbox live v5759
      // to 5787 and called after clicking xbox live in the game library from
      // v6683 to v6717
      // Does not get sent a buffer
      XELOGD("XInvalidateGamerTileCache, unimplemented");
      return X_E_FAIL;
    }
    case 0x000B003D: {
      // Used in 5451082A, 5553081E
      // XUserGetCachedANID
      XELOGI("XUserGetANID({:08X}, {:08X}), implemented in netplay", buffer_ptr,
             buffer_length);
      return X_E_FAIL;
    }
    case 0x000B0041: {
      assert_true(!buffer_length ||
                  buffer_length == sizeof(XGI_XUSER_GET_PROPERTY));
      const XGI_XUSER_GET_PROPERTY* xgi_property =
          reinterpret_cast<const XGI_XUSER_GET_PROPERTY*>(buffer);

      UserProfile* user = nullptr;
      if (xgi_property->xuid != 0) {
        user = kernel_state_->xam_state()->GetUserProfile(xgi_property->xuid);
      } else {
        user = kernel_state_->xam_state()->GetUserProfile(
            xgi_property->user_index);
      }

      if (!user) {
        XELOGD(
            "XGIUserGetProperty - Invalid user provided: Index: {:08X} XUID: "
            "{:16X}",
            xgi_property->user_index.get(), xgi_property->xuid.get());
        return X_E_NOTFOUND;
      }

      // Process context
      if (xgi_property->context_address) {
        XUSER_CONTEXT* context = memory_->TranslateVirtual<XUSER_CONTEXT*>(
            xgi_property->context_address);

        XELOGD("XGIUserGetProperty - Context requested: {:08X} XUID: {:16X}",
               context->context_id.get(), user->xuid());

        auto context_value =
            kernel_state_->xam_state()->user_tracker()->GetUserContext(
                user->xuid(), context->context_id);

        if (!context_value) {
          return X_E_INVALIDARG;
        }

        context->value = context_value.value();
        return X_E_SUCCESS;
      }

      if (!xgi_property->property_size_ptr || !xgi_property->property_address) {
        return X_E_INVALIDARG;
      }

      // Process property
      XUSER_PROPERTY* property = memory_->TranslateVirtual<XUSER_PROPERTY*>(
          xgi_property->property_address);

      XELOGD("XGIUserGetProperty - Property requested: {:08X} XUID: {:16X}",
             property->property_id.get(), user->xuid());

      return kernel_state_->xam_state()->user_tracker()->GetProperty(
          user->xuid(),
          memory_->TranslateVirtual<uint32_t*>(xgi_property->property_size_ptr),
          property);
    }
    case 0x000B0071: {
      XELOGD("ContentEnumerate::ResetEnumerator({:08X}, {:08X}), unimplemented",
             buffer_ptr, buffer_length);
      return X_E_SUCCESS;
    }
  }
  XELOGE(
      "Unimplemented XGI message app={:08X}, msg={:08X}, arg1={:08X}, "
      "arg2={:08X}",
      app_id(), message, buffer_ptr, buffer_length);
  return X_E_FAIL;
}

}  // namespace apps
}  // namespace xam
}  // namespace kernel
}  // namespace xe
