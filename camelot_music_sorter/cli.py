"""Command line interface for the Camelot DJ Sorter."""

from __future__ import annotations
import argparse
import sys

from .apple_music import AppleMusicBridge, MusicAppError
from .audio_engine import ffmpeg_available
from .song_model import KeyResolver
from .sorter import HarmonicPlaylistSorter
from .server import run_web_server


def _key(song) -> str:
    return song.resolved_key.camelot if song.resolved_key else "?"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="camelot-sorter",
        description="Sort an Apple Music playlist for harmonic mixing (Camelot wheel) and save it as '<name> sorted'. "
                    "With no arguments, opens the web app.",
    )
    p.add_argument("--playlist", "-p", help="Name of the Apple Music playlist to sort")
    p.add_argument("--list", "-l", action="store_true", help="List your Apple Music playlists")
    p.add_argument("--web", "-w", action="store_true", help="Open the web app (default when no arguments are given)")
    p.add_argument("--port", type=int, default=8765, help="Port for the web app (default: 8765)")
    p.add_argument("--no-browser", action="store_true", help="Don't open the browser automatically")
    p.add_argument("--dry-run", action="store_true", help="Show the result without creating a playlist")
    p.add_argument("--auto-remove-outliers", action="store_true", help="Leave suggested removals out of the new playlist")
    p.add_argument("--start", help="Title (or part of it) of the song to open the set with")
    p.add_argument("--strategy", choices=["gradual_build", "balanced"], default="gradual_build",
                   help="gradual_build: step up the wheel for rising energy; balanced: smoothest in any direction")
    p.add_argument("--no-audio-analysis", action="store_true", help="Only use keys from tags/comments")
    p.add_argument("--demo", action="store_true", help="Use the built-in sample library instead of Music.app")
    return p


def cli_main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    demo = True if args.demo else None

    if args.web or not (args.playlist or args.list):
        run_web_server(port=args.port, demo=demo, open_browser=not args.no_browser)
        return 0

    bridge = AppleMusicBridge(demo=demo)
    try:
        return _run(args, bridge)
    except MusicAppError as e:
        print(f"\nError: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nCancelled.")
        return 130


def _run(args, bridge: AppleMusicBridge) -> int:
    if args.list:
        playlists = bridge.get_all_playlists()
        if not playlists:
            print("No playlists found.")
        for pl in playlists:
            print(f"  {pl['name']}  ({pl['track_count']} songs{', smart' if pl.get('smart') else ''})")
        return 0

    playlist = bridge.find_playlist(args.playlist)
    if not playlist:
        print(f"Playlist '{args.playlist}' not found. Use --list to see your playlists.", file=sys.stderr)
        return 1

    print(f"Reading '{playlist['name']}' from {'the demo library' if bridge.demo else 'Music'}…")
    songs = bridge.get_playlist_tracks(playlist["id"])
    if not songs:
        print("That playlist is empty.", file=sys.stderr)
        return 1

    if not args.no_audio_analysis and not ffmpeg_available():
        print("Note: ffmpeg not found, so audio analysis is off (brew install ffmpeg).")

    resolver = KeyResolver(enable_audio_analysis=not args.no_audio_analysis)
    interactive = sys.stdout.isatty()

    def progress(done, total, song):
        if interactive:
            print(f"\rCalculating keys… {done}/{total}", end="", flush=True)

    resolver.resolve_many(songs, progress)
    if interactive:
        print()

    start_id = None
    if args.start:
        match = next((s for s in songs if s.resolved_key and args.start.lower() in s.title.lower()), None)
        if not match:
            print(f"No song with a known key matches --start '{args.start}'.", file=sys.stderr)
            return 1
        start_id = match.id

    result = HarmonicPlaylistSorter(energy_flow_preference=args.strategy).sort_and_analyze(songs, start_id)
    summary = result.summary()

    print(f"\nSorted order for '{playlist['name']}':")
    for i, s in enumerate(result.sorted_songs):
        t = result.transitions[i] if i < len(result.transitions) else None
        mark = "" if t is None else ("  ✓" if t.is_smooth else ("" if t.is_unknown else "  ✗"))
        nxt = f"  → {t.description}{mark}" if t else ""
        print(f"  {i + 1:3d}. [{_key(s):>3}] {s.artist} – {s.title}{nxt}")

    print(f"\nSmooth mixes: {summary['smooth_transitions']}/{summary['scored_transitions']}   "
          f"Friction reduced: {summary['improvement_percent']:.0f}% "
          f"({summary['initial_penalty']} → {summary['final_penalty']})")

    if result.unknown_key_songs:
        print(f"\n{len(result.unknown_key_songs)} song(s) have no known key and were placed at the end:")
        for s in result.unknown_key_songs:
            print(f"  ? {s.artist} – {s.title}: {s.key_note}")

    if result.suggestions_to_remove:
        print("\nSuggested removals:")
        for sug in result.suggestions_to_remove:
            print(f"  ✗ [{_key(sug.song)}] {sug.song.artist} – {sug.song.title}")
            print(f"      {sug.reason}")
            print(f"      Tip: {sug.alternative_suggestion}")
    else:
        print("\nNo removals suggested; every song fits the harmonic flow.")

    to_export = result.sorted_songs
    if args.auto_remove_outliers and result.suggestions_to_remove:
        drop = {s.song.id for s in result.suggestions_to_remove}
        to_export = [s for s in to_export if s.id not in drop]
        print(f"\nLeaving out {len(drop)} suggested song(s).")

    if args.dry_run:
        print("\nDry run: no playlist was created.")
        return 0

    created = bridge.create_sorted_playlist(playlist["id"], playlist["name"], to_export)
    note = " (replaced the previous sorted copy)" if created["replaced"] else ""
    print(f"\nCreated '{created['name']}' in Apple Music with {created['added']} songs{note}.")
    if created["added"] < created["requested"]:
        print(f"Warning: {created['requested'] - created['added']} song(s) could not be added.")
    return 0


if __name__ == "__main__":
    sys.exit(cli_main())
