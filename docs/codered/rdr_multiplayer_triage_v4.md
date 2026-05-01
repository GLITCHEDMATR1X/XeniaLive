# CodeRED Xenia RDR Multiplayer Triage v4

This kit is for the first crash after profile creation, when RDR enters multiplayer or LAN/System Link.

Findings from the uploaded partial build:

- The patched Xenia build exists and completed successfully.
- The private host is sometimes healthy and sometimes not responding, usually depending on whether the host console is still open.
- The visible crash stack is in Xenia's x64 JIT/emitter path, not in the CodeRED XSession/XNet C++ functions.
- LAN mode should be treated as diagnostic only for now. For RDR testing, use Private Host mode because RDR multiplayer tends to call Live-like session/profile services even when the user-facing route says System Link/Free Roam.

Try order:

1. `CodeRED_Run_RDR_PrivateHost_SafeCPU_v4.bat`
2. Enter RDR multiplayer.
3. If it still crashes, run `CodeRED_Collect_Small_Logs_v4.bat` and send the resulting zip from `logs`.
4. If SafeCPU works, try `CodeRED_Run_RDR_PrivateHost_NormalCPU_v4.bat`.

The safe CPU fallback sets:

```toml
[CPU]
break_on_debugbreak = false
break_on_unimplemented_instructions = false

[x64]
enable_host_guest_stack_synchronization = false
x64_extension_mask = 0
```

The launcher also forces a real Xenia log file:

```text
logs/xenia_codered_private_mask0.log
```

This is the most important file to send after the next crash.
