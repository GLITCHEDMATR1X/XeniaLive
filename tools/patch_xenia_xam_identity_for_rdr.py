#!/usr/bin/env python3
"""
Code RED private Xenia/XAM profile consistency patcher for RDR offline freeroam tests.

Run from the Xenia source root. It patches source only; it does not patch xenia_canary.exe.
Backups are written next to changed files as *.codered_pass6_bak.
"""
from __future__ import annotations

import argparse
import datetime as _dt
from pathlib import Path
import sys


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="")


def replace_section(text: str, start_marker: str, end_marker: str, replacement: str) -> tuple[str, bool]:
    start = text.find(start_marker)
    if start < 0:
        return text, False
    end = text.find(end_marker, start)
    if end < 0:
        return text, False
    end += len(end_marker)
    return text[:start] + replacement.rstrip() + "\n" + text[end:], True


def backup(path: Path) -> Path:
    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = path.with_name(path.name + f".codered_pass6_bak_{stamp}")
    backup_path.write_bytes(path.read_bytes())
    return backup_path


XAM_USER_REPLACEMENTS = [
    (
        "X_HRESULT_result_t XamUserGetXUID_entry(",
        "DECLARE_XAM_EXPORT1(XamUserGetXUID, kUserProfiles, kImplemented);",
        r'''X_HRESULT_result_t XamUserGetXUID_entry(dword_t user_index, dword_t type_mask,
                                        lpqword_t xuid_ptr) {
  assert_true(type_mask == 1 || type_mask == 2 || type_mask == 3 ||
              type_mask == 4 || type_mask == 7);
  if (!xuid_ptr) {
    return X_E_INVALIDARG;
  }

  *xuid_ptr = 0;
  if (user_index >= XUserMaxUserCount) {
    return X_E_INVALIDARG;
  }
  if (!kernel_state()->xam_state()->IsUserSignedIn(user_index)) {
    return X_E_NO_SUCH_USER;
  }

  // Code RED RDR local-freeroam profile consistency:
  // Always return the loaded profile XUID for both offline and online mask
  // requests. RDR repeatedly asks for type_mask=7 during MP load and later
  // content/profile paths become fragile if any route sees a zero XUID.
  const auto& user_profile = kernel_state()->xam_state()->GetUserProfile(user_index);
  *xuid_ptr = user_profile->xuid();
  return X_E_SUCCESS;
}
DECLARE_XAM_EXPORT1(XamUserGetXUID, kUserProfiles, kImplemented);'''
    ),
    (
        "dword_result_t XamUserGetSigninState_entry(",
        "DECLARE_XAM_EXPORT2(XamUserGetSigninState, kUserProfiles, kImplemented, kHighFrequency);",
        r'''dword_result_t XamUserGetSigninState_entry(dword_t user_index) {
  if (user_index >= XUserMaxUserCount) {
    return 0;
  }
  if (!kernel_state()->xam_state()->IsUserSignedIn(user_index)) {
    return 0;
  }

  // Code RED RDR local-freeroam profile consistency:
  // Report the selected local profile as Live-signed-in for games that gate
  // MP load behind XAM sign-in state. This does not connect to Xbox Live.
  return static_cast<uint32_t>(SignInState::SignedInToLive);
}
DECLARE_XAM_EXPORT2(XamUserGetSigninState, kUserProfiles, kImplemented, kHighFrequency);'''
    ),
    (
        "X_HRESULT_result_t XamUserGetSigninInfo_entry(",
        "DECLARE_XAM_EXPORT1(XamUserGetSigninInfo, kUserProfiles, kImplemented);",
        r'''X_HRESULT_result_t XamUserGetSigninInfo_entry(
    dword_t user_index, dword_t flags, pointer_t<X_USER_SIGNIN_INFO> info) {
  if (!info) {
    return X_E_INVALIDARG;
  }
  info.Zero();
  if (user_index >= XUserMaxUserCount) {
    return X_E_NO_SUCH_USER;
  }
  if (!kernel_state()->xam_state()->IsUserSignedIn(user_index)) {
    return X_E_NO_SUCH_USER;
  }

  const auto& user_profile = kernel_state()->xam_state()->GetUserProfile(user_index);
  xe::string_util::copy_truncating(info->name, user_profile->name(),
                                   xe::countof(info->name));

  // Code RED RDR local-freeroam profile consistency:
  // Populate the XUID even when the caller asks for online/live-style info and
  // force the sign-in state to SignedInToLive. This is local emulator identity
  // only and does not authenticate with official services.
  info->xuid = user_profile->xuid();
  info->signin_state = static_cast<uint32_t>(SignInState::SignedInToLive);
  return X_E_SUCCESS;
}
DECLARE_XAM_EXPORT1(XamUserGetSigninInfo, kUserProfiles, kImplemented);'''
    ),
    (
        "dword_result_t XamUserCheckPrivilege_entry(",
        "DECLARE_XAM_EXPORT1(XamUserCheckPrivilege, kUserProfiles, kStub);",
        r'''dword_result_t XamUserCheckPrivilege_entry(dword_t user_index, dword_t mask,
                                           lpdword_t out_value) {
  if (user_index == XUserIndexAny) {
    user_index = 0;
  }
  if (user_index >= XUserMaxUserCount) {
    return X_ERROR_INVALID_PARAMETER;
  }
  if (!kernel_state()->xam_state()->IsUserSignedIn(user_index)) {
    return X_ERROR_NO_SUCH_USER;
  }

  // Code RED RDR local-freeroam profile consistency:
  // Grant local multiplayer/system-link style privilege checks so RDR can keep
  // moving through its Free Roam load path under Xenia. This is not Xbox Live
  // authentication and should remain for local/offline research only.
  if (out_value) {
    *out_value = 1;
  }
  return X_ERROR_SUCCESS;
}
DECLARE_XAM_EXPORT1(XamUserCheckPrivilege, kUserProfiles, kStub);'''
    ),
]


def patch_xam_user(root: Path) -> list[str]:
    candidates = [
        root / "src" / "xenia" / "kernel" / "xam" / "xam_user.cc",
        root / "src" / "xenia" / "kernel" / "xam_user.cc",
    ]
    xam_user = next((p for p in candidates if p.exists()), None)
    if not xam_user:
        return ["ERROR: xam_user.cc not found under src/xenia/kernel/xam or src/xenia/kernel."]

    original = read_text(xam_user)
    text = original
    messages = []
    for start, end, replacement in XAM_USER_REPLACEMENTS:
        text, ok = replace_section(text, start, end, replacement)
        messages.append(("OK" if ok else "MISS") + f": {start}")

    if text != original:
        bak = backup(xam_user)
        write_text(xam_user, text)
        messages.insert(0, f"Patched {xam_user}")
        messages.insert(1, f"Backup {bak}")
    else:
        messages.insert(0, f"No changes written to {xam_user}")
    return messages


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".", help="Xenia source root")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    print(f"Code RED XAM identity patcher root: {root}")
    messages = patch_xam_user(root)
    for msg in messages:
        print(msg)
    if any(m.startswith("ERROR") for m in messages):
        return 2
    if any(m.startswith("MISS") for m in messages):
        print("\nAt least one marker was not found. Review xam_user.cc manually before building.")
        return 1
    print("\nPatch complete. Rebuild Xenia Canary from this source tree.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
