# Code RED Xenia Canary RDR Netplay First Pass

## Goal

Prepare official Xenia Canary for a Red Dead Redemption System Link / Free Roam test without blindly merging the large netplay fork.

## Strategy

This pass follows the selective-port direction:

1. Keep official Canary as the base.
2. Add compile-safe netplay configuration and a lightweight `XLiveAPI` scaffold.
3. Patch only the lowest-risk XNet paths needed for LAN/System Link discovery.
4. Leave the full private Live-like host, session object, UI, friends, presence, XStorage, and leaderboard APIs for later passes.

## New config values

Add or let Canary generate this section in `xenia-canary.config.toml`:

```toml
[Netplay]
network_mode = 1
netplay_api_address = "http://127.0.0.1:36000/"
selected_network_interface = ""
upnp = true
xhttp = true
net_logging = true
```

Modes:

- `0` = offline
- `1` = LAN/System Link
- `2` = private Live-like host scaffold

For a two-PC or VPN System Link test, set `selected_network_interface` to the IPv4 address of the LAN/VPN adapter that both players can reach.

Example:

```toml
selected_network_interface = "25.10.20.30"
```

## Patched XNet behavior

This pass changes `src/xenia/kernel/xam/xam_net.cc` so these exports are no longer immediate dead ends:

- `NetDll_WSARecvFrom`
- `NetDll_WSASendTo`
- `NetDll_XNetGetTitleXnAddr`
- `NetDll_XNetXnAddrToMachineId`
- `NetDll_XNetXnAddrToInAddr`
- `NetDll_XNetInAddrToXnAddr`
- `NetDll_XNetSetSystemLinkPort`
- `NetDll_XNetQosListen`
- `NetDll_XNetQosServiceLookup`
- `NetDll_XNetGetEthernetLinkStatus`

`WSARecvFrom` uses a zero-timeout readability probe first so a game polling a blocking socket does not freeze the emulator.

## RDR test target

Target route:

```text
Single Player -> Pause -> Multiplayer -> System Link -> Free Roam
```

Expected improvement from this pass:

- RDR should no longer hit the old immediate receive failure path as the only network behavior.
- RDR should see a stable XNADDR and System Link port.
- RDR should be able to call QoS listen/service lookup without immediate function failure.

This is not yet a full working RDR multiplayer host. The next pass needs the session object and private host handshake.

## Next pass

1. Add a real session object layer:
   - `XSessionCreate`
   - `XSessionSearch`
   - `XSessionJoin`
   - `XSessionLeave`
   - session-result filling
2. Wire a local/private API server for:
   - register player
   - create session
   - search session
   - join/leave session
   - QoS post/get
3. Add a small netplay settings dialog only after the non-UI path works.
