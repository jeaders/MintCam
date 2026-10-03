# MintCam

Applicazione desktop leggera per Linux Mint per usare la webcam come videocamera live, fotocamera e registratore video semplice per creator e videochiamate.

## Funzioni disponibili

- Anteprima webcam live con OpenCV
- Scatto foto con salvataggio automatico in `~/MintCam/photos`
- Registrazione video senza audio in `~/MintCam/recordings`
- Selezione della webcam con nome dispositivo
- Risoluzioni: 640x480, 1280x720, 1920x1080 (se supportata)
- FPS: 1-120
- Filtri: Normale, Bianco e nero, Sepia, Negativo, Contrasto elevato
- Specchio live
- Griglia composizione
- Formati: 16:9, 4:3, 9:16
- Timer foto: 3, 5, 10 secondi
- Burst foto: 3, 5, 10 scatti
- Regolazioni: luminosità, contrasto, saturazione
- Focus assist con indicatore visivo
- QR/Barcode scanner live
- Face auto-framing
- Time-lapse con assemblaggio MP4 automatico
- MintCast virtual webcam
- Pausa anteprima
- Limite durata registrazione
- Qualità foto regolabile
- Apertura cartella foto/registrazioni
- Avvio automatico con il sistema
- Tema scuro moderno
- Icona personalizzata

## Requisiti

- Linux Mint 21+ (o compatibile)
- Python 3.10 o superiore
- `python3-venv`, `python3-pip`
- `v4l-utils` (per verificare le webcam)
- `ffmpeg` (consigliato per il codec video)
- `libxcb-cursor0` (richiesto da Qt per il plugin xcb)
- `pyzbar`, `Pillow` (per QR/Barcode scanner)

## Installazione

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip python3-opencv v4l-utils ffmpeg libxcb-cursor0

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

chmod +x run.sh
./run.sh
```

## Installazione come applicazione desktop

```bash
chmod +x install-local.sh
./install-local.sh
```

Cerca **MintCam** nel menu applicazioni di Linux Mint o avvia da terminale con `mintcam`.

Per disinstallare:
```bash
rm -f ~/.local/share/applications/mintcam.desktop
rm -rf ~/.local/share/mintcam
rm -f ~/.local/bin/mintcam
```

## Pacchetto .deb

```bash
./build-deb.sh
sudo dpkg -i dist/mintcam_0.1.0_all.deb
```

## Verifica della webcam

```bash
v4l2-ctl --list-devices
v4l2-ctl --list-formats-ext -d /dev/video0
```

## Avvio automatico all'accensione

1. Apri il menu → Preferenze → Applicazioni d'avvio
2. Clicca "Aggiungi"
3. Nome: `MintCam`
4. Comando: `mintcam`
5. Salva

## MintCast virtual webcam (opzionale)

```bash
sudo apt install v4l2loopback-dkms
sudo modprobe v4l2loopback
```

Poi attiva "MintCast virtual cam" nelle impostazioni.

## Struttura del progetto

```
mintcam/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── camera.py
│   ├── recorder.py
│   ├── storage.py
│   ├── settings.py
│   └── ui/
│       ├── __init__.py
│       ├── main_window.py
│       └── styles.py
├── assets/
├── recordings/
├── photos/
├── logs/
├── tests/
├── requirements.txt
├── README.md
├── run.sh
├── mintcam
├── install-local.sh
├── build-deb.sh
├── packaging/
│   ├── mintcam-launcher
│   └── mintcam.desktop
├── mintcam.appdata.xml
└── .gitignore
```

## Problemi comuni

- **Errore all'avvio: "Could not load the Qt platform plugin xcb"**: installa `libxcb-cursor0` (`sudo apt install libxcb-cursor0`) e riavvia.
- **Webcam non trovata**: verifica che non sia usata da un altro programma (es. Zoom, Cheese).
- **Permesso negato**: controlla di appartenere al gruppo `video` (`sudo usermod -aG video $USER`) e riavvia la sessione.
- **Risoluzione non supportata**: prova 640x480 o 1280x720.
- **Registrazione vuota o corrotta**: assicurati che `ffmpeg` sia installato.
- **QR non funziona**: installa `pyzbar` e `Pillow` (`pip install pyzbar Pillow`).

## Limitazioni

- La registrazione video è **senza audio** nel prototipo attuale.
- MintCast richiede `v4l2loopback` per funzionare.
- Alcune funzionalità avanzate sono in fase di pianificazione.

## Audio previsto nella versione futura

Nelle versioni future verrà aggiunta la registrazione audio tramite:
- GStreamer con pipeline `v4l2src` + `alsasrc`
- oppure FFmpeg come processo esterno

Per il prototipo attuale è stato scelto di non registrare l'audio per mantenere il codice leggero e dipendenza-minimale.

## Roadmap futura

### v0.2.0
- Registrazione audio con GStreamer
- Selezione microfono
- Contatore FPS reale con media mobile
- Overlay data/ora su preview e registrazione
- Zoom digitale con slider

### v0.3.0
- Galleria miniature integrata
- Slow-motion e time-lapse avanzato
- Impostazioni avanzate codec
- Supporto multi-camera contemporaneamente
- Effetti transizione video (fade, dissolve)
- Streaming RTMP diretto (Twitch/Youtube)
- Remote control via HTTP/WebSocket

### v1.0.0 (store)
- Installer `.deb` pulito per Linux Mint store
- AppStream metadata completa
- Icone HD e tema personalizzabile
- Traduzione EN/IT
- Test completati
- Documentazione utente

## Contribuire

1. Fork del progetto
2. Crea un branch: `git checkout -b feature/nuova-funzione`
3. Commit: `git commit -m "Aggiunge ..."`
4. Push: `git push origin feature/nuova-funzione`
5. Apri una Pull Request

## Licenza

Prototipo sperimentale senza licenza definita.
