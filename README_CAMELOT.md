# Camelot DJ Apple Music Sorter (macOS)

An intelligent DJ app for **macOS Apple Music** that organizes playlists using the **Camelot Wheel harmonic mixing system**.

Unlike DJ software such as Rekordbox or Mixed In Key (which analyze song keys but don't automatically optimize or reorder your Apple Music playlists), this app:
1. **Reads your Apple Music playlists directly on macOS** (via native AppleScript / Music.app bridge).
2. **Calculates & resolves musical keys** for every song:
   - Reads existing Camelot or standard key metadata tags (from comments, grouping, or key fields).
   - Direct audio analysis using FFT Chromagram analysis + Krumhansl-Schmuckler & Temperley pitch profiles for local audio files (MP3, AAC/M4A, AIFF, WAV, FLAC).
   - Deterministic harmonic key estimation fallback for streaming tracks without tags.
3. **Harmonically reorders the playlist** into the smoothest possible DJ set progression:
   - Minimizes harmonic clash using 2-opt TSP graph optimization with Camelot wheel rules (exact key match, relative major/minor, adjacent hour moves $\pm 1$, energy boost $+2$, and tempo progression).
   - Supports **Energy Ascent / Gradual Build** (moving up the wheel) or **Balanced Flow**.
4. **Suggests songs to remove**:
   - Detects severe harmonic bottlenecks and isolated outliers (e.g. an outlier track that clashes with the playlist's dominant tonal cluster or breaks the flow).
   - Explains *why* the song was flagged and offers musical advice.
5. **Creates a new playlist in Apple Music**:
   - Duplicates the sorted tracks into a brand-new playlist with `sorted` appended to the name (e.g., `Summer Vibes` &rarr; `Summer Vibes sorted`), leaving your original playlist untouched!

---

## Quick Start on macOS

### Prerequisites
- macOS with **Apple Music / Music.app**
- Python 3.9+ (pre-installed on macOS)
- `ffmpeg` (optional, for direct raw audio file key extraction: `brew install ffmpeg`)

### Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/Alden5/Alden5.git
cd Alden5
pip3 install -e .
```

---

## Usage

### 1. Interactive Web UI (Recommended)

Launch the modern DJ dashboard:

```bash
python3 run_sorter.py --web
```
Or simply:
```bash
python3 run_sorter.py
```
Open your browser at **`http://localhost:8765`**.

In the web interface:
1. Select any playlist from your Apple Music library.
2. Select your harmonic flow preference (*Energy Ascent* or *Balanced Flow*).
3. Click **Sort & Analyze** to inspect keys, harmonic improvement, and transition flow.
4. Review **Recommended Songs to Remove** (with 1-click exclusion).
5. Click **Apply to Apple Music (Create Playlist)**. A new playlist named `<Playlist Name> sorted` is immediately created in your Music app!

---

### 2. Command Line Interface (CLI)

#### List playlists in Apple Music:
```bash
python3 run_sorter.py --list
```

#### Sort a playlist and create the sorted version in Apple Music:
```bash
python3 run_sorter.py --playlist "Friday Night House"
```

#### Dry-run preview without modifying Apple Music:
```bash
python3 run_sorter.py --playlist "Friday Night House" --dry-run
```

#### Automatically exclude suggested outlier tracks:
```bash
python3 run_sorter.py --playlist "Friday Night House" --auto-remove-outliers
```

---

## Camelot DJ System Reference

The Camelot Wheel maps 24 major and minor keys into an easy 12-hour clock:

| Camelot | Musical Key | Camelot | Musical Key |
| :---: | :---: | :---: | :---: |
| **1B** / **1A** | B major / G# minor | **7B** / **7A** | F major / D minor |
| **2B** / **2A** | F# major / D# minor | **8B** / **8A** | C major / A minor |
| **3B** / **3A** | Db major / Bb minor | **9B** / **9A** | G major / E minor |
| **4B** / **4A** | Ab major / F minor | **10B** / **10A** | D major / B minor |
| **5B** / **5A** | Eb major / C minor | **11B** / **11A** | A major / F# minor |
| **6B** / **6A** | Bb major / G minor | **12B** / **12A** | E major / C# minor |

### Transition Rules
- **Same Key** (e.g. `8A` &rarr; `8A`): Perfect harmonic continuity.
- **Relative Major/Minor** (e.g. `8A` &harr; `8B`): Seamless mood shift with identical pitch collection.
- **Harmonic Step** (e.g. `8A` &rarr; `9A` or `7A`): Smooth harmonic modulation.
- **Energy Boost** (e.g. `8A` &rarr; `10A`): +2 hour jump for peak-time excitement.
- **Outliers / Jarring Clashes** (e.g. `8A` &rarr; `2A`): Tritone / opposite wheel dissonance identified and flagged for removal.

---

## Running Automated Tests

Run the test suite across harmonic analysis, Camelot transitions, audio DSP, and API endpoints:

```bash
python3 -m unittest discover -v
```
