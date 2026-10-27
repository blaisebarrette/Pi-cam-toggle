# OctoPrint-CamToggle

Bouton dans la barre de navigation d'OctoPrint pour **arrêter / démarrer le service caméra** du Raspberry Pi
(camera-streamer, webcamd, crowsnest…). Caméra arrêtée = CPU/GPU, mémoire et bande passante libérés.

## Fonctions
- Détection automatique du service caméra (camera-streamer, webcamd, crowsnest).
- Icône caméra dans la navbar (verte = active, grise = arrêtée), un clic pour basculer.
- État synchronisé entre tous les navigateurs ouverts.
- Option : conserver l'état après redémarrage (réappliqué au démarrage d'OctoPrint).
- Option : activer au début d'une impression / désactiver à la fin.
- Permission dédiée `CamToggle → Contrôle caméra` (admins par défaut).

## Installation
*Paramètres → Plugin Manager → Get More → …from URL* :
```
https://github.com/blaisebarrette/Pi-cam-toggle/archive/main.zip
```

### Permissions
**Sur OctoPi : rien à faire.** OctoPi autorise déjà OctoPrint à lancer `sudo service …` sans mot de passe
(`/etc/sudoers.d/octoprint-service`), et le plugin s'en sert pour arrêter/démarrer la caméra.

Si ce fichier a de mauvaises permissions, sudo l'ignore : `sudo chmod 440 /etc/sudoers.d/octoprint-service`.

**Ailleurs** (installation manuelle d'OctoPrint), ajoutez une règle une fois, en SSH :
```bash
SVC=webcamd   # ← nom du service caméra
U=$(ps -o user= -p $(pgrep -f "octoprint serve" | head -1))
echo "$U ALL=(root) NOPASSWD: /usr/bin/systemctl start $SVC, /usr/bin/systemctl stop $SVC" | sudo tee /etc/sudoers.d/octoprint-camtoggle
sudo chmod 440 /etc/sudoers.d/octoprint-camtoggle && sudo visudo -c
```
En cas de refus, le message d'erreur du plugin donne la commande exacte à copier.

| Installation | Service |
|---|---|
| OctoPi ≥ 1.0, Pi Camera | `camera-streamer-libcamera` |
| OctoPi ≥ 1.0, USB | `camera-streamer-usb-default` |
| OctoPi < 1.0 | `webcamd` |
| Crowsnest | `crowsnest` |

Le plugin détecte le service tout seul (survolez l'icône pour le voir).
Pour forcer un service, renseignez-le dans *Paramètres → CamToggle*.

## API
```
GET  /api/plugin/camtoggle                → {"active": true, "services": [...]}
POST /api/plugin/camtoggle {"command": "on" | "off" | "toggle"}
```
