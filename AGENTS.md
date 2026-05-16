# Agent Architecture: StepMania Cardio Course Generator

This document details the functional specifications, algorithmic rules, and data structures of the static analysis script used to generate procedurally balanced fitness courses for StepMania/Project OutFox.

## 1. System Overview

The script automates the creation of `.crs` (Course) files by parsing a local song repository, evaluating the step density and chart properties of discovered songs, filtering out content that violates mechanical constraints, and organizing the matching charts into timed workout playlists.

```text
[ Songs Directory ] ──> [ Audio Engine / Parsers ] ──> [ Fitness Evaluator ]
                                                              │ (NPS / Jumps / Mines)
                                                              ▼
[ Course Manifests ] <── [ Workout Packing Engine ] <── [ Validated Queue ]
```

---

## 2. Component Specifications

### 2.1 Configuration Layer
Defines strict mechanical thresholds tailored for a steady-state cardio workout:
* **`TARGET_MIN_NPS` / `TARGET_MAX_NPS` (2.5 - 4.0)**: Establishes the physical intensity window. Prevents under-exertion or premature fatigue.
* **`MAX_JUMP_PERCENTAGE` (7%)**: Limits double-note steps to prevent excessive high-impact plyometric stress, protecting joints over long sessions.
* **`MAX_MINE_PERCENTAGE` (10%)**: Filters out gimmick or hazard-heavy charts that inflate step density metrics artificially without contributing to a rhythmic cadence.
* **`MIN_SONG_DURATION` / `MAX_SONG_DURATION` (80s - 360s)**: Screens out short transitions/marathons to ensure predictable block lengths.

### 2.2 Parser Engine
The system employs a dual-format parser designed to handle traditional StepMania ecosystems:
* **MSD Tokenizer (`parse_msd`)**: Cleans single-line and block comments (`//`) via regular expressions, then uses a non-greedy regex pattern `\#([^:]+):(.*?);` to slice standard tag-value pairs.
* **Robust SSC Parser (`robust_ssc_parser`)**: Tracks stateful properties across newer StepMania 5/OutFox `.ssc` manifests. It processes data line-by-line, utilizing contextual toggles (`inside_note_block`) to isolate step metadata from global song attributes.

### 2.3 Fitness Evaluator (Audit Engine)
For every chart identified, the evaluator calculates operational metrics based on step patterns:
$$\text{NPS} = \frac{\text{Total Steps}}{\text{Song Duration}}$$
$$\text{Jump \%} = \frac{\text{Double Notes}}{\text{Total Steps}}$$

Charts are explicitly dropped if they fail any bounding constraint. An `AUDIT_LIST` permits targeted logging of specific files to diagnose parsing irregularities or boundary failures.

### 2.4 Workout Packing Engine
Applies a greedy, multi-bin packing algorithm:
1. Shuffles the validated chart queue to ensure structural variance between sets.
2. Accumulates tracks sequentially until the aggregate duration matches or exceeds `TARGET_SET_DURATION` (typically 45 minutes).
3. Flushes the current queue into a sequentially numbered `.crs` file and instantiates a new set block.

---

## 3. Input/Output Data Specifications

### 3.1 Expected Input Structure
The source directories must conform to the standard two-tier StepMania hierarchy to pass matching logic:

```text
Songs/
└── [Group Folder]/
    └── [Song Folder]/
        ├── Song_File.sm
        └── Song_File.ssc
```

### 3.2 Generated Course Format (.crs)
To guarantee isolation, proper metadata initialization, and avoid cache validation conflicts across different engine variants, the generated courses are explicitly isolated into a unified target subdirectory (`Courses/Cardio Workout/`).

The script outputs plain text payloads structured as follows:
```text
#COURSE:[Cardio Workout] Set NN;
#GROUP:Cardio Workouts;
#BACKGROUND:inline;
#BANNER:inline;

// METRICS -> NPS: X.XX | Jumps: X.X% | Mines: X.X% | Len: XXXs
#SONG:[Group Folder]/[Song Folder]:[Difficulty];