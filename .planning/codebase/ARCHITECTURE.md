# Architecture

**Analysis Date:** 2026-03-01

## Pattern Overview

**Overall:** Data extraction and asset rendering pipeline with multi-layered decoding architecture.

**Key Characteristics:**
- Decode-first architecture: Binary format parsers (DCC, DS1, DT1) → intermediate data structures → asset generation
- Python backend for heavy file processing (sprite compilation, map rendering)
- Web frontend for interactive visualization (PixiJS-based character viewer)
- Asset manifest-driven composition for layer blending and animation sequencing

## Layers

**Data Extraction & Parsing Layer:**
- Purpose: Read and decode Diablo 2 binary asset formats
- Location: `tools/dcc_decoder.py`, `tools/ds1_decoder.py`, `tools/dt1_decoder.py`
- Contains: Bit-stream readers, struct parsers, compression decoders
- Depends on: Binary file format specifications
- Used by: Sprite generation and map rendering pipeline

**Sprite Composition Layer:**
- Purpose: Composite multi-layer character sprites with COF-driven draw order
- Location: `tools/generate_sprites.py`
- Contains: Layer loading, palette application, spritesheet generation, JSON atlas creation
- Depends on: DCC decoder, palette data, COF file parsing
- Used by: Demo application sprite assets

**Map Rendering Layer:**
- Purpose: Render isometric DS1 maps using DT1 tile graphics
- Location: `tools/render_map.py`
- Contains: Tile selection, palette lookup, isometric compositing
- Depends on: DS1 and DT1 decoders, tile and palette files
- Used by: Map asset generation (demo includes pre-rendered town quarters)

**Client Rendering Layer:**
- Purpose: Display decoded assets with interactive camera and animation controls
- Location: `demo/main.js`
- Contains: PixiJS scene management, animation playback, input handling, camera tracking
- Depends on: JSON manifests, sprite PNGs, direction mapping
- Used by: `demo/index.html` viewer application

**Asset Management Layer:**
- Purpose: Index and manifest generated assets for client consumption
- Location: `demo/assets/sprites/manifest.json`, per-character `atlas.json` files, `demo/assets/maps/act1_town/manifest.json`
- Contains: Character/weapon metadata, animation frame data, texture coordinates
- Depends on: Generated sprite sheets and map tiles
- Used by: Client layer for asset discovery and loading

## Data Flow

**Sprite Generation Flow:**

1. Diablo 2 MPQ archives → MPQExtractor tool → Extracted `/CHARS/`, `/data/` directories
2. Per-character/weapon: Extract weapon class from COF files → detect weapon graphics
3. For each animation mode: Load layered DCC files (body, armor, weapons) → decode pixel data with palette
4. Composite layers using COF priority table → generate spritesheet PNG
5. Create JSON atlas with frame metadata (dimensions, anchor points, animation speed)
6. `generate_sprites.py --batch` creates manifest.json index of all character/weapon combos

**Character Viewer Flow:**

1. Browser loads `demo/index.html` with embedded PixiJS
2. `main.js` fetches `sprites/manifest.json` to populate character/weapon dropdown
3. User selects character → fetches character's `atlas.json` for animation metadata
4. For selected weapon: Load sprite PNG sheet, create textures for each frame
5. Game loop animates frames based on direction (8-way) and state (walk/run/attack/cast/etc)
6. Camera follows character position, zoom controlled via mouse wheel

**Map Rendering Flow:**

1. DS1 file specifies DT1 file references and tile grid
2. `render_map.py` loads referenced DT1 files → builds tile index
3. For each DS1 cell: Select DT1 tile by (orientation, mainIndex, subIndex)
4. Composite tiles in isometric projection using three-pass rendering:
   - Pass 1: Floor tiles (orientation 0)
   - Pass 2: Wall tiles with depth (orientations 1-19)
   - Pass 3: Shadows and overlays
5. Output composite PNG (pre-rendered in demo)

**State Management:**

- Characters: Mutable position (charWorldX/Y), animation state, weapon/armor selection
- Animations: Direction-indexed frame arrays loaded on demand, FPS lookup from metadata
- Input: Keyboard state map (keys[]) checked each frame for movement/actions
- One-shot animations: Tracked separately with optional callback for death → dead transition

## Key Abstractions

**BitReader:**
- Purpose: Read arbitrary-length sequences from bit-packed binary data
- Examples: `tools/dcc_decoder.py` lines 15-53
- Pattern: Bit position tracking with unsigned/signed read operations

**DCCFile/DCCDirection/DCCFrame:**
- Purpose: Represent sprite animation data at file/direction/frame hierarchy
- Examples: `tools/dcc_decoder.py` lines 93-129, frame decompression lines 429-514
- Pattern: Parallel pixel buffers (for cell reuse) + per-frame pixel data generation

**DS1File/DS1Cell:**
- Purpose: Map layout grid with tile references
- Examples: `tools/ds1_decoder.py` lines 12-52
- Pattern: Flat array indexed as `[row * width + col]` for 2D tile grids

**DT1Tile/DT1Block:**
- Purpose: Isometric tile with sub-block pixel data
- Examples: `tools/dt1_decoder.py` lines 52-71
- Pattern: Variable-height tiles (negative height for upper layers), block-based RLE/isometric encoding

**CharacterAnimationState:**
- Purpose: Track current animation, direction, frame, and playback context
- Examples: `demo/main.js` lines 49-61
- Pattern: Global state updated each frame, supports interruption by one-shot animations

**SpriteAtlas:**
- Purpose: JSON metadata for sprite texture coordinates and animation timing
- Examples: `demo/assets/sprites/ba/HTH/atlas.json` (generated), consumed at `demo/main.js` lines 170-239
- Pattern: Flat frame array indexed as `[direction][frame]`, per-animation metadata (speed, dimensions)

## Entry Points

**Sprite Generation:**
- Location: `tools/generate_sprites.py` main()
- Triggers: Manual execution with `python3 generate_sprites.py --batch`
- Responsibilities: Orchestrate DCC decoding → COF parsing → layer compositing → spritesheet + atlas creation

**Character Viewer:**
- Location: `demo/index.html` + `demo/main.js`
- Triggers: Browser GET request to `demo/index.html`
- Responsibilities: Initialize PixiJS, load manifest, manage character/weapon selection, run animation loop

**Map Rendering:**
- Location: `tools/render_map.py` main()
- Triggers: Manual execution with `python3 render_map.py <ds1_path> <output_png>`
- Responsibilities: Load DS1 + DT1s + palette, composite tiles, save PNG

## Error Handling

**Strategy:** Graceful degradation with console logging and fallback UI.

**Patterns:**

- **DCC Decoding:** Try/catch on sprite load; log failure + continue with next weapon (`tools/generate_sprites.py` lines 403-408)
- **File Not Found:** Return `None` from find/load functions; skip generation step (`tools/generate_sprites.py` lines 401-409)
- **Missing Map:** Fall back to grid background if map load fails (`demo/main.js` lines 77-108, 111-123)
- **Texture Load Failure:** Catch async load error, show console warning, mark as non-fatal

## Cross-Cutting Concerns

**Logging:**
- Python: `print()` statements for batch operations and errors
- JavaScript: `console.log()` / `console.error()` for debug and failures

**Validation:**
- DCC: Signature check (0x74 marker) at file start
- DS1: Version check determines header layout
- DT1: Format flag (isometric vs RLE) per block
- Client: Animation existence check before playback

**Coordination:**
- COF (Composition) files drive layer ordering and weapon class per-layer (not global)
- Palette applied uniformly within a character/weapon combo
- Direction index mapping: `DIR_MAP` in client (D2 standard: 0-7 map to S/SW/W/NW/N/NE/E/SE)
- Frame timing: FPS lookup from metadata speed value or defaults table

---

*Architecture analysis: 2026-03-01*
