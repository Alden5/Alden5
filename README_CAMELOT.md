# Camelot DJ Sorter for Apple Music (macOS)

Takes an Apple Music playlist, works out the key of every song, puts the songs
in the smoothest harmonic mixing order using the Camelot wheel, suggests songs
that don't fit, and saves the result as a **new playlist named
`<original name> sorted`**. Your original playlist is never changed.

## Setup

You need macOS with the Music app and Python 3.9 or newer. If `python3
--version` asks you to install developer tools, accept the prompt.

```bash
git clone https://github.com/Alden5/Alden5.git
cd Alden5
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
brew install ffmpeg        # optional but recommended: enables audio key detection
```

The first time the app talks to Music, macOS asks whether Terminal may control
Music. Click **OK**. If you clicked "Don't Allow", turn it back on in
**System Settings → Privacy & Security → Automation → Terminal → Music**.

## Using the app

```bash
source .venv/bin/activate   # in each new Terminal window
camelot-sorter              # or: python3 run_sorter.py
```

Your browser opens at `http://localhost:8765`.

1. Choose a playlist and press **Analyze & Sort**.
2. Review the order. Each row shows the song's Camelot key and how well it mixes
   into the next song. Green means a smooth mix and red means a key clash.
3. Under **Suggested removals**, press **Remove** on any song you want to leave out,
   or **Remove all suggested**. Removed songs can be restored.
4. Optionally choose **Start with** to fix the opening song, or change **Flow**:
   - *Build energy* prefers rising tempo and stepping up the wheel (8A → 9A → 10A).
   - *Smoothest overall* minimizes clashes in either direction.
5. Press **Create sorted playlist**. Running it again replaces the earlier
   sorted copy. If you already have your own playlist with that name, the new one
   is called `… sorted (2)` instead, and yours is not touched.

Try it without touching your library: `camelot-sorter --demo`.

### Command line

```bash
camelot-sorter --list                                   # list playlists
camelot-sorter -p "Friday Night House"                  # sort and create "Friday Night House sorted"
camelot-sorter -p "Friday Night House" --dry-run        # preview only
camelot-sorter -p "Friday Night House" --auto-remove-outliers --start "Deep Inside"
```

## Where keys come from

Music doesn't store musical keys, so each song's key is found in this order:

1. **Comments or Grouping in Music.** Text such as `8A`, `8A - Energy 6`, `Am`,
   `F# minor` or Open Key `1m` is recognized. Mixed In Key writes keys here, and
   you can type them in yourself with **Get Info → Comments**.
2. **A key tag inside the audio file** (ID3 `TKEY` or iTunes `initialkey`), as
   written by Rekordbox, Mixed In Key, Traktor and similar tools.
3. **Audio analysis** of downloaded, non-DRM files (MP3, AAC/M4A, AIFF, WAV,
   FLAC). This uses ffmpeg plus chroma / Krumhansl–Kessler key profiles. The
   result shows a confidence percentage. Results are cached, so later runs are
   instant.

Apple Music streaming songs and DRM-protected downloads can't be analyzed. If
one of these has no key in Comments or Grouping, it is marked **?** and placed
at the end instead of being given a guessed key. To include it, add its key to
Comments in Music and press **↻**.

## How sorting works

Each pair of songs gets a mixing cost based on Camelot rules:

| Move | Example | Cost |
|---|---|---:|
| Same key | 8A → 8A | 0 |
| Relative major/minor | 8A ↔ 8B | 0.2 |
| One step around the wheel | 8A → 9A / 7A | 0.5 |
| Diagonal mood shift | 8A → 9B, 8B → 7A | 1.0 |
| Other diagonal | 8A → 7B, 8B → 9A | 1.8 |
| Energy boost / drop | 8A → 10A / 8A → 6A | 2.0 / 2.3 |
| Semitone lift (cut, don't blend) | 8A → 3A | 3.0 |
| Three or more steps | 8A → 11A … 2A | 4.5 – 8.5 |

If BPM is set in Music, tempo jumps of more than about 6% add to the cost. Half
and double time (87 ↔ 174) count as compatible. Any transition costing more than
2.5 is a **clash**.

The app looks for the best order in this priority:

1. **Fewest clashes.** Each clash carries a large penalty, so the app will take
   two smooth steps (8A → 10A → 12A) over one jump (8A → 12A).
2. **Least total friction** across all transitions.
3. **Variety.** The same artist doesn't play twice in a row, including
   features (e.g. "Meduza" and "Meduza, Becky Hill & Goodboys"), and duplicate
   copies of a song are never placed next to each other.
4. With **Build energy**, tempo rises through the set and keys step up the wheel.

Playlists of up to 13 songs are solved exactly. Larger ones use iterated local
search: 2-opt and Or-opt moves, restarted from random shuffles. This takes
about 1 second for 150 songs and is capped at 2.5 seconds. The same playlist
always gives the same order.

A song is **suggested for removal** in either of these cases:

- It belongs to a small minority (no more than a quarter of the playlist) whose
  keys are 4 or more steps from the playlist's tonal center, and none of the
  other songs mix into it smoothly.
- It sits between two songs that mix well with each other, but it clashes with
  both of them.

## Privacy and safety

The web app only listens on `127.0.0.1` and refuses requests from other
websites. Nothing leaves your Mac.

## Tests

```bash
python3 -m unittest -v
```
