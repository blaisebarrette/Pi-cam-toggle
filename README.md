# OctoPrint-CamToggle

Bouton dans la barre de navigation d'OctoPrint pour **arrêter / démarrer le service caméra** du Raspberry Pi
(camera-streamer, webcamd, crowsnest…). Caméra arrêtée = CPU/GPU, mémoire et bande passante libérés.

## Fonctions
- Détection automatique du service caméra (camera-streamer, webcamd, crowsnest).
- Icône caméra dans la navbar (verte = active, grise = arrêtée), un clic pour basculer.
- État synchronisé entre tous les navigateurs ouverts.
- Option : conserver l'état après redémarrage (`systemctl enable/disable`).
- Option : activer au début d'une impression / désactiver à la fin.
- Permission dédiée `CamToggle → Contrôle caméra` (admins par défaut).

## Installation
*Paramètres → Plugin Manager → Get More → …from URL* :
```
https://github.com/blaisebarrette/Pi-cam-toggle/archive/main.zip
```

### Autoriser systemctl sans mot de passe (obligatoire)
Sur le Pi, en SSH :
```bash
systemctl list-units --type=service | grep -Ei 'camera|webcam|crowsnest'   # nom du service
SVC=webcamd   # ← à adapter
U=$(ps -o user= -p $(pgrep -f "octoprint serve" | head -1))
echo "$U ALL=(root) NOPASSWD: /usr/bin/systemctl start $SVC, /usr/bin/systemctl stop $SVC, /usr/bin/systemctl enable $SVC, /usr/bin/systemctl disable $SVC" | sudo tee /etc/sudoers.d/octoprint-camtoggle
sudo chmod 440 /etc/sudoers.d/octoprint-camtoggle && sudo visudo -c
sudo -k; sudo -n /usr/bin/systemctl start $SVC && echo OK   # doit afficher OK sans mot de passe
```

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
