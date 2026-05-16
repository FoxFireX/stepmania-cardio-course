# StepMania Cardio Course Generator

An automated tool to procedurally generate balanced, steady-state fitness playlists (Courses) from your StepMania or Project OutFox song library. It scans your files, filters out charts with high-impact or rhythm-breaking patterns, and bundles them into target-length cardio sets.

## Features

* **Procedural Packing**: Groups songs randomly into cohesive workout blocks targeting a specific session duration (e.g., 45 minutes).
* **Cardio-Focused Filtering**: Eliminates charts that drop below or exceed your physical intensity parameters.
* **Impact Reduction**: Screens out tracks containing excessive double-steps (jumps) to protect joints during prolonged play.
* **Gimmick Removal**: Rejects charts with heavy mine distributions that inflate step-density metrics artificially without maintaining a steady cadence.

## Prerequisites

* **Python 3.10 or higher**
* A local or network-accessible StepMania song repository containing standard `.sm` or `.ssc` files.

## Installation

1. Clone or download this repository to your local machine.
2. Ensure Python is installed by running:

```bash
python --version
```

## Configuration

Open `custom-course.py` in a text editor to adjust your target thresholds and file locations.

### Path Resolution
Update the network paths to point to your actual installation directory structure:

```python
SONGS_DIR = Path("\\\\nas\\media\\Stepmania\\Songs")
OUTPUT_DIR = Path("\\\\nas\\media\\Stepmania\\Courses\\Cardio Workout")
```

### Workout Intensity Parameters
Modify these values to tailor the generation to your personal fitness window:
* `TARGET_MIN_NPS`: The minimum allowed Notes-Per-Second boundary (Default: `2.5`).
* `TARGET_MAX_NPS`: The maximum allowed Notes-Per-Second boundary (Default: `4.0`).
* `MAX_JUMP_PERCENTAGE`: Maximum percentage of double-steps allowed per chart (Default: `0.07` / 7%).
* `MAX_MINE_PERCENTAGE`: Maximum percentage of mines allowed per chart (Default: `0.10` / 10%).
* `MIN_SONG_DURATION` / `MAX_SONG_DURATION`: Discards short transitions or grueling marathon files (Default: `80` to `360` seconds).

## Usage

Run the generation script from your terminal:

```bash
python custom-course.py
```

The script will scan your database, audit files against your constraints, and write sequential `.crs` files directly to your designated output directory.

## StepMania / OutFox Integration Constraints

To ensure StepMania reads, groups, and sorts the generated playlists accurately without parsing errors:

1. **Required Directory Nesting**: The output directory must be configured exactly one level deep relative to the root `Courses` directory (e.g., `Courses/Cardio Workout/`). Placing `.crs` files directly in the root folder causes parsing dropouts and broken song metadata lists on several engine variants.
2. **Menu Sorting**: Ensure your selection menu inside the game is set to **Group** or **Title**. Sorting by *Length* or *Difficulty* will override the zero-padded sequential order (`Set 01`, `Set 02`) established by the generation script.
3. **Cache Flushing**: Because this script operates directly on the raw file system, StepMania will not automatically register adjustments made to underlying `.sm`/`.ssc` files. If you modify your song files, clear your game's `Cache/` folder to force a clean database re-index.