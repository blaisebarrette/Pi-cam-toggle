# OctoPrint-CamToggle

Bouton dans la barre de navigation d'OctoPrint pour **arrêter / démarrer le service caméra** du Raspberry Pi
(camera-streamer, webcamd, crowsnest…). Caméra arrêtée = CPU/GPU, mémoire et bande passante libérés.

## Fonctions
- Icône caméra dans la navbar (verte = active, grise = arrêtée), un clic pour basculer.
- État synchronisé entre tous les navigateurs ouverts.
- Option : conserver l'état après redémarrage (`systemctl enable/disable`).
- Option : activer au début d'une impression / désactiver à la fin.
- Permission dédiée `CamToggle → Contrôle caméra` (admins par défaut).

## Installation
Sur le Pi :
```bash
~/oprint/bin/pip install https://github.com/blaisebarrette/Pi-cam-toggle/archive/main.zip
# ou, depuis ce dossier :
~/oprint/bin/pip install .
```
Ou via *Paramètres → Plugin Manager → Get More → … from an uploaded file* (zip du dossier).

### Autoriser systemctl sans mot de passe (obligatoire)
```bash
sudo cp extras/octoprint-camtoggle.sudoers /etc/sudoers.d/octoprint-camtoggle
sudo chmod 440 /etc/sudoers.d/octoprint-camtoggle
sudo visudo -c
```
Adaptez l'utilisateur et le nom du service dans ce fichier.

### Trouver le nom du service
```bash
systemctl list-units --type=service | grep -Ei 'camera|webcam|crowsnest'
```
| Installation | Service |
|---|---|
| OctoPi ≥ 1.0, Pi Camera | `camera-streamer-libcamera` |
| OctoPi ≥ 1.0, USB | `camera-streamer-usb-default` |
| OctoPi < 1.0 | `webcamd` |
| Crowsnest | `crowsnest` |

Renseignez-le dans *Paramètres → CamToggle* puis redémarrez OctoPrint.

## API
```
GET  /api/plugin/camtoggle                → {"active": true, "services": [...]}
POST /api/plugin/camtoggle {"command": "on" | "off" | "toggle"}
```
