from setuptools import setup, find_packages

setup(
    name="camelot-music-sorter",
    version="1.0.0",
    description="Harmonically organize Apple Music playlists on macOS using the Camelot DJ System",
    author="Camelot DJ Sorter",
    packages=find_packages(),
    install_requires=[
        "numpy>=1.20.0",
    ],
    entry_points={
        "console_scripts": [
            "camelot-sorter=camelot_music_sorter.cli:cli_main",
        ],
    },
    python_requires=">=3.9",
)
