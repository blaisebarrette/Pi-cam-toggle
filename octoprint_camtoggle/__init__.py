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


# Services caméra connus, par ordre de préférence pour la détection automatique.
KNOWN_SERVICES = [
    "camera-streamer-libcamera",    # OctoPi >= 1.0, Pi Camera
    "camera-streamer-usb-default",  # OctoPi >= 1.0, webcam USB
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
            # Un ou plusieurs services systemd, séparés par des virgules.
            # Vide = détection automatique parmi KNOWN_SERVICES.
            "services": "",
            # Dernier résultat de la détection automatique (interne).
            "detected": "",
            "systemctl": "/usr/bin/systemctl",
            # Garde l'état après un redémarrage (systemctl enable/disable).
            "persist": True,
            "auto_on_print_start": False,
            "auto_off_print_done": False,
        }

    def get_settings_version(self):
        return 2

    def on_settings_migrate(self, target, current):
        # La v1 avait camera-streamer-libcamera par défaut : passer en détection auto.
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
                "name": "Contrôle caméra",
                "description": "Permet d'activer/désactiver le service caméra",
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
            # Mémorisé pour retrouver le bon service quand la caméra est arrêtée et désactivée.
            self._settings.set(["detected"], ",".join(found))
            self._settings.save()
        else:
            last = [s for s in (self._settings.get(["detected"]) or "").split(",") if s in loaded]
            found = last or loaded[:1]
        self._logger.info("Service(s) caméra détecté(s) : %s", ", ".join(found) or "aucun")
        return found

    def _run(self, *args, sudo=True):
        cmd = (["sudo", "-n"] if sudo else []) + [self._settings.get(["systemctl"])] + list(args)
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            code, out = p.returncode, (p.stdout + p.stderr).strip()
        except Exception as e:  # FileNotFoundError, TimeoutExpired...
            code, out = 1, str(e)
        if sudo:
            if code != 0:
                out = "{} [cmd={} user={} host={}]".format(out, " ".join(cmd), getpass.getuser(),
                                                           socket.gethostname())
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
            if not self._services():
                errors.append("Aucun service caméra trouvé : indiquez-le dans Paramètres → CamToggle")
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
        self._logger.info("CamToggle prêt — service(s) : %s", ", ".join(self._services()) or "aucun")

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
