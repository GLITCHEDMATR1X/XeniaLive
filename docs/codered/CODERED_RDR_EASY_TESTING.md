# CodeRED Xenia Canary — Easy RDR Netplay Test Kit

This kit assumes:

```text
D:\Games\Red Dead Redemption\
```

Expected file:

```text
D:\Games\Red Dead Redemption\default.xex
```

Run from the patched Xenia source folder:

```bat
CodeRED_Easy_RDR_Netplay_Menu.bat
```

Fast local test:

```bat
CodeRED_OneClick_RDR_Test.bat
```

If Xenia is not built:

```bat
CodeRED_Build_Xenia_Release.bat
```

Inside RDR:

```text
Single Player > Pause > Multiplayer > System Link > Free Roam
```

For two PCs, edit the top of the BAT files:

```text
API_ADDRESS=http://HOST_PC_LAN_IP:36000/
NET_INTERFACE=THIS_PC_LAN_OR_VPN_IP
```

Send back:

```text
logs\codered_easy_rdr_netplay.log
private host console output
Xenia log around System Link / Free Roam
```
