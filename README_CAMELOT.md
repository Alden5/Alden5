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

1. Click a playlist in the sidebar. Its keys are calculated and it's sorted right away.
2. Review the running order. Each row shows the song's Camelot key, energy level (1–10),
   BPM and where the key came from. Between rows you can see the granular **1–100 compatibility score**
   and how well each song mixes into the next: green (85–100) is seamless, cyan (70–84) is a clean mix,
   yellow (50–69) is workable, and red (<50) is a clash. The **Set journey** chart on the right displays
   the overall energy curve and tempo across your playlist.
3. Choose a **Flow**:
   - *Build energy* prefers rising tempo, stepping up the wheel (8A → 9A → 10A), and smooth energy progression.
   - *Smoothest* minimizes clashes and abrupt energy swings in either direction.
4. In the **Trim** tab on the right, choose how many songs you're willing to remove. The app
   picks the songs whose removal helps most and summarizes the effect: key clashes,
   smooth mixes and mixing friction before and after. Press **Remove these songs**
   to apply the plan, **Remove** for a single song, or **Keep it** to lock a song so
   it's never suggested. See [Trimming the set](#trimming-the-set) for details.
5. Press **Create sorted playlist**. The new playlist is built top to bottom in the
   order shown. Running it again replaces the earlier sorted copy. If you already
   have your own playlist with that name, the new one is called `… sorted (2)`
   instead, and yours is not touched.

### Trimming the set

You set a limit on how many songs to remove. Within that limit, the app looks
for the cuts that make the set flow best:

- Each round, it tries removing the songs that are hardest to mix in and out of,
  re-sorts the set without each one, and keeps the removal that helps most.
- Songs that only fit with each other (for example two songs in a key far from
  the rest) are tried as a group, since removing just one wouldn't fix anything.
- It stops early when no removal helps much, so it never cuts songs just to use
  up your limit. If going over your limit would fix another clash, it says so
  and offers to raise it.
- Songs you placed manually are never suggested and keep their place.

### Shaping the order yourself

The playlist is built from the top down. When you place a song, it's marked
**Manual**, the songs above it stay where they are, and everything below it is
re-sorted around your choice.

- **Drag** a song by its handle to any spot, or use the move button to type a
  position (or pick Top, Middle or Bottom).
- The **pin** button locks a song where it is. Pressing it again unlocks the song,
  and the order is re-sorted from that song down.
- **Remove** (✕), or dragging a song onto the **Removed** tray, drops the song
  and re-sorts the songs below it. You can drag removed songs back into the list
  at any spot. **Restore** puts a song back where it fits best without moving
  anything else.
- **Re-sort** and **Flow** changes re-sort everything except manual songs.
  **Clear manual** unlocks them all.
- **Undo/Redo** (⌘Z / ⇧⌘Z) step through every change. Press `/` to filter the list.
- **Keyboard:** click a song (or tab to it), then use ↑/↓ to select, ⌥↑/⌥↓ to move it
  (this locks it), `L` to lock or unlock, `Delete` to remove, and `Enter` for the
  song menu. The keyboard button in the header lists every shortcut.
- While you drag a song, a **Drop here to remove** target appears at the bottom.
  Removed songs are in the **Removed** tab, and the **Keys & flow** tab has the
  Camelot wheel and the set journey chart. **Transitions** hides the mix notes
  between rows for a compact list.

Try it without touching your library: `camelot-sorter --demo`.

### Command line

```bash
camelot-sorter --list                                   # list playlists
camelot-sorter -p "Friday Night House"                  # sort and create "Friday Night House sorted"
camelot-sorter -p "Friday Night House" --dry-run        # preview only
camelot-sorter -p "Friday Night House" --max-remove 3 --dry-run   # cut up to 3 songs and show the effect
camelot-sorter -p "Friday Night House" --auto-remove-outliers --start "Deep Inside"
```

## Where keys come from

Music doesn't store musical keys, so each song's key is found in this order:

1. **Comments or Grouping in Music.** Text such as `8A`, `8A - Energy 6`, `Am`,
   `F# minor` or Open Key `1m` is recognized. Mixed In Key writes keys here, and
   you can type them in yourself with **Get Info → Comments**. A key here always wins.
2. **An imported rekordbox analysis**, which also works for Apple Music streaming
   songs. See [Using keys from rekordbox](#using-keys-from-rekordbox).
3. **A key tag inside the audio file** (ID3 `TKEY` or iTunes `initialkey`), as
   written by Rekordbox, Mixed In Key, Traktor and similar tools.
4. **Audio analysis** of downloaded, non-DRM files (MP3, AAC/M4A, AIFF, WAV,
   FLAC). This uses ffmpeg plus chroma / Krumhansl–Kessler key profiles. The
   result shows a confidence percentage. Results are cached, so later runs are
   instant.

Apple Music streaming songs and DRM-protected downloads can't be analyzed by
this app. If one of these has no key in Comments or Grouping, it is marked **?**
and placed at the end instead of being given a guessed key. To include it,
import a rekordbox analysis (below) or add its key to Comments in Music and
press **↻**.

### Using keys from rekordbox

rekordbox can analyze Apple Music songs through its Apple Music integration,
but it keeps the results in its own library. To use them here:

1. In rekordbox, analyze the songs, then choose **File → Export Collection in
   xml format**.
2. In the app, press **Import XML** at the bottom of the sidebar and pick that
   file. The import is remembered, so you only need to repeat it after analyzing
   new songs in rekordbox (press **Replace**).

Songs are matched by file location when there is one, otherwise by title and
artist (ignoring things like "feat. …" or "(Remastered)"), using the song length
to tell versions apart. rekordbox's key is used when a song has no key in
Comments or Grouping, and its BPM fills in songs that have no BPM in Music.
Songs whose key came from rekordbox are tagged **rekordbox** in the list.

To keep those keys in Music itself, press **Save to Music** in the notice above
the list. The Camelot key is added in front of each song's existing Comments
(for example `8A | your comment`), and BPM is filled in where Music has none.
Nothing else is changed.

From the command line:

```bash
camelot-sorter -p "Friday Night House" --rekordbox ~/Desktop/rekordbox.xml --dry-run
camelot-sorter -p "Friday Night House" --rekordbox ~/Desktop/rekordbox.xml --save-rekordbox-keys
```

Without `--rekordbox`, the CLI uses the export last imported in the web app.

## Energy level detection

In addition to key and tempo, the sorter calculates an **Energy level (1.0 to 10.0)** for every song:
1. **Metadata tags**: Reads energy tags from comments or grouping (e.g. `8A - Energy 7`, `E:8`, `Energy level 6`).
2. **Audio analysis**: For local audio files, extracts RMS loudness, spectral centroid (brightness), and dynamic crest factor via ffmpeg.
3. **Smart metadata fallback**: When audio PCM is unavailable (streaming / cloud tracks), estimates energy using BPM, genre (e.g. ambient vs. techno/hardstyle), and rating.

## How sorting works

Each pair of songs gets a granular **1–100 compatibility score** based on:
- **Harmonic compatibility** (Camelot distance, relative major/minor, diagonal mood shifts; up to 60 points)
- **Tempo matching** (beatmatching margin and half/double-time harmony; up to 25 points)
- **Energy flow & continuity** (energy delta continuity; up to 15 points)

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
4. **Energy trajectory.** With **Build energy**, tempo and energy rise smoothly through the set while keys step up the wheel. With **Smoothest**, energy drops and extreme spikes are smoothed out.

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
