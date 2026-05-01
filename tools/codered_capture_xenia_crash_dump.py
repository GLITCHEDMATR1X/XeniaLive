#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ctypes
import datetime as dt
import struct
import subprocess
import sys
from pathlib import Path


DEBUG_ONLY_THIS_PROCESS = 0x00000002
DBG_CONTINUE = 0x00010002
DBG_EXCEPTION_NOT_HANDLED = 0x80010001
EXCEPTION_DEBUG_EVENT = 1
EXIT_PROCESS_DEBUG_EVENT = 5
EXCEPTION_BREAKPOINT = 0x80000003
CPP_EXCEPTION = 0xE06D7363
ACCESS_VIOLATION = 0xC0000005
IMAGE_FILE_MACHINE_AMD64 = 0x8664
ADDR_MODE_FLAT = 1
THREAD_ALL_ACCESS = 0x001F03FF
CONTEXT_AMD64 = 0x00100000
CONTEXT_CONTROL = 0x00000001
CONTEXT_INTEGER = 0x00000002
CONTEXT_FLOATING_POINT = 0x00000008
CONTEXT_FULL = CONTEXT_AMD64 | CONTEXT_CONTROL | CONTEXT_INTEGER | CONTEXT_FLOATING_POINT
SYMOPT_UNDNAME = 0x00000002
SYMOPT_DEFERRED_LOADS = 0x00000004
SYMOPT_LOAD_LINES = 0x00000010

MiniDumpNormal = 0x00000000
MiniDumpWithDataSegs = 0x00000001
MiniDumpWithHandleData = 0x00000004
MiniDumpWithUnloadedModules = 0x00000020
MiniDumpWithThreadInfo = 0x00001000
MINIDUMP_TYPE = (
    MiniDumpNormal
    | MiniDumpWithDataSegs
    | MiniDumpWithHandleData
    | MiniDumpWithUnloadedModules
    | MiniDumpWithThreadInfo
)


class STARTUPINFO(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_ulong),
        ("lpReserved", ctypes.c_wchar_p),
        ("lpDesktop", ctypes.c_wchar_p),
        ("lpTitle", ctypes.c_wchar_p),
        ("dwX", ctypes.c_ulong),
        ("dwY", ctypes.c_ulong),
        ("dwXSize", ctypes.c_ulong),
        ("dwYSize", ctypes.c_ulong),
        ("dwXCountChars", ctypes.c_ulong),
        ("dwYCountChars", ctypes.c_ulong),
        ("dwFillAttribute", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("wShowWindow", ctypes.c_ushort),
        ("cbReserved2", ctypes.c_ushort),
        ("lpReserved2", ctypes.c_void_p),
        ("hStdInput", ctypes.c_void_p),
        ("hStdOutput", ctypes.c_void_p),
        ("hStdError", ctypes.c_void_p),
    ]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", ctypes.c_void_p),
        ("hThread", ctypes.c_void_p),
        ("dwProcessId", ctypes.c_ulong),
        ("dwThreadId", ctypes.c_ulong),
    ]


class EXCEPTION_RECORD(ctypes.Structure):
    _fields_ = [
        ("ExceptionCode", ctypes.c_ulong),
        ("ExceptionFlags", ctypes.c_ulong),
        ("ExceptionRecord", ctypes.c_void_p),
        ("ExceptionAddress", ctypes.c_void_p),
        ("NumberParameters", ctypes.c_ulong),
        ("ExceptionInformation", ctypes.c_ulonglong * 15),
    ]


class EXCEPTION_DEBUG_INFO(ctypes.Structure):
    _fields_ = [
        ("ExceptionRecord", EXCEPTION_RECORD),
        ("dwFirstChance", ctypes.c_ulong),
    ]


class DEBUG_EVENT_UNION(ctypes.Union):
    _fields_ = [
        ("Exception", EXCEPTION_DEBUG_INFO),
        ("raw", ctypes.c_byte * 160),
    ]


class DEBUG_EVENT(ctypes.Structure):
    _fields_ = [
        ("dwDebugEventCode", ctypes.c_ulong),
        ("dwProcessId", ctypes.c_ulong),
        ("dwThreadId", ctypes.c_ulong),
        ("u", DEBUG_EVENT_UNION),
    ]


class M128A(ctypes.Structure):
    _fields_ = [("Low", ctypes.c_ulonglong), ("High", ctypes.c_longlong)]


class CONTEXT64(ctypes.Structure):
    _fields_ = [
        ("P1Home", ctypes.c_ulonglong),
        ("P2Home", ctypes.c_ulonglong),
        ("P3Home", ctypes.c_ulonglong),
        ("P4Home", ctypes.c_ulonglong),
        ("P5Home", ctypes.c_ulonglong),
        ("P6Home", ctypes.c_ulonglong),
        ("ContextFlags", ctypes.c_ulong),
        ("MxCsr", ctypes.c_ulong),
        ("SegCs", ctypes.c_ushort),
        ("SegDs", ctypes.c_ushort),
        ("SegEs", ctypes.c_ushort),
        ("SegFs", ctypes.c_ushort),
        ("SegGs", ctypes.c_ushort),
        ("SegSs", ctypes.c_ushort),
        ("EFlags", ctypes.c_ulong),
        ("Dr0", ctypes.c_ulonglong),
        ("Dr1", ctypes.c_ulonglong),
        ("Dr2", ctypes.c_ulonglong),
        ("Dr3", ctypes.c_ulonglong),
        ("Dr6", ctypes.c_ulonglong),
        ("Dr7", ctypes.c_ulonglong),
        ("Rax", ctypes.c_ulonglong),
        ("Rcx", ctypes.c_ulonglong),
        ("Rdx", ctypes.c_ulonglong),
        ("Rbx", ctypes.c_ulonglong),
        ("Rsp", ctypes.c_ulonglong),
        ("Rbp", ctypes.c_ulonglong),
        ("Rsi", ctypes.c_ulonglong),
        ("Rdi", ctypes.c_ulonglong),
        ("R8", ctypes.c_ulonglong),
        ("R9", ctypes.c_ulonglong),
        ("R10", ctypes.c_ulonglong),
        ("R11", ctypes.c_ulonglong),
        ("R12", ctypes.c_ulonglong),
        ("R13", ctypes.c_ulonglong),
        ("R14", ctypes.c_ulonglong),
        ("R15", ctypes.c_ulonglong),
        ("Rip", ctypes.c_ulonglong),
        ("FltSave", ctypes.c_byte * 512),
        ("VectorRegister", M128A * 26),
        ("VectorControl", ctypes.c_ulonglong),
        ("DebugControl", ctypes.c_ulonglong),
        ("LastBranchToRip", ctypes.c_ulonglong),
        ("LastBranchFromRip", ctypes.c_ulonglong),
        ("LastExceptionToRip", ctypes.c_ulonglong),
        ("LastExceptionFromRip", ctypes.c_ulonglong),
    ]


class ADDRESS64(ctypes.Structure):
    _fields_ = [
        ("Offset", ctypes.c_ulonglong),
        ("Segment", ctypes.c_ushort),
        ("Mode", ctypes.c_ulong),
    ]


class KDHELP64(ctypes.Structure):
    _fields_ = [
        ("Thread", ctypes.c_ulonglong),
        ("ThCallbackStack", ctypes.c_ulong),
        ("ThCallbackBStore", ctypes.c_ulong),
        ("NextCallback", ctypes.c_ulong),
        ("FramePointer", ctypes.c_ulong),
        ("KiCallUserMode", ctypes.c_ulonglong),
        ("KeUserCallbackDispatcher", ctypes.c_ulonglong),
        ("SystemRangeStart", ctypes.c_ulonglong),
        ("KiUserExceptionDispatcher", ctypes.c_ulonglong),
        ("StackBase", ctypes.c_ulonglong),
        ("StackLimit", ctypes.c_ulonglong),
        ("BuildVersion", ctypes.c_ulonglong),
        ("RetpolineStubFunctionTableSize", ctypes.c_ulonglong),
        ("RetpolineStubFunctionTable", ctypes.c_ulonglong),
        ("RetpolineStubOffset", ctypes.c_ulonglong),
        ("RetpolineStubSize", ctypes.c_ulonglong),
        ("Reserved0", ctypes.c_ulonglong * 2),
    ]


class STACKFRAME64(ctypes.Structure):
    _fields_ = [
        ("AddrPC", ADDRESS64),
        ("AddrReturn", ADDRESS64),
        ("AddrFrame", ADDRESS64),
        ("AddrStack", ADDRESS64),
        ("AddrBStore", ADDRESS64),
        ("FuncTableEntry", ctypes.c_void_p),
        ("Params", ctypes.c_ulonglong * 4),
        ("Far", ctypes.c_bool),
        ("Virtual", ctypes.c_bool),
        ("Reserved", ctypes.c_ulonglong * 3),
        ("KdHelp", KDHELP64),
    ]


class IMAGEHLP_LINE64(ctypes.Structure):
    _fields_ = [
        ("SizeOfStruct", ctypes.c_ulong),
        ("Key", ctypes.c_void_p),
        ("LineNumber", ctypes.c_ulong),
        ("FileName", ctypes.c_char_p),
        ("Address", ctypes.c_ulonglong),
    ]


def win32_error() -> ctypes.WinError:
    return ctypes.WinError(ctypes.get_last_error())


def symbol_name(dbghelp: ctypes.WinDLL, process_handle: int, address: int) -> str | None:
    max_name = 1024
    # SYMBOL_INFO has a trailing one-byte Name field; allocate extra bytes for it.
    symbol_size = 88 + max_name
    symbol = ctypes.create_string_buffer(symbol_size)
    ctypes.memset(symbol, 0, symbol_size)
    ctypes.c_ulong.from_buffer(symbol, 0).value = 88
    ctypes.c_ulong.from_buffer(symbol, 84).value = max_name
    displacement = ctypes.c_ulonglong()
    if not dbghelp.SymFromAddr(process_handle, address, ctypes.byref(displacement), symbol):
        return None
    name_len = ctypes.c_ulong.from_buffer(symbol, 80).value
    raw_name = bytes(symbol[88 : 88 + name_len]).decode("utf-8", errors="replace")
    name = f"{raw_name}+0x{displacement.value:X}"
    line = IMAGEHLP_LINE64()
    line.SizeOfStruct = ctypes.sizeof(IMAGEHLP_LINE64)
    line_disp = ctypes.c_ulong()
    if dbghelp.SymGetLineFromAddr64(process_handle, address, ctypes.byref(line_disp), ctypes.byref(line)):
        file_name = line.FileName.decode("utf-8", errors="replace") if line.FileName else "?"
        name += f" ({file_name}:{line.LineNumber})"
    return name


def resolve_symbol(dbghelp: ctypes.WinDLL, process_handle: int, address: int) -> str:
    return symbol_name(dbghelp, process_handle, address) or f"0x{address:016X}"


def write_stack_trace(process_handle: int, thread_id: int, stack_path: Path) -> None:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    dbghelp = ctypes.WinDLL("dbghelp", use_last_error=True)
    dbghelp.SymSetOptions(SYMOPT_UNDNAME | SYMOPT_DEFERRED_LOADS | SYMOPT_LOAD_LINES)
    dbghelp.SymInitializeW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_bool]
    dbghelp.SymInitializeW.restype = ctypes.c_bool
    dbghelp.SymFromAddr.argtypes = [ctypes.c_void_p, ctypes.c_ulonglong, ctypes.POINTER(ctypes.c_ulonglong), ctypes.c_void_p]
    dbghelp.SymFromAddr.restype = ctypes.c_bool
    dbghelp.SymGetLineFromAddr64.argtypes = [
        ctypes.c_void_p,
        ctypes.c_ulonglong,
        ctypes.POINTER(ctypes.c_ulong),
        ctypes.POINTER(IMAGEHLP_LINE64),
    ]
    dbghelp.SymGetLineFromAddr64.restype = ctypes.c_bool
    dbghelp.StackWalk64.argtypes = [
        ctypes.c_ulong,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(STACKFRAME64),
        ctypes.POINTER(CONTEXT64),
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
    ]
    dbghelp.StackWalk64.restype = ctypes.c_bool

    thread_handle = kernel32.OpenThread(THREAD_ALL_ACCESS, False, thread_id)
    if not thread_handle:
        raise win32_error()
    try:
        context = CONTEXT64()
        context.ContextFlags = CONTEXT_FULL
        if not kernel32.GetThreadContext(thread_handle, ctypes.byref(context)):
            raise win32_error()
        if not dbghelp.SymInitializeW(process_handle, None, True):
            raise win32_error()
        frame = STACKFRAME64()
        frame.AddrPC.Offset = context.Rip
        frame.AddrPC.Mode = ADDR_MODE_FLAT
        frame.AddrStack.Offset = context.Rsp
        frame.AddrStack.Mode = ADDR_MODE_FLAT
        frame.AddrFrame.Offset = context.Rbp
        frame.AddrFrame.Mode = ADDR_MODE_FLAT
        access = dbghelp.SymFunctionTableAccess64
        base = dbghelp.SymGetModuleBase64
        lines = [
            f"ThreadId: {thread_id}",
            f"RIP=0x{context.Rip:016X} RSP=0x{context.Rsp:016X} RBP=0x{context.Rbp:016X}",
            "",
            "Stack:",
        ]
        for index in range(96):
            if not dbghelp.StackWalk64(
                IMAGE_FILE_MACHINE_AMD64,
                process_handle,
                thread_handle,
                ctypes.byref(frame),
                ctypes.byref(context),
                None,
                access,
                base,
                None,
            ):
                break
            if not frame.AddrPC.Offset:
                break
            lines.append(f"{index:02d} 0x{frame.AddrPC.Offset:016X} {resolve_symbol(dbghelp, process_handle, frame.AddrPC.Offset)}")
        if len(lines) <= 4:
            lines.extend(["", "Stack memory symbol scan:"])
            read_process_memory = kernel32.ReadProcessMemory
            read_process_memory.argtypes = [
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.c_size_t,
                ctypes.POINTER(ctypes.c_size_t),
            ]
            read_process_memory.restype = ctypes.c_bool
            size = 0x8000
            buffer = ctypes.create_string_buffer(size)
            read = ctypes.c_size_t()
            if read_process_memory(process_handle, ctypes.c_void_p(context.Rsp), buffer, size, ctypes.byref(read)):
                seen: set[int] = set()
                count = 0
                raw = buffer.raw[: read.value]
                for offset in range(0, max(0, len(raw) - 8), 8):
                    value = struct.unpack_from("<Q", raw, offset)[0]
                    if value in seen or value < 0x0000000100000000 or value > 0x00007FFFFFFFFFFF:
                        continue
                    name = symbol_name(dbghelp, process_handle, value)
                    if not name:
                        continue
                    seen.add(value)
                    lines.append(f"rsp+0x{offset:04X} 0x{value:016X} {name}")
                    count += 1
                    if count >= 80:
                        break
            else:
                lines.append(f"ReadProcessMemory failed: {win32_error()}")
        stack_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    finally:
        kernel32.CloseHandle(thread_handle)


def read_target(process_handle: int, address: int, size: int) -> bytes:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    buffer = ctypes.create_string_buffer(size)
    read = ctypes.c_size_t()
    if not kernel32.ReadProcessMemory(process_handle, ctypes.c_void_p(address), buffer, size, ctypes.byref(read)):
        raise win32_error()
    return buffer.raw[: read.value]


def read_i32(process_handle: int, address: int) -> int:
    return struct.unpack("<i", read_target(process_handle, address, 4))[0]


def read_c_string(process_handle: int, address: int, limit: int = 512) -> str:
    raw = read_target(process_handle, address, limit)
    raw = raw.split(b"\x00", 1)[0]
    return raw.decode("utf-8", errors="replace")


def decode_msvc_cxx_exception(process_handle: int, params: list[int]) -> str:
    if len(params) < 4 or params[0] != 0x19930520:
        return ""
    object_address = params[1]
    throw_info = params[2]
    image_base = params[3]
    if throw_info < image_base:
        throw_info = image_base + throw_info
    try:
        catchable_array_rva = read_i32(process_handle, throw_info + 12)
        catchable_array = image_base + catchable_array_rva
        count = read_i32(process_handle, catchable_array)
        if count < 1 or count > 64:
            return f"cxx_object=0x{object_address:016X} cxx_type=<invalid catchable count {count}>"
        catchable_type_rva = read_i32(process_handle, catchable_array + 4)
        catchable_type = image_base + catchable_type_rva
        type_descriptor_rva = read_i32(process_handle, catchable_type + 4)
        type_descriptor = image_base + type_descriptor_rva
        decorated_name = read_c_string(process_handle, type_descriptor + 16)
        object_preview = read_target(process_handle, object_address, 96).hex(" ")
        return (
            f"cxx_object=0x{object_address:016X} "
            f"cxx_type={decorated_name} "
            f"object_bytes={object_preview}"
        )
    except Exception as exc:
        return f"cxx_object=0x{object_address:016X} cxx_decode_failed={exc}"


def write_dump(process_handle: int, pid: int, dump_path: Path) -> None:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    dbghelp = ctypes.WinDLL("dbghelp", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_void_p,
    ]
    create_file.restype = ctypes.c_void_p
    handle = create_file(str(dump_path), 0x40000000, 0, None, 2, 0x80, None)
    if handle == ctypes.c_void_p(-1).value:
        raise win32_error()
    try:
        mini_dump_write_dump = dbghelp.MiniDumpWriteDump
        mini_dump_write_dump.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        mini_dump_write_dump.restype = ctypes.c_bool
        if not mini_dump_write_dump(process_handle, pid, handle, MINIDUMP_TYPE, None, None, None):
            raise win32_error()
    finally:
        kernel32.CloseHandle(handle)


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch Xenia under a tiny crash-dump debugger.")
    parser.add_argument("--exe", required=True)
    parser.add_argument("--game", required=True)
    parser.add_argument("--cwd", required=True)
    parser.add_argument("--dump-dir", required=True)
    ns = parser.parse_args()

    exe = Path(ns.exe)
    game = Path(ns.game)
    cwd = Path(ns.cwd)
    dump_dir = Path(ns.dump_dir)
    dump_dir.mkdir(parents=True, exist_ok=True)

    # Keep the private host alive if the one-click script did not leave one running.
    try:
        import urllib.request
        urllib.request.urlopen("http://127.0.0.1:36000/health", timeout=1).close()
    except Exception:
        subprocess.Popen(
            [sys.executable, str(Path(__file__).with_name("codered_rdr_private_host.py")), "--host", "0.0.0.0", "--port", "36000"],
            cwd=str(Path(__file__).resolve().parents[1]),
        )

    command = f'"{exe}" "{game}"'
    startup = STARTUPINFO()
    startup.cb = ctypes.sizeof(startup)
    process_info = PROCESS_INFORMATION()

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    if not kernel32.CreateProcessW(
        None,
        ctypes.create_unicode_buffer(command),
        None,
        None,
        False,
        DEBUG_ONLY_THIS_PROCESS,
        None,
        str(cwd),
        ctypes.byref(startup),
        ctypes.byref(process_info),
    ):
        raise win32_error()

    print(f"Started Xenia pid={process_info.dwProcessId}")
    event = DEBUG_EVENT()
    dump_written = False
    noisy_first_chance_counts: dict[int, int] = {}
    try:
        while True:
            if not kernel32.WaitForDebugEvent(ctypes.byref(event), 300000):
                raise win32_error()
            continue_status = DBG_CONTINUE
            if event.dwDebugEventCode == EXCEPTION_DEBUG_EVENT:
                record = event.u.Exception.ExceptionRecord
                code = record.ExceptionCode
                first = bool(event.u.Exception.dwFirstChance)
                params = [
                    int(record.ExceptionInformation[i])
                    for i in range(min(int(record.NumberParameters), 15))
                ]
                param_text = " ".join(f"{value:016X}" for value in params)
                should_log = True
                if first and code == ACCESS_VIOLATION:
                    noisy_first_chance_counts[code] = noisy_first_chance_counts.get(code, 0) + 1
                    should_log = noisy_first_chance_counts[code] <= 5
                if should_log:
                    print(
                        f"exception code=0x{code:08X} first_chance={first} "
                        f"thread={event.dwThreadId} address=0x{int(record.ExceptionAddress):016X} "
                        f"params=[{param_text}]",
                        flush=True,
                    )
                if code == CPP_EXCEPTION:
                    cxx_info = decode_msvc_cxx_exception(process_info.hProcess, params)
                    if cxx_info:
                        print(cxx_info, flush=True)
                if code != EXCEPTION_BREAKPOINT:
                    continue_status = DBG_EXCEPTION_NOT_HANDLED
                if code != EXCEPTION_BREAKPOINT and not first and not dump_written:
                    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
                    dump_path = dump_dir / f"xenia_canary_{stamp}_{process_info.dwProcessId}.dmp"
                    stack_path = dump_dir / f"xenia_canary_{stamp}_{process_info.dwProcessId}_stack.txt"
                    try:
                        write_stack_trace(process_info.hProcess, event.dwThreadId, stack_path)
                        print(f"Wrote stack: {stack_path}", flush=True)
                    except Exception as exc:
                        print(f"Stack capture failed: {exc}", flush=True)
                    write_dump(process_info.hProcess, process_info.dwProcessId, dump_path)
                    dump_written = True
                    print(f"Wrote dump: {dump_path}", flush=True)
            elif event.dwDebugEventCode == EXIT_PROCESS_DEBUG_EVENT:
                print("Xenia exited")
                break
            kernel32.ContinueDebugEvent(event.dwProcessId, event.dwThreadId, continue_status)
    finally:
        kernel32.CloseHandle(process_info.hThread)
        kernel32.CloseHandle(process_info.hProcess)
    return 0 if dump_written else 2


if __name__ == "__main__":
    raise SystemExit(main())
