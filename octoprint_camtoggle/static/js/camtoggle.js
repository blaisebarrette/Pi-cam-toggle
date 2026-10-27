$(function () {
    function CamToggleViewModel(parameters) {
        var self = this;
        self.loginState = parameters[0];
        self.access = parameters[1];

        self.active = ko.observable(false);
        self.busy = ko.observable(false);
        self.services = ko.observableArray([]);
        self.loaded = false;

        // Reload OctoPrint's webcam stream when the state changes.
        self.active.subscribe(function (active) {
            if (self.loaded) self.reloadViewer(active);
        });

        self.reloadViewer = function (active) {
            $("img[id^='webcam_image'], img.webcam_image, #webcam_container img").each(function () {
                var img = this;
                // Webcam tab hidden (empty src): OctoPrint will reload the stream itself.
                if (!/^https?:/.test(img.src || "")) return;
                var base = img.src.replace(/([?&])_camtoggle=\d+&?/, "$1").replace(/[?&]$/, "");

                var tries = 0;
                var load = function () {
                    img.src = base + (base.indexOf("?") < 0 ? "?" : "&") + "_camtoggle=" + Date.now();
                };
                // The streamer takes a moment to start: retry a few times.
                img.onerror = active ? function () {
                    if (++tries <= 5) setTimeout(load, 1000);
                } : null;
                setTimeout(load, active ? 1500 : 0);
            });
        };

        self.title = ko.pureComputed(function () {
            var svc = self.services().length ? " (" + self.services().join(", ") + ")" : " (no service found)";
            return (self.active() ? "Camera on - click to turn off" : "Camera off - click to turn on") + svc;
        });

        self.canControl = ko.pureComputed(function () {
            return self.loginState.hasPermission(self.access.permissions.PLUGIN_CAMTOGGLE_CONTROL);
        });

        self.refresh = function () {
            OctoPrint.simpleApiGet("camtoggle").done(function (r) {
                self.active(r.active);
                self.services(r.services || []);
                self.loaded = true;
            });
        };

        self.toggle = function () {
            if (self.busy()) return;
            self.busy(true);
            OctoPrint.simpleApiCommand("camtoggle", self.active() ? "off" : "on")
                .done(function (r) {
                    self.active(r.active);
                    self.showErrors(r.errors);
                })
                .fail(function (xhr) {
                    self.showErrors([xhr.responseText || "Unknown error"]);
                })
                .always(function () {
                    self.busy(false);
                });
        };

        self.showErrors = function (errors) {
            if (!errors || !errors.length) return;
            new PNotify({
                title: "CamToggle",
                text: errors.join("<br>"),
                type: "error",
                hide: false
            });
        };

        self.onPluginMessage = function (plugin, data) {
            if (plugin !== "camtoggle") return;
            self.active(data.active);
            if (data.services) self.services(data.services);
        };

        self.onUserLoggedIn = self.refresh;
        self.onStartupComplete = self.refresh;
    }

    OCTOPRINT_VIEWMODELS.push({
        construct: CamToggleViewModel,
        dependencies: ["loginStateViewModel", "accessViewModel"],
        elements: ["#navbar_plugin_camtoggle"]
    });
});
