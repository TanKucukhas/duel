# Codebase Concerns

**Analysis Date:** 2026-03-01

## Tech Debt

**Large Image Assets in Git:**
- Issue: Four 15MB PNG map renders committed to repository (`townN1.png`, `townE1.png`, `townS1.png`, `townW1.png`)
- Files: `demo/assets/maps/act1_town/*.png`
- Impact: Bloats repo size, slow clones, unnecessary bandwidth for distributors
- Fix approach: Move map renders to `.gitignore`, generate on-demand with `tools/render_map.py --act1-town`, or use git-lfs for binary assets

**Inconsistent Error Recovery in Character Loading:**
- Issue: Animation loading silently continues if a direction animation is missing (e.g., `animations.attack1` check at line 299 uses fallback to `attack2`, but other animations assume they exist)
- Files: `demo/main.js` (lines 298-315)
- Impact: Silent failures could result in undefined animations, crashes when accessing undefined properties
- Fix approach: Validate all required animations exist at load time, provide visual feedback when animations are incomplete

**Unchecked Array Bounds in DCC Decoder:**
- Issue: `BitReader.read_bits()` doesn't validate final bit_pos against data length after reading
- Files: `tools/dcc_decoder.py` (lines 28-39), specifically when `stream.copy().offset_bits()` extends past data boundary
- Impact: Silent data corruption or incorrect palette remapping, corrupted frame data when bit stream extends beyond EOF
- Fix approach: Add bounds check in `read_bits()` to return 0 and log warning if reading past EOF, validate total bit stream size before decoding

**Map Coordinate Calculation Lacks Validation:**
- Issue: `render_map.py` calculates output buffer size based on DS1 width/height but doesn't validate that all referenced DT1 tiles are found
- Files: `tools/render_map.py` (lines 176-191), tile rendering fallback returns silently on missing tiles (lines 209-210)
- Impact: Map renders holes/missing tiles without visual indication or error reporting to user
- Fix approach: Collect missing tile statistics and warn user of coverage gaps before rendering

**Potential Array Index Out of Bounds in Pixel Rendering:**
- Issue: While bounds checks exist (e.g., line 132 in `render_map.py`), the palette lookup at line 133 could fail if `pi` > 255
- Files: `tools/render_map.py` (line 133: `r, g, b = palette[pi]`)
- Impact: IndexError if corrupted palette index > 255, crashes render process
- Fix approach: Clamp `pi = min(pi, 255)` before palette lookup, or validate during DCC/DT1 decoding

## Known Bugs

**Manifest Fetch Silently Fails Without Fallback:**
- Symptoms: Demo shows no character buttons if `manifest.json` is missing or network unavailable
- Files: `demo/main.js` (lines 70-75)
- Trigger: Missing `assets/sprites/manifest.json` file or offline mode
- Workaround: Ensure manifest exists; in offline mode, demo becomes unusable
- Fix approach: Provide static fallback manifest or hardcoded character list

**Map Loading Fails Silently with Grid Fallback:**
- Symptoms: Fallback grid renders when Act 1 Town manifest not found, but character moves off map into empty space with no bounds
- Files: `demo/main.js` (lines 78-109, fallback at lines 106-123)
- Trigger: Missing `assets/maps/act1_town/manifest.json` during demo startup
- Workaround: User can still interact with character but grid is infinite
- Fix approach: Validate required assets exist at startup, show warning overlay if critical assets missing

## Performance Bottlenecks

**Memory Explosion from Large Isometric Map Renders:**
- Problem: A single 7840x4212 map creates 132MB bytearray (7840 * 4212 * 4 bytes RGBA)
- Files: `tools/render_map.py` (line 194: `bytearray(out_w * out_h * 4)`)
- Cause: Full map rendered to raw pixel buffer before PIL conversion
- Improvement path: Stream render to image in tiles, or render directly to PIL Image without intermediate bytearray

**Unoptimized Pixel-by-Pixel Rendering in Python:**
- Problem: Triple nested loops in `composite_layers()` and tile rendering are pure Python, very slow for large maps
- Files: `tools/generate_sprites.py` (lines 261-267), `tools/render_map.py` (lines 123-149)
- Cause: NumPy not used for vectorized operations, PIL pixel access via `.load()` is slow
- Improvement path: Use NumPy arrays for composite operations, cache palette as NumPy array for vectorized lookups

**Synchronous File I/O in Sprite Generation:**
- Problem: `generate_sprites.py` loads all DCC frames sequentially, no parallelization for character/weapon combinations
- Files: `tools/generate_sprites.py` (main loop, lines 450+)
- Cause: Single-threaded file reading for 7 characters × 13 weapons × 8+ animations
- Improvement path: Use multiprocessing.Pool to decode multiple CCFs in parallel

**Inefficient Texture Memory in PixiJS Demo:**
- Problem: Each animation frame loaded as individual PIXI.Texture, no atlasing for better batching
- Files: `demo/main.js` (lines 200-211: individual Rectangle textures for each frame)
- Cause: Manual texture creation from spritesheet leads to draw call overhead
- Improvement path: Pre-compute texture region data, use single draw call per animation

## Fragile Areas

**DCC Decoder's Complex Bitstream Parsing:**
- Files: `tools/dcc_decoder.py` (entire file, 514 lines)
- Why fragile: Multi-level BitReader offsets (`stream.copy().offset_bits(...)`) make bit position tracking error-prone; buffer overruns silent
- Safe modification: Add comprehensive unit tests for each bitstream type, validate bit counts at each offset stage, add asserts for expected bit stream sizes
- Test coverage: No test files exist; decoder only tested via `generate_sprites.py` integration

**DS1 Layer Reading with Version-Dependent Formats:**
- Files: `tools/ds1_decoder.py` (lines 149-221)
- Why fragile: Version < 4 uses different layer order; version >= 4 has interleaved walls/orient; multiple conditional branches make edge cases easy to miss
- Safe modification: Create version-specific layer readers, add validation that offset position matches expected next layer start
- Test coverage: No unit tests for version parsing

**COF Priority Table Parsing:**
- Files: `tools/generate_sprites.py` (lines 160-180 in COF parsing)
- Why fragile: COF file format has complex priority lookup based on frame/direction; fallback silently switches to wrong layer order if parsing fails
- Safe modification: Validate COF header magic bytes, add bounds checks on priority table indexing
- Test coverage: No tests for corrupt/malformed COF files

**Memory Leaks in Character Loading Loop:**
- Files: `demo/main.js` (lines 184-191: texture destruction)
- Why fragile: Old textures destroyed but PIXI.Assets cache may retain references; no manual garbage collection trigger
- Safe modification: Clear PIXI.Assets cache explicitly, use WeakMap for animation storage
- Test coverage: No memory profiling or leak detection

## Scaling Limits

**Map Rendering Limited by Available RAM:**
- Current capacity: Maps up to ~8000x4000px fit in RAM (132MB for single map)
- Limit: Very large maps (e.g., 20000x20000) would require 6.4GB just for pixel buffer
- Scaling path: Implement tiled rendering (divide map into 1024x1024 chunks), render to disk iteratively

**Character Animation Memory:**
- Current capacity: Single character+weapon ~50-100MB (all 8 directions × 30+ frames)
- Limit: Loading all 7 characters × 13 weapons × 8 directions = ~7GB peak memory for full sprite cache
- Scaling path: Implement on-demand loading per weapon, use texture streaming, reduce spritesheet resolution for unused animations

**WebGL Texture Memory in Browser:**
- Current capacity: PixiJS can handle ~512MB textures on high-end devices (limited by GPU VRAM)
- Limit: Full animated character set exceeds VRAM on mobile/integrated GPUs
- Scaling path: Implement dynamic texture paging, reduce animation quality for constrained devices, progressive loading with lower-res fallbacks

## Fragile Dependencies

**struct.unpack_from() Unsafe on Truncated Files:**
- Risk: No length validation before unpacking; truncated files cause struct.error
- Files: All decoders (`dcc_decoder.py`, `dt1_decoder.py`, `ds1_decoder.py`, `render_map.py`)
- Current mitigation: Individual checks scattered (e.g., `if offset + 4 > len(data)`) but inconsistent
- Recommendations: Wrap all `struct.unpack_from()` calls with bounds-checked wrapper, define minimum file sizes for validation

**PIL Image Creation Without Size Validation:**
- Risk: `Image.new()` or `Image.frombytes()` with invalid dimensions cause memory allocation failure or corruption
- Files: `tools/generate_sprites.py` (line 258, 317), `tools/render_map.py` (line 317)
- Current mitigation: Dimensions calculated from layer data, no explicit bounds
- Recommendations: Add size sanity checks (max 20000x20000), validate width/height > 0 before Image creation

## Security Considerations

**No Validation of DT1/DS1 Path Traversal:**
- Risk: Path from DS1 file (e.g., `../../malicious.dt1`) could load files outside expected tile directory
- Files: `tools/render_map.py` (line 56-87: `resolve_dt1_path()`)
- Current mitigation: Path normalized to forward slashes, search limited to TILES_BASE
- Recommendations: Use `pathlib.Path.resolve()` and verify result starts with TILES_BASE, reject `..` components

**Unsafe File Read of User-Provided Paths:**
- Risk: Command-line tool accepts arbitrary file paths without validation
- Files: `tools/render_map.py` (line 389: `ds1_path = sys.argv[1]`)
- Current mitigation: None
- Recommendations: Whitelist allowed directories, validate file extensions, check file permissions before reading

**Palette Index Out of Bounds (No Signed Check):**
- Risk: Malformed DCC files could specify palette indices > 255, causing IndexError in rendering
- Files: All decoders assume palette indices fit in 256 entries
- Current mitigation: None explicit in rendering code
- Recommendations: Clamp palette indices during decoding, add assertions in palette lookup

## Test Coverage Gaps

**No Unit Tests for Decoder Modules:**
- What's not tested: DCC bitstream parsing, DT1 isometric/RLE decoding, DS1 layer interleaving, COF priority tables
- Files: `tools/dcc_decoder.py` (514 lines), `tools/dt1_decoder.py` (286 lines), `tools/ds1_decoder.py` (290 lines)
- Risk: Silent corruption in decoded data, version-specific bugs, truncated file handling untested
- Priority: High — decoders are core to entire pipeline

**No Tests for Map Renderer:**
- What's not tested: Tile selection logic, z-order correctness for walls/shadows/roofs, coordinate transformations, out-of-bounds rendering
- Files: `tools/render_map.py` (391 lines)
- Risk: Incorrect rendering goes unnoticed (visual inspection only), performance regressions on large maps
- Priority: High — produces final asset

**No Tests for Sprite Generation:**
- What's not tested: COF parsing, layer compositing, spritesheet packing, animation metadata export
- Files: `tools/generate_sprites.py` (624 lines)
- Risk: Character animations with wrong frame counts or incorrect layer order
- Priority: High — blocks demo if broken

**No Browser Tests for Demo:**
- What's not tested: Asset loading, animation playback, camera/zoom behavior, keyboard input handling
- Files: `demo/main.js` (487 lines)
- Risk: Missing assets or broken animations only discovered during manual testing
- Priority: Medium — catches UX issues late

## Missing Critical Features

**No Error UI Feedback in Browser Demo:**
- Problem: Loading failures (missing manifest, map, character assets) silently fail with console errors only
- Blocks: User can't diagnose why demo is broken, no recovery path
- Fix approach: Add error overlay div, report missing assets with "assets/sprites/manifest.json not found" messages

**No Progress Reporting for Large File Loads:**
- Problem: Loading 15MB map PNG hangs UI for seconds with no feedback
- Blocks: Users think demo crashed when loading large character/map assets
- Fix approach: Implement fetch with progress events, show loading percentage

**No Fallback Palettes for Missing Act Palettes:**
- Problem: If ACT2/ACT3+ palette missing, render_map.py falls back to ACT1, map colors incorrect
- Blocks: Can't reliably render non-Act1 maps
- Fix approach: Validate palette before use, hardcode fallback 256-color Diablo 2 palette

**No Validation of D2 File Formats:**
- Problem: Corrupt DCC/DT1/DS1 files cause cryptic unhandled exceptions
- Blocks: No user-friendly error messages, development workflow hindered by debug-by-exception
- Fix approach: Add file format validators with descriptive error messages

---

*Concerns audit: 2026-03-01*
