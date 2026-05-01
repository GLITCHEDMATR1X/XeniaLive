# CodeRED RDR Multiplayer Crash Guard v5

This is a runtime triage kit for the current RDR multiplayer entry crash.

## Why this pass exists

The uploaded stack traces do not point at the CodeRED XSession/XNet bridge directly. They repeatedly land in Xenia's x64 JIT/compiler path (`x64_emitter.cc`, `register_allocation_pass.cc`, `ppc_translator.cc`, and `processor.cc`). The current config also had debug-break and unimplemented-instruction break behavior enabled, which is too aggressive for a multiplayer compatibility test.

## Test order

1. Private Host / Disc 2 / SAFE CPU
2. Private Host / Disc 2 / BARE
3. Offline / Disc 2 / SAFE CPU
4. Collect small logs

If Offline crashes the same way, the issue is probably not the private host or session bridge. If Private Host crashes but Offline does not, the next pass should focus on XAM/XNet multiplayer entry calls.
