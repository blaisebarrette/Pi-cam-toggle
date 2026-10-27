$(function () {
    function CamToggleViewModel(parameters) {
        var self = this;
        self.loginState = parameters[0];
        self.access = parameters[1];

        self.active = ko.observable(false);
        self.busy = ko.observable(false);

        self.canControl = ko.pureComputed(function () {
            return self.loginState.hasPermission(self.access.permissions.PLUGIN_CAMTOGGLE_CONTROL);
        });

        self.refresh = function () {
            OctoPrint.simpleApiGet("camtoggle").done(function (r) {
                self.active(r.active);
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
                    self.showErrors([xhr.responseText || "Erreur inconnue"]);
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
