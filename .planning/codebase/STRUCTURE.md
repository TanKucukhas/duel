# Codebase Structure

**Analysis Date:** 2026-03-01

## Directory Layout

```
diablo2-duel/
├── demo/                           # Web-based character viewer (PixiJS frontend)
│   ├── index.html                 # HTML entry point, controls panel UI
│   ├── main.js                    # PixiJS animation engine + input handling
│   └── assets/                    # Pre-generated sprite + map assets
│       ├── sprites/               # Character spritesheets by class/weapon
│       │   ├── manifest.json      # Index of all character/weapon combos
│       │   ├── ba/                # Barbarian
│       │   ├── am/                # Amazon
│       │   ├── ne/                # Necromancer
│       │   ├── pa/                # Paladin
│       │   ├── so/                # Sorceress
│       │   ├── dz/                # Druid
│       │   └── ai/                # Assassin
│       │       └── [WEAPON]/      # Weapon class (HTH, 1HS, BOW, etc.)
│       │           ├── atlas.json # Frame metadata (dims, anchor, speed)
│       │           ├── NU_*.png   # Neutral stance spritesheet
│       │           ├── WL_*.png   # Walk animation spritesheet
│       │           ├── RN_*.png   # Run animation spritesheet
│       │           └── [other anim modes]
│       └── maps/                  # Pre-rendered map quarters
│           └── act1_town/         # Act 1 Town
│               ├── manifest.json  # Map metadata
│               └── town*.png      # N/S/E/W quarter renders
├── tools/                         # Backend Python utilities
│   ├── dcc_decoder.py            # Diablo 2 sprite decompressor
│   ├── ds1_decoder.py            # Diablo 2 map layout parser
│   ├── dt1_decoder.py            # Diablo 2 tile graphics decompressor
│   ├── generate_sprites.py       # Orchestrator: DCC → spritesheet + atlas
│   └── render_map.py             # DS1 + DT1 → isometric PNG compositor
├── Diablo2_all/                  # Extracted game assets (source data)
│   └── extracted/                # From MPQExtractor output
│       ├── data/data/global/
│       │   ├── CHARS/            # Character sprite DCC files
│       │   └── palette/          # ACT1-ACT5 + Units palettes
│       └── tiles/data/global/tiles/  # Tile DT1 files by act
├── MPQExtractor/                 # C++ tool to extract MPQ archives
│   ├── CMakeLists.txt
│   ├── src/
│   │   └── main.cpp             # CLI tool
│   └── StormLib/                # Git submodule (Blizzard MPQ parser)
└── pcx-to-spritesheet/          # Legacy PCX → sprite tool (unused)
```

## Directory Purposes

**demo/:**
- Purpose: Production-ready web viewer for character animations
- Contains: Single-page HTML app with inline PixiJS, generated sprite/map assets
- Key files: `index.html` (UI structure + styles), `main.js` (rendering + logic)

**demo/assets/sprites/:**
- Purpose: Generated character animation spritesheets indexed by class and weapon
- Contains: PNG spritesheets (multiple animations per weapon) + JSON atlases with metadata
- Key files: `manifest.json` (top-level index), per-weapon `atlas.json` files
- Structure: Each character class (BA, AM, etc.) → weapon class (HTH, 1HS, BOW, etc.) → animations

**demo/assets/maps/:**
- Purpose: Pre-rendered isometric maps for display in viewer
- Contains: PNG composites of DS1 map data + DT1 tiles
- Key files: `manifest.json` (map metadata), `town*.png` (4 quarters of Act 1 town)

**tools/:**
- Purpose: Backend processing pipeline for asset extraction and conversion
- Contains: Format decoders (binary parsers), composition logic, PNG generation
- Key files: Three decoders (dcc_, ds1_, dt1_), two generators (generate_sprites, render_map)

**Diablo2_all/extracted/:**
- Purpose: Source game assets extracted from Diablo 2 MPQ files
- Contains: Organized directories of DCC files, DT1 files, and palette data
- Location: `/extracted/data/data/global/CHARS/`, `/extracted/data/data/global/palette/`, `/extracted/tiles/`
- Note: Not all extracted files are committed; some regenerated per build

**MPQExtractor/:**
- Purpose: Command-line tool to extract binary assets from Blizzard game archives
- Contains: C++ source + StormLib submodule (MPQ format support)
- Used by: Initial asset extraction workflow (not part of normal web viewer build)

## Key File Locations

**Entry Points:**
- `demo/index.html`: Web application entry point
- `tools/generate_sprites.py`: Batch sprite generation orchestrator
- `tools/render_map.py`: Map rendering utility

**Configuration:**
- `demo/assets/sprites/manifest.json`: Character/weapon availability index
- `demo/assets/sprites/[class]/[weapon]/atlas.json`: Frame data for single character+weapon combo
- `demo/assets/maps/act1_town/manifest.json`: Map metadata

**Core Logic:**
- `demo/main.js` (lines 1-100): PixiJS setup, map loading, manifest loading
- `demo/main.js` (lines 170-239): Character + weapon loading, texture creation
- `demo/main.js` (lines 390-480): Game loop, animation updates, camera tracking
- `tools/generate_sprites.py` (lines 480-572): Character generation orchestration
- `tools/generate_sprites.py` (lines 282-336): Multi-layer composition with COF priorities
- `tools/dcc_decoder.py` (lines 131-247): DCC file decoding entry point

**Testing:**
- Not detected (no test framework configured)

## Naming Conventions

**Files:**

- **DCC sprites:** `{CHAR}{LAYER}{ARMOR}{ANIM_MODE}{WEAPON}.dcc`
  - Example: `BANUHTH.dcc` = Barbarian / Head / Lite Armor / Neutral / Hand-to-Hand
  - Layers: HD (head), TR (torso), LG (legs), RA (right arm), LA (left arm), RH (right hand), LH (left hand), SH (shield)
  - Armor codes: LIT (lite), MED (medium), HVY (heavy)
  - Anim modes: NU (neutral), WL (walk), RN (run), A1/A2 (attack 1/2), SC (cast), etc.

- **COF files:** `{CHAR}{ANIM_MODE}{WEAPON}.COF`
  - Example: `BANUHTH.COF` = Barbarian / Neutral / Hand-to-Hand
  - Specifies layer count, frame count, priorities, and per-layer weapon classes

- **DS1 maps:** `{NAME}.ds1` (e.g., `townS1.ds1`)
  - Stores tile grid, object placements, DT1 file references

- **DT1 tiles:** `{NAME}.dt1` (e.g., `floor.dt1`)
  - Multiple tiles per file, indexed by (orientation, mainIndex, subIndex)

- **Palettes:** `pal.dat` (256 colors, BGR format)
  - Located in `ACT1/`, `ACT2/`, etc. directories

- **Generated spritesheets:** `{MODE}_{WEAPON}.png`
  - Example: `NU_HTH.png` = Neutral animation, hand-to-hand weapon
  - Arranged as: columns = frames per direction, rows = directions (0-7)

**Directories:**

- Character/weapon asset paths: `demo/assets/sprites/{class_code}/{weapon_class}/`
- Map asset paths: `demo/assets/maps/{map_name}/`
- DCC layer paths: `Diablo2_all/extracted/data/data/global/CHARS/{CLASS}/{LAYER}/`

## Where to Add New Code

**New Feature:**
- **Interactive features** (UI, input handling, camera): Add to `demo/main.js` game loop or input section
- **Asset loading logic**: Extend `demo/main.js` character loading (lines 170-239)
- **Backend transformations**: Add Python script to `tools/` directory

**New Component/Module:**
- **Asset generators**: Create new Python script in `tools/` following the pattern of `generate_sprites.py`
  - Must accept asset sources from `Diablo2_all/extracted/`
  - Must output to `demo/assets/` with JSON manifest
- **PixiJS components**: Add classes/functions to `demo/main.js` (example: particle effects, HUD elements)

**Utilities:**
- **Shared decoders**: Extend existing `tools/*_decoder.py` files (do not create new decoder files)
- **Shared helpers in JS**: Add utility functions to `demo/main.js` top section before game loop
- **Data structures**: Define in decoder modules with dataclasses (Python) or inline objects (JavaScript)

## Special Directories

**demo/assets/:**
- Purpose: Static web assets (sprites, maps) served directly by browser
- Generated: Yes (from `tools/` Python scripts)
- Committed: Partial (manifest.json committed, PNG files only if < 1MB per file or critical for demo)
- How to regenerate: `cd tools && python3 generate_sprites.py --batch && python3 render_map.py <ds1_path> <output>`

**Diablo2_all/extracted/:**
- Purpose: Extracted source game data (DCC, DS1, DT1, palette files)
- Generated: Partially (extracted from MPQ files via MPQExtractor, then post-processed)
- Committed: Some key assets only; bulk DCC/DT1 files typically not committed
- How to regenerate: Run MPQExtractor against Diablo 2 MPQ archives (requires original game files)

**MPQExtractor/build/:**
- Purpose: Compiled C++ binary output
- Generated: Yes
- Committed: No
- How to build: `mkdir build && cd build && cmake .. && cmake --build .`

## Code Organization Principles

**Python Backend:**
- **Separation of concerns:** Each decoder module (`dcc_`, `ds1_`, `dt1_`) handles single format
- **Data-first design:** Decoders return dataclasses, composition logic works with intermediate representations
- **Palette independence:** Decoders return palette indices; palette applied at generation time
- **CLI-first:** Scripts accept command-line arguments for batch processing

**JavaScript Frontend:**
- **Global state pattern:** Single animation/position/input state updated per frame (see `demo/main.js` lines 49-66)
- **Direction-indexed storage:** All directional data stored as arrays of 8 (0-7 for cardinal/diagonal directions)
- **Event-driven input:** Keydown/keyup store state, game loop queries on each tick
- **Layer-based rendering:** PixiJS container hierarchy: app.stage → world (camera target) → mapContainer + character sprite

---

*Structure analysis: 2026-03-01*
