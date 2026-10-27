# coding=utf-8
"""OctoPrint-CamToggle: turn the Pi camera service on/off from OctoPrint.

Stopping the streaming service (camera-streamer, webcamd, crowsnest...) frees
the camera, CPU, memory and network bandwidth of the Raspberry Pi.
"""
from __future__ import absolute_import

import getpass
import socket
import subprocess
import threading
import time

import flask
import octoprint.plugin
from octoprint.access import ADMIN_GROUP
from octoprint.access.permissions import Permissions
from octoprint.events import Events


# Known camera services, in order of preference for auto-detection.
KNOWN_SERVICES = [
    "camera-streamer-libcamera",    # OctoPi >= 1.0, Pi Camera
    "camera-streamer-usb-default",  # OctoPi >= 1.0, USB webcam
    "webcamd",                      # OctoPi < 1.0
    "crowsnest",                    # Crowsnest
]


class CamTogglePlugin(
    octoprint.plugin.StartupPlugin,
    octoprint.plugin.SettingsPlugin,
    octoprint.plugin.AssetPlugin,
    octoprint.plugin.TemplatePlugin,
    octoprint.plugin.SimpleApiPlugin,
    octoprint.plugin.EventHandlerPlugin,
):
    def __init__(self):
        self._lock = threading.Lock()
        self._detected = None

    # ------------------------------------------------------------------ settings

    def get_settings_defaults(self):
        return {
            # One or more systemd services, comma-separated.
            # Empty = auto-detection among KNOWN_SERVICES.
            "services": "",
            # Last auto-detection result (internal).
            "detected": "",
            "systemctl": "/usr/bin/systemctl",
            # OctoPi already allows passwordless "sudo service" (/etc/sudoers.d/octoprint-service).
            "service_cmd": "/usr/sbin/service",
            # Re-apply the last chosen state when OctoPrint starts.
            "persist": True,
            # Last chosen state: "on", "off" or "" (internal).
            "desired": "",
            "auto_on_print_start": False,
            "auto_off_print_done": False,
        }

    def get_settings_version(self):
        return 2

    def on_settings_migrate(self, target, current):
        # v1 defaulted to camera-streamer-libcamera: switch to auto-detection.
        if (current or 1) < 2 and self._settings.get(["services"]) == "camera-streamer-libcamera":
            self._settings.set(["services"], "")

    def on_settings_save(self, data):
        octoprint.plugin.SettingsPlugin.on_settings_save(self, data)
        self._detected = None
        self._push_state()

    # ------------------------------------------------------------------ assets / templates

    def get_assets(self):
        return {"js": ["js/camtoggle.js"]}

    def get_template_configs(self):
        return [
            {"type": "navbar", "custom_bindings": True},
            {"type": "settings", "custom_bindings": False},
        ]

    # ------------------------------------------------------------------ permissions

    def get_additional_permissions(self, *args, **kwargs):
        return [
            {
                "key": "CONTROL",
                "name": "Camera control",
                "description": "Allows turning the camera service on/off",
                "roles": ["control"],
                "default_groups": [ADMIN_GROUP],
            }
        ]

    # ------------------------------------------------------------------ systemd

    def _services(self):
        raw = (self._settings.get(["services"]) or "").strip()
        if raw and raw.lower() != "auto":
            return [s.strip() for s in raw.split(",") if s.strip()]
        if self._detected is None:
            self._detected = self._detect()
        return self._detected

    def _unit_state(self, service):
        code, out = self._run("show", "-p", "LoadState", "-p", "ActiveState", "-p", "UnitFileState",
                              service, sudo=False)
        return dict(line.split("=", 1) for line in out.splitlines() if "=" in line) if code == 0 else {}

    def _detect(self):
        states = {s: self._unit_state(s) for s in KNOWN_SERVICES}
        loaded = [s for s in KNOWN_SERVICES if states[s].get("LoadState") == "loaded"]
        active = [s for s in loaded if states[s].get("ActiveState") in ("active", "activating")]
        enabled = [s for s in loaded if states[s].get("UnitFileState") == "enabled"]
        found = active or enabled
        if found:
            # Remembered to find the right service once the camera is stopped and disabled.
            self._settings.set(["detected"], ",".join(found))
            self._settings.save()
        else:
            last = [s for s in (self._settings.get(["detected"]) or "").split(",") if s in loaded]
            found = last or loaded[:1]
        self._logger.info("Detected camera service(s): %s", ", ".join(found) or "none")
        return found

    def _run(self, *args, sudo=True):
        return self._exec([self._settings.get(["systemctl"])] + list(args), sudo=sudo)

    def _exec(self, cmd, sudo=True):
        cmd = (["sudo", "-n"] if sudo else []) + cmd
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            code, out = p.returncode, (p.stdout + p.stderr).strip()
        except Exception as e:  # FileNotFoundError, TimeoutExpired...
            code, out = 1, str(e)
        if sudo:
            self._logger.info("%s -> %s %s", " ".join(cmd), code, out)
        return code, out

    def _control(self, service, action):
        """start/stop via "sudo service" (allowed by default on OctoPi), else "sudo systemctl"."""
        code, out = self._exec([self._settings.get(["service_cmd"]), service, action])
        if code == 0:
            return None
        code, out2 = self._run(action, service)
        if code == 0:
            return None
        cmds = "{0} start {1}, {0} stop {1}".format(self._settings.get(["systemctl"]), service)
        return (
            "{} {} denied ({}). On the Pi, over SSH: "
            "echo '{} ALL=(root) NOPASSWD: {}' | sudo tee /etc/sudoers.d/octoprint-camtoggle "
            "&& sudo chmod 440 /etc/sudoers.d/octoprint-camtoggle  [host={}]"
        ).format(action, service, out2 or out, getpass.getuser(), cmds, socket.gethostname())

    def _is_active(self):
        services = self._services()
        if not services:
            return False
        # Active if at least one service is running
        return any(self._run("is-active", "--quiet", s, sudo=False)[0] == 0 for s in services)

    def _set_state(self, enable):
        with self._lock:
            errors = []
            if not self._services():
                errors.append("No camera service found: set it in Settings → CamToggle")
            action = "start" if enable else "stop"
            for service in self._services():
                err = self._control(service, action)
                if err:
                    errors.append(err)
            if not errors:
                self._settings.set(["desired"], "on" if enable else "off")
                self._settings.save()
                self._logger.info("Camera %s", "on" if enable else "off")
            for e in errors:
                self._logger.error(e)
            self._push_state(errors)
            return errors

    def _push_state(self, errors=None):
        self._plugin_manager.send_plugin_message(
            self._identifier,
            {"active": self._is_active(), "services": self._services(), "errors": errors or []},
        )

    # ------------------------------------------------------------------ API

    def get_api_commands(self):
        return {"on": [], "off": [], "toggle": []}

    def on_api_get(self, request):
        return flask.jsonify(active=self._is_active(), services=self._services())

    def on_api_command(self, command, data):
        if not Permissions.PLUGIN_CAMTOGGLE_CONTROL.can():
            return flask.make_response("Permission denied", 403)
        if command == "toggle":
            enable = not self._is_active()
        else:
            enable = command == "on"
        errors = self._set_state(enable)
        return flask.jsonify(active=self._is_active(), errors=errors)

    def is_api_protected(self):
        return True

    # ------------------------------------------------------------------ events

    def on_after_startup(self):
        self._logger.info("CamToggle ready - service(s): %s", ", ".join(self._services()) or "none")
        if self._settings.get_boolean(["persist"]) and self._settings.get(["desired"]) in ("on", "off"):
            threading.Thread(target=self._restore_state, daemon=True).start()

    def _restore_state(self):
        # The camera service may start after OctoPrint: check twice.
        enable = self._settings.get(["desired"]) == "on"
        for delay in (10, 60):
            time.sleep(delay)
            if self._is_active() != enable:
                self._logger.info("Re-applying remembered state: %s", "on" if enable else "off")
                self._set_state(enable)

    def on_event(self, event, payload):
        if event == Events.PRINT_STARTED and self._settings.get_boolean(["auto_on_print_start"]):
            threading.Thread(target=self._set_state, args=(True,), daemon=True).start()
        elif event in (Events.PRINT_DONE, Events.PRINT_FAILED, Events.PRINT_CANCELLED) and \
                self._settings.get_boolean(["auto_off_print_done"]):
            threading.Thread(target=self._set_state, args=(False,), daemon=True).start()

    # ------------------------------------------------------------------ software update

    def get_update_information(self):
        # Checks GitHub releases (tags vX.Y.Z) and installs the tagged archive with pip.
        return {
            "camtoggle": {
                "displayName": "CamToggle",
                "displayVersion": self._plugin_version,
                "type": "github_release",
                "user": "blaisebarrette",
                "repo": "Pi-cam-toggle",
                "current": self._plugin_version,
                "pip": "https://github.com/blaisebarrette/Pi-cam-toggle/archive/{target_version}.zip",
            }
        }


__plugin_name__ = "CamToggle"
__plugin_pythoncompat__ = ">=3.7,<4"


def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = CamTogglePlugin()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.access.permissions": __plugin_implementation__.get_additional_permissions,
        "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information,
    }
