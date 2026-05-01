# Code RED Xenia RDR Netplay - Pass F Session Layout Bridge

## Goal

Move the RDR System Link bridge from the temporary compact search snapshot to the Xbox 360 session structures used by the netplay branch:

- `XSESSION_INFO = 0x3C`
- `XSESSION_SEARCHRESULT_HEADER = 0x08`
- `XSESSION_SEARCHRESULT = 0x5C`
- `XSESSION_LOCAL_DETAILS = 0x80`

This pass keeps writes guarded. If the XGI message does not expose a safe guest pointer and buffer size, the bridge logs the discovered sessions and does not write memory.

## Main changes

### Search result writing

`FillCodeRedSessionSearchResults` now writes:

```text
XSESSION_SEARCHRESULT_HEADER
+0x00 search_results_count
+0x04 search_results_ptr

XSESSION_SEARCHRESULT[0..n]
+0x00 XSESSION_INFO
+0x3C open_public_slots
+0x40 open_private_slots
+0x44 filled_public_slots
+0x48 filled_private_slots
+0x4C properties_count
+0x50 contexts_count
+0x54 properties_ptr
+0x58 contexts_ptr
```

### XSESSION_INFO writing

The embedded session info writes:

```text
XNKID sessionID
XNADDR hostAddress
XNKEY keyExchangeKey
```

The key is deterministic for now. It is intentionally stable per session until the XNet key registration path is ported.

### XGI buffer parsing

`xgi_app.cc` now prefers exact XGI message layouts before using the fallback scanner:

```text
XGI_SESSION_SEARCH
XGI_SESSION_SEARCH_BYIDS
XGI_SESSION_SEARCH_WEIGHTED
XGI_SESSION_DETAILS
```

This should make RDR logs much more useful because we can tell whether the game is passing the normal `XSessionSearch`, by-ID, weighted, or details path.

## Logs to watch

```text
CodeRED Netplay: XSessionSearch source=XGI_SESSION_SEARCH filled=...
CodeRED Netplay: XSessionSearchByIDs/Weighted source=XGI_SESSION_SEARCH_WEIGHTED filled=...
CodeRED Netplay: XSessionGetDetails source=XGI_SESSION_DETAILS filled=...
```

If the result is not filled, the log will include the expected layout string instead of writing to an unsafe pointer.

## Still held for the next pass

- Full XNetRegisterKey / XNetUnregisterKey behavior.
- Real generated XNKEY lifecycle.
- SPA-backed title contexts/properties in search results.
- More exact RDR-specific game mode/type context filling.
