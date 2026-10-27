# coding=utf-8
"""OctoPrint-CamToggle : active/désactive le service caméra du Pi depuis OctoPrint.

Arrêter le service de streaming (camera-streamer, webcamd, crowsnest...) libère
la caméra, le CPU/GPU et la bande passante réseau du Raspberry Pi.
"""
from __future__ import absolute_import

import getpass
import socket
import subprocess
import threading

import flask
import octoprint.plugin
from octoprint.access import ADMIN_GROUP
from octoprint.access.permissions import Permissions
from octoprint.events import Events


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

    # ------------------------------------------------------------------ settings

    def get_settings_defaults(self):
        return {
            # Un ou plusieurs services systemd, séparés par des virgules.
            # OctoPi >= 1.0 : camera-streamer-libcamera (Pi Cam) / camera-streamer-usb-default
            # OctoPi < 1.0  : webcamd   |   Crowsnest : crowsnest
            "services": "camera-streamer-libcamera",
            "systemctl": "/usr/bin/systemctl",
            # Garde l'état après un redémarrage (systemctl enable/disable).
            "persist": True,
            "auto_on_print_start": False,
            "auto_off_print_done": False,
        }

    def get_settings_version(self):
        return 1

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
                "name": "Contrôle caméra",
                "description": "Permet d'activer/désactiver le service caméra",
                "roles": ["control"],
                "default_groups": [ADMIN_GROUP],
            }
        ]

    # ------------------------------------------------------------------ systemd

    def _services(self):
        raw = self._settings.get(["services"]) or ""
        return [s.strip() for s in raw.split(",") if s.strip()]

    def _run(self, *args, sudo=True):
        cmd = (["sudo", "-n"] if sudo else []) + [self._settings.get(["systemctl"])] + list(args)
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            code, out = p.returncode, (p.stdout + p.stderr).strip()
        except Exception as e:  # FileNotFoundError, TimeoutExpired...
            code, out = 1, str(e)
        if code != 0 and sudo:
            out = "{} [cmd={} user={} host={}]".format(out, " ".join(cmd), getpass.getuser(), socket.gethostname())
        self._logger.info("%s -> %s %s", " ".join(cmd), code, out)
        return code, out

    def _is_active(self):
        services = self._services()
        if not services:
            return False
        # Actif si au moins un service tourne
        return any(self._run("is-active", "--quiet", s, sudo=False)[0] == 0 for s in services)

    def _set_state(self, enable):
        with self._lock:
            errors = []
            action = "start" if enable else "stop"
            for service in self._services():
                code, out = self._run(action, service)
                if code != 0:
                    errors.append("{} {}: {}".format(action, service, out))
                if self._settings.get_boolean(["persist"]):
                    code, out = self._run("enable" if enable else "disable", service)
                    if code != 0:
                        errors.append("{} {}: {}".format("enable" if enable else "disable", service, out))
            for e in errors:
                self._logger.error(e)
            self._logger.info("Caméra %s", "activée" if enable else "désactivée")
            self._push_state(errors)
            return errors

    def _push_state(self, errors=None):
        self._plugin_manager.send_plugin_message(
            self._identifier, {"active": self._is_active(), "errors": errors or []}
        )

    # ------------------------------------------------------------------ API

    def get_api_commands(self):
        return {"on": [], "off": [], "toggle": []}

    def on_api_get(self, request):
        return flask.jsonify(active=self._is_active(), services=self._services())

    def on_api_command(self, command, data):
        if not Permissions.PLUGIN_CAMTOGGLE_CONTROL.can():
            return flask.make_response("Permission refusée", 403)
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
        self._logger.info("CamToggle prêt — services: %s", ", ".join(self._services()))

    def on_event(self, event, payload):
        if event == Events.PRINT_STARTED and self._settings.get_boolean(["auto_on_print_start"]):
            threading.Thread(target=self._set_state, args=(True,), daemon=True).start()
        elif event in (Events.PRINT_DONE, Events.PRINT_FAILED, Events.PRINT_CANCELLED) and \
                self._settings.get_boolean(["auto_off_print_done"]):
            threading.Thread(target=self._set_state, args=(False,), daemon=True).start()

    # ------------------------------------------------------------------ software update

    def get_update_information(self):
        return {}


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
