# Code RED Xenia RDR Netplay — Pass D Private Host HTTP Bridge

## Goal

Pass D adds the first usable private-host bridge on top of the Pass C session
registry. The goal is not to fake official Xbox Live. The goal is to give Red
Dead Redemption's System Link / Free Roam path a controlled session discovery
service for local or LAN testing.

## Added

- `src/xenia/kernel/util/http_client.h`
- `src/xenia/kernel/util/http_client.cc`
- `tools/codered_rdr_private_host.py`
- `tools/codered_start_rdr_private_host.bat`

## Emulator-side behavior

When `[Netplay].network_mode = 2` and `[Netplay].xhttp = true`, the experimental
XLiveAPI layer now attempts private-host calls for:

- player registration: `POST /players`
- host session publish: `POST /title/{titleId}/sessions`
- session search: `POST /title/{titleId}/sessions/search`
- local-player join relay: `POST /title/{titleId}/sessions/{sessionId}/join`
- local-player leave relay: `POST /title/{titleId}/sessions/{sessionId}/leave`
- session delete: `DELETE /title/{titleId}/sessions/{sessionId}`
- QoS upload placeholder: `POST /title/{titleId}/sessions/{sessionId}/qos`

The bridge only uses plain `http://` private-host URLs. It intentionally does not
attempt TLS, public Xbox Live, account auth, marketplace features, or official
service impersonation.

## Private host usage

From the patched Xenia source root:

```bat
tools\codered_start_rdr_private_host.bat
```

Or manually:

```bash
python tools/codered_rdr_private_host.py --host 0.0.0.0 --port 36000 --verbose
```

Set both Xenia instances to the same host:

```toml
[Netplay]
network_mode = 2
netplay_api_address = "http://HOST_PC_IP:36000/"
selected_network_interface = "THIS_PC_LAN_OR_VPN_IPV4"
xhttp = true
net_logging = true
netplay_http_timeout_ms = 1500
```

For single-machine tests, use:

```toml
netplay_api_address = "http://127.0.0.1:36000/"
selected_network_interface = "127.0.0.1"
```

For LAN/VPN tests, each PC should use its own `selected_network_interface`, but
both should point `netplay_api_address` at the same private host machine.

## RDR test path

Use the same game version/media/title update/DLC state on both clients, then try:

```text
Single Player → Pause → Multiplayer → System Link → Free Roam
```

Expected logging targets:

- `CodeRED Netplay: RegisterPlayer`
- `CodeRED Netplay: PublishSession`
- `CodeRED Netplay: SearchRemoteSessions`
- `CodeRED Netplay: JoinRemoteSession`

## Known limits after Pass D

- XSessionSearch result-buffer filling is not finished yet.
- The host service stores session discovery and QoS payloads only; it is not a
  full Live service.
- UDP peer traffic still depends on the XNet paths and the selected LAN/VPN
  interface being reachable.
- UI settings are still deliberately deferred.

## Next pass

Pass E should focus on the XSessionSearch / details result path. The game needs
the discovered private-host sessions converted into the exact result structure it
expects, not just logged and cached.
