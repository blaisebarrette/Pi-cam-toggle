# OctoPrint-CamToggle

Bouton dans la barre de navigation d'OctoPrint pour **arrêter / démarrer le service caméra** du Raspberry Pi
(camera-streamer, webcamd, crowsnest…). Caméra arrêtée = CPU, mémoire, caméra et bande passante libérés.

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

## Testé
| Version | Système | Service | Résultat |
|---|---|---|---|
| 0.3.0 | OctoPi (octopi-piero) | `webcamd` | ✅ Bascule on/off **sans aucune règle sudoers ajoutée** (vérifié après `sudo -k`) |

### Ce qui est libéré / ce qui ne l'est pas
- ✅ Processus de streaming arrêté (`mjpg_streamer`, camera-streamer…) : CPU et RAM libérés.
- ✅ `/dev/video0` relâché, plus de capture.
- ✅ Plus aucun trafic vidéo sur le réseau.
- ❌ La mémoire GPU (`gpu_mem`) reste réservée et le pilote caméra reste chargé (fixés au boot).
- ⚠️ Les timelapses échouent si la caméra est éteinte : utilisez l'option « Activer au début d'une impression ».

Pour mesurer (caméra active puis éteinte) :
```bash
ps -C mjpg_streamer -o %cpu,rss,cmd
sudo fuser -v /dev/video0
```

## Dépannage
- **« sudo: a password is required »** : vérifiez que vous configurez bien **le Pi qui héberge OctoPrint**
  (le message d'erreur indique `host=` et `user=`).
- **Tester une règle sudo** : faites toujours `sudo -k` avant `sudo -n …`. Sur OctoPi (`timestamp_type=global`),
  un mot de passe tapé récemment est réutilisé pendant 15 min, même par OctoPrint, et fausse le test.
- **Icône grise alors que la vidéo tourne** : mauvais service. Videz le champ « Service(s) » pour
  la détection automatique, ou indiquez le bon nom.
- **La caméra ne démarre plus au boot** : une version < 0.3.0 a pu faire `systemctl disable`.
  Corrigez une fois avec `sudo systemctl enable webcamd` (ou votre service).
- **`visudo -c` signale « bad permissions »** : `sudo chmod 440 /etc/sudoers.d/<fichier>`, sinon sudo l'ignore.

## API
```
GET  /api/plugin/camtoggle                → {"active": true, "services": [...]}
POST /api/plugin/camtoggle {"command": "on" | "off" | "toggle"}
```
