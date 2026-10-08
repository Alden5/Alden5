"""
Command line interface for Camelot DJ Sorter for Apple Music.
"""

from __future__ import annotations
import argparse
import sys
import os

from .apple_music import AppleMusicBridge
from .song_model import KeyResolver
from .sorter import HarmonicPlaylistSorter
from .server import run_web_server


def cli_main():
    parser = argparse.ArgumentParser(
        description="Harmonically sort Apple Music playlists on macOS using the Camelot DJ System."
    )
    parser.add_argument("--playlist", "-p", type=str, help="Name of playlist in Apple Music to sort")
    parser.add_argument("--list", "-l", action="store_true", help="List available playlists in Apple Music")
    parser.add_argument("--web", "-w", action="store_true", help="Launch interactive Web UI app")
    parser.add_argument("--port", type=int, default=8765, help="Port for Web UI (default: 8765)")
    parser.add_argument("--dry-run", action="store_true", help="Show sorted playlist and suggestions without creating playlist in Apple Music")
    parser.add_argument("--auto-remove-outliers", action="store_true", help="Automatically exclude suggested outliers when creating the sorted playlist")
    parser.add_argument("--strategy", choices=["gradual_build", "balanced"], default="gradual_build",
                        help="Harmonic progression preference: gradual_build (energy climb) or balanced")

    args = parser.parse_args()

    bridge = AppleMusicBridge()

    if args.web or (len(sys.argv) == 1):
        # Default action with no args or --web is to run the app web interface
        print(f"Starting Camelot DJ Apple Music Sorter on http://localhost:{args.port} ...")
        if not bridge.is_macos():
            print("Note: Running in test/emulation mode (not on macOS). Mock Music.app library active.")
        run_web_server(port=args.port)
        return

    if args.list:
        playlists = bridge.get_all_playlists()
        print("\nAvailable Apple Music Playlists:")
        print("---------------------------------")
        for pl in playlists:
            print(f"- {pl['name']} ({pl['track_count']} tracks)")
        print()
        return

    if not args.playlist:
        parser.print_help()
        sys.exit(1)

    print(f"\n[1/4] Fetching tracks for playlist '{args.playlist}'...")
    tracks = bridge.get_playlist_tracks(args.playlist)
    if not tracks:
        print(f"Error: No tracks found in playlist '{args.playlist}'.")
        sys.exit(1)

    print(f"Found {len(tracks)} tracks.")

    print("\n[2/4] Calculating keys and Camelot values for all songs...")
    resolver = KeyResolver(enable_audio_analysis=True)
    for t in tracks:
        resolver.resolve(t)
        k_str = t.resolved_key.camelot if t.resolved_key else "Unknown"
        k_name = t.resolved_key.standard_name if t.resolved_key else "Unknown"
        print(f"  • {t.artist} - {t.title}: {k_str} ({k_name}) [Source: {t.key_source}]")

    print("\n[3/4] Optimizing playlist order using Camelot harmonic rules...")
    sorter = HarmonicPlaylistSorter(energy_flow_preference=args.strategy)
    sort_result = sorter.sort_and_analyze(tracks)

    summary = sort_result.summary()
    print(f"\nOptimization complete:")
    print(f"  Initial transition friction: {summary['initial_penalty']}")
    print(f"  Final transition friction:   {summary['final_penalty']}")
    print(f"  Improvement:                 +{summary['improvement_percent']}%")
    print(f"  Smooth transitions:          {summary['smooth_transitions']} / {len(sort_result.transitions)}")

    if sort_result.suggestions_to_remove:
        print("\n⚠️  Suggested Songs to Remove (Severe Harmonic Bottlenecks):")
        print("---------------------------------------------------------")
        for sug in sort_result.suggestions_to_remove:
            k_str = sug.song.resolved_key.camelot if sug.song.resolved_key else "??"
            print(f"  ❌ {sug.song.artist} - {sug.song.title} [{k_str}]")
            print(f"     Reason: {sug.reason}")
            print(f"     Advice: {sug.alternative_suggestion}\n")
    else:
        print("\n✨ All tracks fit cleanly into the harmonic flow; no removals recommended.")

    print("\nRecommended Sorted Sequence:")
    print("----------------------------")
    for i, s in enumerate(sort_result.sorted_songs):
        k_str = s.resolved_key.camelot if s.resolved_key else "??"
        k_name = s.resolved_key.standard_name if s.resolved_key else "??"
        trans_info = ""
        if i < len(sort_result.transitions):
            t = sort_result.transitions[i]
            trans_info = f" -> [{t.description}]"
        print(f"  {i+1:2d}. [{k_str:3s}] {s.artist} - {s.title} ({k_name}){trans_info}")

    final_tracks_to_export = sort_result.sorted_songs
    if args.auto_remove_outliers and sort_result.suggestions_to_remove:
        outlier_ids = {s.song.id for s in sort_result.suggestions_to_remove}
        final_tracks_to_export = [s for s in sort_result.sorted_songs if s.id not in outlier_ids]
        print(f"\nAuto-removing {len(outlier_ids)} outliers from target export.")

    if not args.dry_run:
        print(f"\n[4/4] Creating new sorted playlist in Apple Music...")
        new_name = bridge.create_sorted_playlist(args.playlist, final_tracks_to_export, suffix="sorted")
        print(f"✅ Success! Created Apple Music playlist: '{new_name}' with {len(final_tracks_to_export)} tracks.")
    else:
        print(f"\n[4/4] Dry run specified. Skipping playlist creation in Apple Music.")


if __name__ == "__main__":
    cli_main()
