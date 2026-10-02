# MintCam

Applicazione desktop leggera per Linux Mint per usare la webcam come videocamera live, fotocamera e registratore video semplice per creator e videochiamate.

## Funzioni disponibili (prototipo)

- Anteprima webcam live con OpenCV
- Scatto foto con salvataggio automatico in `~/MintCam/photos`
- Registrazione video senza audio (prototipo) in `~/MintCam/recordings`
- Selezione della webcam (`/dev/video0` … `/dev/video3`)
- Risoluzioni: 640x480, 1280x720, 1920x1080 (se supportata)
- FPS: 15 / 30
- Filtri: Normale, Bianco e nero, Sepia, Negativo, Contrasto elevato, Specchio orizzontale
- Formati: 16:9, 4:3, 9:16
- Timer foto: 3, 5, 10 secondi
- Regolazioni: luminosità, contrasto, saturazione
- Apertura cartella foto con il file manager di Linux
- Tema scuro moderno

## Requisiti

- Linux Mint 21+ (o compatibile)
- Python 3.10 o superiore
- `python3-venv`, `python3-pip`
- `v4l-utils` (per verificare le webcam)
- `ffmpeg` (consigliato per il codec video)
- `libxcb-cursor0` (richiesto da Qt per il plugin xcb)

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

## Verifica della webcam

```bash
v4l2-ctl --list-devices
v4l2-ctl --list-formats-ext -d /dev/video0
```

## Installazione come applicazione desktop

Dopo aver creato il virtualenv e installato le dipendenze, puoi integrare MintCam nel menu di Linux Mint:

```bash
chmod +x install-local.sh
./install-local.sh
```

Lo script copia l'app in `~/.local/share/mintcam/`, crea il launcher `mintcam` in `~/.local/bin/` e il file `.desktop` in `~/.local/share/applications/`.

Dopo l'installazione:
- cerca **MintCam** nel menu applicazioni di Linux Mint
- oppure avvia da terminale con `mintcam`

Per disinstallare:
```bash
rm -f ~/.local/share/applications/mintcam.desktop
rm -rf ~/.local/share/mintcam
rm -f ~/.local/bin/mintcam
```

## Avvio automatico all'accensione (opzionale)

Per avviare MintCam automaticamente quando accendi il computer:
1. Apri il menu → Preferenze → Applicazioni d'avvio
2. Clicca "Aggiungi"
3. Nome: `MintCam`
4. Comando: `mintcam`
5. Salva

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
└── .gitignore
```

## Problemi comuni

- **Errore all'avvio: "Could not load the Qt platform plugin xcb"**: installa `libxcb-cursor0` (`sudo apt install libxcb-cursor0`) e riavvia.
- **Webcam non trovata**: verifica che non sia usata da un altro programma (es. Zoom, Cheese).
- **Permesso negato**: controlla di appartenere al gruppo `video` (`sudo usermod -aG video $USER`) e riavvia la sessione.
- **Risoluzione non supportata**: prova 640x480 o 1280x720.
- **Registrazione vuota o corrotta**: assicurati che `ffmpeg` sia installato.

## Limitazioni

- La prima versione registra il video **senza audio**.
- Non sono supportate effetti overlay o transizioni.
- Non è previsto caricamento online o cloud.

## Audio previsto nella versione futura

Nelle versioni future verrà aggiunta la registrazione audio tramite:
- GStreamer con pipeline `v4l2src` + `alsasrc`
- oppure FFmpeg come processo esterno

Per il prototipo attuale è stato scelto di non registrare l'audio per mantenere il codice leggero e dipendenza-minimale.

## Roadmap futura

- Selezione microfono
- Registrazione audio sincronizzata
- Filtri avanzati (bilanciamento bianco, nitidezza)
- Supporto slow-motion / time-lapse
- Esportazione diretta in MP4 con FFmpeg
- Impostazioni di compressione
- Supporto a più webcam contemporaneamente
- Registrazione a schermo intero
- Scatto multiplo / burst

## Contribuire

1. Fork del progetto
2. Crea un branch: `git checkout -b feature/nuova-funzione`
3. Commit: `git commit -m "Aggiunge ..."`
4. Push: `git push origin feature/nuova-funzione`
5. Apri una Pull Request

## Licenza

Prototipo sperimentale senza licenza definita.
