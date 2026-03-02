# Coding Conventions

**Analysis Date:** 2025-03-01

## Naming Patterns

**Files:**
- JavaScript/TypeScript: camelCase (e.g., `main.js`)
- Python: snake_case (e.g., `dcc_decoder.py`, `generate_sprites.py`)
- HTML: lowercase with hyphens (e.g., `index.html`)
- Directories: lowercase with underscores for Python packages (e.g., `/tools/`)

**Functions:**
- JavaScript: camelCase (e.g., `selectCharacter()`, `loadMap()`, `getAnimFPS()`)
- Python: snake_case (e.g., `decode_dcc()`, `load_palette()`, `resolve_dt1_path()`)

**Variables:**
- JavaScript: camelCase for all variables and constants in function scope (e.g., `charWorldX`, `currentDir`, `animTimer`)
- Python: snake_case for variables (e.g., `bit_pos`, `num_tiles`, `palette_entries`)
- Python: UPPER_CASE for module-level constants (e.g., `CRAZY_BIT_TABLE`, `TILE_WIDTH`, `TILE_HEIGHT`)

**Types & Classes:**
- Python dataclasses: PascalCase (e.g., `DCCFile`, `DS1Cell`, `DT1Tile`, `BitReader`)
- JavaScript object keys: camelCase (e.g., `DIR_MAP`, `DIR_VECTORS` for data structures)

## Code Style

**Formatting:**
- JavaScript: Minified inline styles for HTML attributes, no external formatters configured
- Python: 4-space indentation, PEP 8 style observed
- Line wrapping: JavaScript uses descriptive chaining and early returns; Python uses multi-line function signatures

**Linting:**
- No .eslintrc or prettier configuration found in root
- No Python linting config (no .flake8, pyproject.toml)
- Code appears hand-written without automated linting, though styles are consistent

**Commenting Style:**
- JavaScript: Sparse comments, using section markers with dashes for organization
  - Example: `// ── Animation State ──` (decorative section headers)
  - Console logging used for diagnostics: `console.log()`, `console.error()`, `console.warn()`
- Python: Module-level docstrings for all files
  - Example: `"""Diablo 2 DCC file decoder.\nPorted from OpenDiablo2 (Go) to Python.\n"""`
  - Function docstrings: `"""Decode a DCC file from raw bytes."""`

## Import Organization

**JavaScript:**
- Single file (`main.js`) with inline code, no imports
- External dependencies via CDN: `<script src="https://cdn.jsdelivr.net/npm/pixi.js@8.6.6/dist/pixi.min.js"></script>`
- HTML source files added via `<script src="main.js?v=5"></script>` with cache-busting version param

**Python:**
- Standard library imports first: `import struct`, `import os`, `import sys`, `from pathlib import Path`
- Third-party imports: `from PIL import Image`
- Local imports: `from dcc_decoder import decode_dcc`, `from dt1_decoder import decode_dt1`
- Example from `render_map.py`:
  ```python
  import os
  import sys
  import json
  import struct
  from pathlib import Path
  from PIL import Image

  sys.path.insert(0, os.path.dirname(__file__))
  from dt1_decoder import decode_dt1, DT1File, DT1Tile, build_tile_index, select_tile
  from ds1_decoder import (
      decode_ds1, DS1File, DS1Cell, DS1OrientCell,
      get_dt1_key_for_floor, get_dt1_key_for_shadow, get_dt1_key_for_wall,
  )
  ```

## Error Handling

**JavaScript:**
- try/catch blocks for async operations
- Graceful fallbacks: Map fails to load → creates fallback grid
- Console warnings for non-fatal issues: `console.warn('No map available, using grid background:', e.message)`
- Early returns for invalid states: `if (!animations[name]) return`
- Example from `main.js`:
  ```javascript
  try {
    const resp = await fetch(`assets/maps/act1_town/manifest.json?v=${CB}`);
    const mapManifest = await resp.json();
    // ... processing
  } catch (e) {
    console.warn('No map available, using grid background:', e.message);
    _createFallbackGrid();
  }
  ```

**Python:**
- Raises exceptions for invalid file formats: `raise ValueError(f"Invalid DCC signature: 0x{sig:02x}")`
- Boundary checking before buffer access: `if byte_idx < len(self.data)`
- Fallback paths for file resolution with case-insensitive lookup
- Example from `dcc_decoder.py`:
  ```python
  sig = data[0]
  if sig != 0x74:
      raise ValueError(f"Invalid DCC signature: 0x{sig:02x}")
  ```

## Logging

**Framework:** Console for JavaScript, print-style for Python

**JavaScript Patterns:**
- Startup info: `console.log(\`Map loaded: ${name} (${mapWidth}x${mapHeight})\`)`
- Errors: `console.error(\`Failed to load ${charCode}/${weapon}:\`, e)`
- Warnings: `console.warn('No map available, using grid background:', e.message)`
- Info load: `console.log(\`Loaded ${charCode}/${weapon}:\`, Object.keys(animations))`

**Python Patterns:**
- Debug/diagnostic output only (no structured logging found)
- File I/O logging: `print(f'Loading {path}')`
- Status output via print statements

## Function Design

**Size:** Functions range from 5 lines (simple helpers) to 40+ lines (complex state management)

**Parameters:**
- JavaScript: Most functions accept 1-2 parameters (charCode, weapon, name)
- Python: Functions follow struct unpacking pattern with named parameters in dataclass constructors
- Avoid excessive global dependencies within functions

**Return Values:**
- JavaScript: Void functions (side effects on global state), some return booleans/strings
- Python: Decode functions return structured dataclass instances (`DCCFile`, `DS1File`, `DT1File`)

**Patterns Observed:**
- Early return on invalid inputs: `if (!manifest || !manifest.characters[charCode]) return`
- State mutation: Animation state updated via assignment to module-level variables
- Callbacks for async operations: `playOneShot('death', () => { /* callback */ })`

## Module Design

**Exports:**
- Python: Top-level functions are implicit exports (no __all__ defined)
  - Main entry: `decode_dcc(data: bytes) -> DCCFile`
  - Helper functions: `_decode_direction()`, `_parse_tile_header()` (prefixed with underscore for private)
- JavaScript: Single monolithic file with module-level IIFE wrapping all code

**Naming Conventions for Internal Helpers:**
- Python: Underscore prefix for private/internal functions: `_decode_direction()`, `_parse_tile_header()`, `_createFallbackGrid()`
- JavaScript: Mixed approach — some prefixed with underscore (`_createFallbackGrid()`), most are module-scoped

## Data Structure Patterns

**JavaScript:**
- Object literals for mapping: `DIR_MAP = { S: 4, SW: 0, W: 5, ... }`
- Object literals for constants: `ANIM_MODES = { "NU": "neutral", "WL": "walk", ... }`
- Arrays for ordered data: `DIR_VECTORS = [{ x, y }, ...]` indexed by direction

**Python:**
- Dataclasses with field defaults: `@dataclass` decorator for all structured data
  - Example: `@dataclass class DCCFrame: width: int = 0; height: int = 0; ...`
- Dictionaries for ID lookups: `palette_entries: list = field(default_factory=lambda: [0] * 256)`
- Lists for sequential data: `frames: list = field(default_factory=list)`
- Constants as module-level variables or as class attributes

## Code Organization

**JavaScript (`main.js`):**
- IIFE wrapper: `(async () => { ... })()`
- Section organization with comment headers: `// ── D2 Direction Mapping ──`, `// ── PixiJS Setup ──`
- State variables grouped by domain: animation state together, map state together, input state together
- Event listeners registered at load time
- Game loop implemented via `app.ticker.add()`

**Python Tool Files:**
- Module docstring at top explaining purpose
- Constants defined before class definitions
- Dataclasses defined before functions
- Helper functions prefixed with underscore
- Main entry point functions (e.g., `decode_dcc()`) at module level

---

*Convention analysis: 2025-03-01*
