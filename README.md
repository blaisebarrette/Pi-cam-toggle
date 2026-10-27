# OctoPrint-CamToggle

A navbar button in OctoPrint to **stop / start the Raspberry Pi camera service**
(camera-streamer, webcamd, crowsnest…). Camera off = CPU, memory, camera and network bandwidth freed.

## Features
- Automatic detection of the camera service (camera-streamer, webcamd, crowsnest).
- Camera icon in the navbar (green = running, grey = stopped), one click to toggle.
- State synced across all open browsers.
- Webcam stream reloaded automatically after a toggle.
- Option: keep the state across reboots (re-applied when OctoPrint starts).
- Option: turn the camera on when a print starts / off when it ends.
- Dedicated permission `CamToggle → Contrôle caméra` (admins by default).

## Installation
*Settings → Plugin Manager → Get More → …from URL*:
```
https://github.com/blaisebarrette/Pi-cam-toggle/archive/main.zip
```

### Permissions
**On OctoPi: nothing to do.** OctoPi already allows OctoPrint to run `sudo service …` without a password
(`/etc/sudoers.d/octoprint-service`), and the plugin uses it to stop/start the camera.

If that file has wrong permissions, sudo ignores it: `sudo chmod 440 /etc/sudoers.d/octoprint-service`.

**Elsewhere** (manual OctoPrint install), add a rule once, over SSH:
```bash
SVC=webcamd   # ← camera service name
U=$(ps -o user= -p $(pgrep -f "octoprint serve" | head -1))
echo "$U ALL=(root) NOPASSWD: /usr/bin/systemctl start $SVC, /usr/bin/systemctl stop $SVC" | sudo tee /etc/sudoers.d/octoprint-camtoggle
sudo chmod 440 /etc/sudoers.d/octoprint-camtoggle && sudo visudo -c
```
If access is denied, the plugin's error message gives the exact command to copy.

| Setup | Service |
|---|---|
| OctoPi ≥ 1.0, Pi Camera | `camera-streamer-libcamera` |
| OctoPi ≥ 1.0, USB | `camera-streamer-usb-default` |
| OctoPi < 1.0 | `webcamd` |
| Crowsnest | `crowsnest` |

The plugin detects the service on its own (hover the icon to see it).
To force a service, set it in *Settings → CamToggle*.

## Tested
| Version | System | Service | Result |
|---|---|---|---|
| 0.3.0 | OctoPi | `webcamd` | ✅ Toggles on/off **with no extra sudoers rule** (verified after `sudo -k`) |

### What is freed / what is not
- ✅ Streaming process stopped (`mjpg_streamer`, camera-streamer…): CPU and RAM freed.
- ✅ `/dev/video0` released, no more capture.
- ✅ No more video traffic on the network.
- ❌ GPU memory (`gpu_mem`) stays reserved and the camera driver stays loaded (set at boot).
- ⚠️ Timelapses fail while the camera is off: use the "turn on when a print starts" option.

To measure (camera on, then off):
```bash
ps -C mjpg_streamer -o %cpu,rss,cmd
sudo fuser -v /dev/video0
```

## Troubleshooting
- **"sudo: a password is required"**: make sure you are configuring **the Pi that runs OctoPrint**
  (the error message shows `host=` and `user=`).
- **Testing a sudo rule**: always run `sudo -k` before `sudo -n …`. On OctoPi (`timestamp_type=global`),
  a recently typed password is reused for 15 min, even by OctoPrint, which skews the test.
- **Grey icon while video is streaming**: wrong service. Clear the "Service(s)" field for
  auto-detection, or enter the correct name.
- **Camera no longer starts at boot**: a version < 0.3.0 may have run `systemctl disable`.
  Fix it once with `sudo systemctl enable webcamd` (or your service).
- **`visudo -c` reports "bad permissions"**: `sudo chmod 440 /etc/sudoers.d/<file>`, otherwise sudo ignores it.

## API
```
GET  /api/plugin/camtoggle                → {"active": true, "services": [...]}
POST /api/plugin/camtoggle {"command": "on" | "off" | "toggle"}
```
