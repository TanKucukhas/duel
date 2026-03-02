# Testing Patterns

**Analysis Date:** 2025-03-01

## Test Framework

**Status:** No automated testing framework configured

**Current Approach:**
- Manual testing through interactive UI/CLI
- No test runner (Jest, Vitest, pytest, unittest) configured
- No test files or test structure found
- No test configuration files (.eslintrc, jest.config.js, pytest.ini, etc.)

**Run Commands:**
- JavaScript demo: Run `demo/index.html` in a browser (no test script)
- Python tools: Run directly with `python3 script.py [args]` and observe stdout/file output

## Manual Testing Approach

**JavaScript - Interactive Testing:**
- Demo viewable at `/Users/tankucukhas/workspace/diablo2-duel/demo/index.html`
- PixiJS viewer allows manual testing of:
  - Character selection (buttons 1-7 for quick select, or click buttons)
  - Animation playback (Space=attack, Q=cast, E=kick, F=skill1, X=gethit, Z=death, B=block, R=attack2, T=throw)
  - Movement (WASD/Arrow keys, Shift for run)
  - Zoom (mouse wheel)
- Console logging available in browser DevTools for diagnostics

**Python - CLI Testing:**
- `generate_sprites.py`: Processes DCC/COF files and outputs PNG spritesheets + JSON atlases
  - Usage: `python3 generate_sprites.py BA HTH LIT` (single character+weapon)
  - Usage: `python3 generate_sprites.py --batch` (all characters and weapons)
  - Outputs validation: Visual inspection of PNG files and atlas JSON structure
- `render_map.py`: Loads DS1/DT1 files and composites map to PNG
  - Outputs validation: Visual inspection of rendered PNG
- `dcc_decoder.py`: Decodes sprite files
  - Testing: Run via import by `generate_sprites.py`
- `ds1_decoder.py`: Parses map layout files
  - Testing: Run via import by `render_map.py`
- `dt1_decoder.py`: Decodes tile graphics
  - Testing: Run via import by `render_map.py`

## Validation Approach

**JavaScript:**
- Runtime validation via browser console (check for errors/warnings)
- Visual validation of sprite rendering and animation timing
- Input handling verification (keyboard/mouse responsiveness)
- Debug output in bottom-left corner shows state: animation, direction, frame count, FPS

**Python:**
- File I/O validation: Check if decoded files are read without exceptions
- Output validation: Verify PNG files are generated and have correct dimensions
- Data structure validation: Confirm dataclass fields populate correctly from binary data
- Palette application: Visual inspection of rendered colors in output images

## Data Validation Patterns

**JavaScript (`main.js`):**
- Early returns for missing data: `if (!animations[name]) return`
- Guard clauses for manifest data: `if (!manifest || !manifest.characters[charCode]) return`
- Texture cleanup on reload: Old textures explicitly destroyed before loading new ones
- Safe property access: `animations[name]?.meta` (optional chaining)

**Python:**
- Exception on invalid file signatures:
  ```python
  sig = data[0]
  if sig != 0x74:
      raise ValueError(f"Invalid DCC signature: 0x{sig:02x}")
  ```
- Boundary checks before buffer access:
  ```python
  if byte_idx < len(self.data):
      result |= ((self.data[byte_idx] >> bit_idx) & 1) << i
  ```
- Type-safe dataclass instantiation with defaults:
  ```python
  @dataclass
  class DCCFrame:
      width: int = 0
      height: int = 0
  ```

## Error Handling Patterns

**JavaScript:**
- try/catch for async operations (fetch, JSON parsing)
- Fallback behavior on error: `catch (e) { _createFallbackGrid() }`
- Console warnings for non-critical failures: `console.warn('No map available...')`
- State consistency: Animation state reset on reload

**Python:**
- ValueError raised for malformed files
- Graceful file resolution fallback: Try exact path, then case-insensitive search
- Optional return for missing dependencies: Returns empty string if file not found
- Safe struct unpacking with offset validation

## Missing Coverage Areas

**High Priority (Critical Path):**
- `main.js` animation frame selection: No validation that frame indices stay in bounds
  - Risk: Array out-of-bounds on corrupted sprite data
  - Pattern found: `currentFrame = Math.min(currentFrame, anim.meta.framesPerDirection - 1)` provides some safety
- Sprite loading error recovery: If texture load fails mid-character-swap, state could be inconsistent
- Map boundary clamping: Character position clamped, but no test for edge cases

**Medium Priority:**
- DCC frame decompression: Complex bit-level operations without unit tests
  - Files: `dcc_decoder.py` — BitReader class with complex bit manipulation
  - Pattern: Binary protocol decoding, no inline validation of intermediate states
- DT1 tile rendering: Three-pass rendering pipeline (wall, floor, shadow) — order-dependent
  - Files: `dt1_decoder.py`, `render_map.py`
  - Risk: Rendering artifacts if passes applied in wrong order
- DS1 orientation mapping: Lookup table with 25 possible values, no bounds checking
  - Files: `ds1_decoder.py` — `DIR_LOOKUP` array
  - Risk: Index out-of-bounds on corrupted map data

**Low Priority:**
- Palette loading fallback: If ACT-specific palette missing, falls back to ACT1
  - Files: `render_map.py` — `load_palette()`
  - Risk: Color misrepresentation in non-ACT1 areas

## Testing Recommendations

**For Future Test Automation:**

**JavaScript (if adding Jest/Vitest):**
```javascript
// Pattern: Test animation state machine
describe('Animation', () => {
  test('setAnimation() changes currentAnim', () => {
    setAnimation('walk');
    expect(currentAnim).toBe('walk');
  });

  test('playOneShot() executes callback on completion', (done) => {
    playOneShot('attack1', () => {
      expect(oneShotAnim).toBeNull();
      done();
    });
  });
});

// Pattern: Test direction input mapping
describe('Movement', () => {
  test('getInputDirection() returns correct 8-way direction', () => {
    keys['w'] = true;
    keys['d'] = true;
    expect(getInputDirection()).toBe('NE');
  });
});
```

**Python (if adding pytest):**
```python
# Pattern: Test binary decoding
def test_decode_dcc_valid_signature():
    # Create minimal valid DCC data with signature 0x74
    data = bytes([0x74, 0, 0, ...])
    dcc = decode_dcc(data)
    assert dcc.version == 0

def test_decode_dcc_invalid_signature():
    data = bytes([0xFF, 0, 0, ...])
    with pytest.raises(ValueError, match="Invalid DCC signature"):
        decode_dcc(data)

# Pattern: Test bit reading
def test_bit_reader():
    data = bytes([0b10101010, 0b01010101])
    reader = BitReader(data)
    assert reader.read_bits(1) == 0
    assert reader.read_bits(1) == 1
    assert reader.read_bits(4) == 0b1010
```

## Current Test Coverage Status

| Area | Coverage | Status |
|------|----------|--------|
| Animation state machine | None | Untested - core gameplay logic |
| Sprite loading & caching | Partial | Manual visual testing only |
| Character/weapon selection | Manual | Interactive testing only |
| DCC decoding | None | Unit tested via output inspection |
| DS1 parsing | None | Integration tested via map render |
| DT1 rendering | None | Integration tested via visual inspection |
| Input handling | Manual | Keyboard/mouse responsiveness only |
| Zoom/camera | Manual | Visual inspection only |
| Error recovery | Partial | Fallback grid renders on map load fail |

---

*Testing analysis: 2025-03-01*
