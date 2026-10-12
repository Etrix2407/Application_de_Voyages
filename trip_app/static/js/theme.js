// Mode clair ou sombre. Sans choix enregistré, la page suit le réglage de l'appareil (feuille de style).
// Chargé dans <head> sans defer : le mode choisi est appliqué avant l'affichage, sans éclair blanc.
(function () {
    var STORAGE_KEY = "theme";
    var root = document.documentElement;

    function readChoice() {
        try {
            return localStorage.getItem(STORAGE_KEY);
        } catch (error) {
            return null; // stockage bloqué (navigation privée, cookies refusés)
        }
    }

    function saveChoice(theme) {
        try {
            localStorage.setItem(STORAGE_KEY, theme);
        } catch (error) {
            // Le choix vaut alors pour cette page seulement.
        }
    }

    function isDark() {
        var theme = root.getAttribute("data-theme");
        if (theme) {
            return theme === "dark";
        }
        return window.matchMedia("(prefers-color-scheme: dark)").matches;
    }

    var saved = readChoice();
    if (saved === "dark" || saved === "light") {
        root.setAttribute("data-theme", saved);
    }

    // Le bouton annonce le mode vers lequel il bascule (son libellé change à chaque clic).
    function updateButton(button) {
        var next = isDark() ? "light" : "dark";
        button.setAttribute("data-next", next);
        button.textContent = next === "dark" ? "Mode sombre" : "Mode clair";
    }

    document.addEventListener("DOMContentLoaded", function () {
        var button = document.getElementById("theme-toggle");
        if (!button) {
            return;
        }
        updateButton(button);
        button.hidden = false;
        button.addEventListener("click", function () {
            var theme = button.getAttribute("data-next");
            root.setAttribute("data-theme", theme);
            saveChoice(theme);
            updateButton(button);
        });
    });
})();
