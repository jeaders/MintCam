# MintCam – Analisi interna e componenti avanzati

Documentazione riservata allo sviluppo. Non distribuire pubblicamente.

## Indice

1. Architettura dettagliata
2. Flusso dati frame
3. Componenti avanzati previsti
4. Decisioni tecniche e trade-off
5. Problematiche note
6. TODO di sviluppo
7. Testing avanzato
8. Performance e profiling
9. Sicurezza e privacy

---

## 1. Architettura dettagliata

### Moduli

| Modulo | Responsabilità |
|---|---|
| `app/camera.py` | Acquisizione webcam in QThread, gestione dispositivo, risoluzione, FPS |
| `app/recorder.py` | `cv2.VideoWriter`, selezione codec, durata, fallback formato |
| `app/storage.py` | Percorsi in `~/MintCam`, creazione cartelle, salvataggio foto/video, `xdg-open` |
| `app/settings.py` | `settings.json` in `~/MintCam/`, persistenza preferenze utente |
| `app/ui/main_window.py` | Finestra principale, controlli, filtri, overlay, timer |
| `app/ui/styles.py` | Tema scuro QSS, palette Qt |
| `app/main.py` | Entry point, logging |

### Gerarchia Qt

```
QApplication
└── MainWindow (QMainWindow)
    ├── QGridLayout
    │   ├── Header (QFrame)
    │   ├── Preview (QLabel) + Overlays
    │   ├── Controls (QVBoxLayout + QGroupBox)
    │   └── Footer (QHBoxLayout + QPushButton)
    └── QStatusBar
```

---

## 2. Flusso dati frame

1. `CameraWorker` (QThread) legge frame da OpenCV.
2. Frame BGR originale conservato in `_last_frame` e emesso via segnale `frame_ready`.
3. `MainWindow._on_frame_ready()` salva il frame in `_current_frame`.
4. `QTimer` scatta a intervallo di aggiornamento UI e chiama `_update_preview()`.
5. `_update_preview()` copia il frame, applica filtro, regolazioni e formato.
6. Frame elaborato salvato in `_processed_frame` (BGR).
7. Conversione BGR → RGB → `QImage` → `QPixmap` → `QLabel`.
8. Per foto: usa `_processed_frame`.
9. Per registrazione: usa `_processed_frame`.

### Perché QTimer e non solo segnale `frame_ready`

Il segnale `frame_ready` viene emesso alla massima velocità consentita dalla webcam. Se la UI si aggiornasse a ogni frame, l'interfaccia si bloccherebbe. Il QTimer limita l'aggiornamento a un valore controllabile (default 30 FPS UI).

---

## 3. Componenti avanzati previsti

### 3.1 Registrazione audio

**Opzione A: GStreamer**
```python
pipeline = (
    "v4l2src device=/dev/video0 ! videoconvert ! queue ! "
    "tee name=t ! queue ! videoconvert ! x264enc ! mp4mux name=mux ! filesink location=output.mp4 "
    "alsasrc device=hw:0 ! audioconvert ! queue ! t. ! mux."
)
```

**Opzione B: FFmpeg subprocess**
- Avvia `ffmpeg` come processo separato con pipe stdin per il video e pipe per l'audio.
- Sincronizzazione tramite PTS (presentation timestamp).

**Opzione C: PyAV**
- Binding Python per FFmpeg, più stabile di `subprocess`.
- Richiede `av` (`pip install av`).

### 3.2 Contatore FPS reale

- Misurare `time.perf_counter()` tra frame letti.
- Media mobile sugli ultimi N frame.
- Visualizzare nel header.

### 3.3 Overlay testo su preview

- Data/ora, nome filtro, risoluzione.
- Usare `cv2.putText()` prima di `_apply_format()`.

### 3.4 Salvataggio in tempo reale

- Scrivere frame su disco mentre la preview continua.
- Già supportato da `Recorder.write()`.

### 3.5 Zoom digitale

- Ritaglio centrale del frame prima di `_apply_format()`.
- Aggiungere slider con valore da 1.0 a 2.0.

### 3.6 Anteprima istantanea dopo scatto

- Mostrare il frame catturato in una sovrapposizione per 1 secondo.
- Effetto “flash” bianco sul preview.

### 3.7 Hotkey

- `Space` → scatta foto
- `R` → avvia/ferma registrazione
- `F` → cambia filtro
- `Esc` → chiudi app

### 3.8 Miniature galleria

- Barra laterale o inferiore con ultime N foto/video.
- Anteprima cliccabile per aprire nel viewer di sistema.

### 3.9 Slow-motion / Time-lapse

- Time-lapse: salvare 1 frame ogni N secondi, riprodurre a 30 FPS.
- Slow-motion: registrare a 60+ FPS, riprodurre a 30 FPS.

### 3.10 Impostazioni avanzate

- Compressione JPEG (0-100)
- Codec video preferito
- Percorso salvataggio personalizzato
- Auto-avvio registrazione all'apertura
- Sovrapposizione data/ora sul video

---

## 4. Decisioni tecniche e trade-off

### 4.1 QThread vs QTimer per acquisizione

Scelta: **QThread**.
Motivo: separa l'I/O bloccante di OpenCV dal thread GUI. QTimer avrebbe richiesto di leggere la webcam nel thread GUI, rischiando blocchi se `cap.read()` si blocca.

### 4.2 Codec video

Scelta: `mp4v` → `XVID` → `MJPG` (AVI).
Motivo: MP4 è preferibile, ma non tutti i backend OpenCV supportano `mp4v` su V4L2. MJPG è quasi sempre supportato.

Trade-off: senza FFmpeg attivo, il contenitore MP4 potrebbe non essere scrivibile. Con `mp4v` su `cv2.VideoWriter`, OpenCV scrive un MP4 solo se il backend include FFmpeg.

### 4.3 Percorsi di salvataggio

Scelta: `~/MintCam/` invece della directory corrente.
Motivo: la directory corrente dipende da dove viene lanciato lo script. `~/MintCam` è stabile e scrivibile.

### 4.4 xdg-open per aprire cartelle

Scelta: `subprocess.run(["xdg-open", ...])`.
Motivo: standard freedesktop, funziona su Cinnamon, MATE, Xfce, GNOME.
Alternativa: `QDesktopServices.openUrl()` da PySide6. È più portabile ma meno flessibile su percorsi locali.

### 4.5 Qt platform plugin

Problema: OpenCV nel venv include plugin Qt incompatibili con PySide6.
Soluzione: `QT_QPA_PLATFORM_PLUGIN_PATH` forzato ai plugin di PySide6 in `run.sh` e `install-local.sh`.

### 4.6 QImage.copy()

Motivo: `QImage(rgb.data, ...)` non copia i dati. Se il numpy array viene liberato, QImage punta a memoria invalida.
Soluzione: `.copy()` crea una copia profonda, leggermente più lenta ma sicura.

### 4.7 .desktop icon

Scelta: `camera-photo` (icona di sistema standard).
Motivo: nessuna dipendenza esterna. Per un'icona personalizzata, servirebbe un file `.png` in `~/.local/share/icons/`.

---

## 5. Problematiche note

### 5.1 Memory leak frame

Il frame numpy emesso dal QThread viene copiato in `_current_frame` e poi di nuovo in `_processed_frame`. Se l'utente cambia filtro/resoluzione velocemente, si accumulano array temporanei. Soluzione: riutilizzare buffer preallocati (non implementato per semplicità).

### 5.2 Risoluzioni non standard

Se la webcam restituisce frame con risoluzione diversa da quella richiesta, `_apply_format()` ritaglia. Ma le dimensioni del `VideoWriter` potrebbero non corrispondere se OpenCV negozia una risoluzione diversa. Soluzione: leggere `cap.get(cv2.CAP_PROP_FRAME_WIDTH/HEIGHT)` dopo l'apertura e usare quelle dimensioni.

### 5.3 Fotogrammi persi

Se il QThread produce frame più velocemente di quanto la UI li consumi, i segnali vengono accodati. In caso di backlog, l'UI mostra frame vecchi. Soluzione: nel slot `_on_frame_ready`, tenere solo l'ultimo frame e scartare i segnali vecchi usando un flag o confrontando timestamp.

### 5.4 Webcam disconnessa durante l'uso

OpenCV restituisce `False` da `read()` e poi solleva errori. Attualmente il worker continua a riprovare. Comportamento desiderato: mostrare un messaggio e fermare l'app o permettere di cambiare dispositivo.

### 5.5 Permessi V4L2

Se l'utente non è nel gruppo `video`, OpenCV fallisce in modo non chiaro. Aggiungere un controllo esplicito all'avvio:
```python
import os, grp
if os.access('/dev/video0', os.R_OK) is False:
    # mostra messaggio
```

---

## 6. TODO di sviluppo

- [ ] Contatore FPS reale con media mobile
- [ ] Overlay data/ora su preview e registrazione
- [ ] Zoom digitale
- [ ] Hotkey configurabili
- [ ] Galleria miniature
- [ ] Time-lapse / slow-motion
- [ ] Impostazioni avanzate (codec, compressione, percorso)
- [ ] Registrazione audio (GStreamer / PyAV / FFmpeg)
- [ ] Controllo ganzo luminosità automatico
- [ ] Supporto multi-camera contemporaneo
- [ ] Registrazione schermo intero
- [ ] Scatto multiplo / burst
- [ ] Effetti transizione
- [ ] Esportazione diretta MP4 con FFmpeg post-processing
- [ ] Installer `.deb` per Linux Mint
- [ ] Flatpak / AppImage per distribuzione
- [ ] Traduzione interfaccia in inglese
- [ ] Unit test per UI (pytest-qt)

---

## 7. Testing avanzato

### 7.1 Test attuali

- `tests/test_storage.py`: nomi file, salvataggio foto, gestione errori
- `tests/test_camera.py`: risoluzioni, apertura webcam, emissione frame (mock)
- `tests/test_recorder.py`: avvio/arresto, codec fallback
- `tests/test_settings.py`: default, caricamento, salvataggio

### 7.2 Test consigliati

- **Integration test**: mock completo di `cv2.VideoCapture` e verificare che `MainWindow` aggiorni la preview.
- **Test UI**: `pytest-qt` per verificare che i pulsanti siano abilitati/disabilitati correttamente durante la registrazione.
- **Test performance**: profilare l'uso di CPU con `cProfile` durante l'acquisizione a 30 FPS.
- **Test memory**: `objgraph` o `tracemalloc` per verificare che i frame numpy vengano rilasciati.

---

## 8. Performance e profiling

### 8.1 Benchmark attesi (CPU)

| Risoluzione | FPS | CPU stimata |
|---|---|---|
| 640x480 | 30 | 10-20% |
| 1280x720 | 30 | 20-40% |
| 1920x1080 | 30 | 40-70% |

Dipende dal processore e dalla presenza di accelerazione hardware.

### 8.2 Ottimizzazioni possibili

- Usare `cv2.CAP_PROP_CONVERT_RGB = False` se il formato nativo è RGB (risparmia conversione).
- Evitare `frame.copy()` se possibile (attualmente necessario per `QImage.copy()`).
- Ridimensionare il frame solo se la risoluzione di preview è diversa da quella nativa.
- Usare `QImage.Format_BGR888` se disponibile (evita conversione BGR→RGB), ma non tutti i backend Qt lo supportano.

---

## 9. Sicurezza e privacy

### 9.1 Dati personali

L'app non raccoglie dati personali. Tutti i file (foto, video, log) rimangono in `~/MintCam`.

### 9.2 Permessi

- Webcam: richiede accesso a `/dev/video*` (gruppo `video`).
- Microfono futuro: richiederà accesso a `/dev/snd/*`.
- File system: richiede scrittura in `~/MintCam`.

### 9.3 Log

I log in `~/MintCam/logs/mintcam.log` potrebbero contenere percorsi di file e timestamp. Non contengono dati biometrici o personali, ma se l'app viene usata in contesti sensibili, valutare cifratura o eliminazione periodica.

### 9.4 Dipendenze

- `PySide6`: licenza LGPL v3
- `opencv-python`: licenza Apache 2.0
- `numpy`: licenza BSD

Nessuna dipendenza a pagamento o servizio cloud.

---

*Documento generato il 2026-10-02 – Versione prototipo 0.1*
