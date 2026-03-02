# External Integrations

**Analysis Date:** 2026-03-01

## APIs & External Services

**Content Delivery Network:**
- jsdelivr.net (PixiJS v8.6.6 CDN)
  - Serves: `https://cdn.jsdelivr.net/npm/pixi.js@8.6.6/dist/pixi.min.js`
  - No authentication required
  - No fallback mechanism (application is offline-capable if assets are pre-cached)

## Data Storage

**Databases:**
- None - No runtime database or persistent storage
- All data is static file-based

**File Storage:**
- **Local filesystem** (development & asset generation)
  - `Diablo2_all/extracted/` - Extracted Diablo 2 game data
  - `demo/assets/` - Generated static assets (PNG, JSON)

- **HTTP static file serving** (demo)
  - Assets served as-is from `demo/` directory
  - Requires CORS headers if accessed from different domain
  - No API endpoint for asset retrieval

**Caching:**
- Browser HTTP caching via standard headers
- No application-level caching mechanism
- Asset versioning via query params: `?v={timestamp}` in HTML/JS (cache busting)

## Authentication & Identity

**Auth Provider:**
- None - Application is stateless and public
- No user accounts, login, or authorization required
- Demo is publicly accessible

## Monitoring & Observability

**Error Tracking:**
- None configured
- Browser console logging for debugging:
  - `console.log()` for sprite loading status
  - `console.error()` for file load failures
  - `console.warn()` for fallback grid rendering

**Logs:**
- Client-side console output only
- No server-side logging
- No analytics or telemetry

**Debug Output:**
- On-screen FPS, animation state, zoom level display in bottom-left corner
- Real-time animation frame counter in debug panel

## CI/CD & Deployment

**Hosting:**
- Static file hosting only (no server backend)
- Can be deployed to:
  - GitHub Pages
  - Netlify
  - Vercel
  - Any static HTTP server

**CI Pipeline:**
- None configured in repo
- Asset generation is manual:
  ```bash
  # Python tools must be run locally
  python3 tools/generate_sprites.py --batch
  python3 tools/render_map.py
  ```

## Environment Configuration

**Required env vars:**
- None - Application has no configuration

**Required for asset generation:**
- Python 3.6+ with Pillow installed
- `Diablo2_all/extracted/` directory populated with decompressed game data
- File system access to write `demo/assets/`

**Secrets location:**
- N/A - No secrets used (public demo)

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None

## Asset Dependencies

**JavaScript:**
- PixiJS 8.6.6 (CDN only, no fallback)
  - Used for: Sprite rendering, texture management, camera system, game loop (`app.ticker`)

**Python Tools:**
- Pillow 9.1.0 (via `requirements.txt` in `pcx-to-spritesheet/`)
  - Used by: `tools/generate_sprites.py`, `tools/render_map.py`
  - Image format: PNG (8-bit indexed) with palette conversion

## Data Sources

**Game Data Extraction:**
- Original source: Diablo 2 / Diablo 2: Resurrected ISOs
- Extraction tool: MPQExtractor (separate project, pre-run)
- Location: `Diablo2_all/extracted/data/data/global/`
- Directories:
  - `CHARS/` - Character sprite files (DCC + COF)
  - `palette/` - Color palettes (PAL files)
  - `tiles/` - Tile graphics (DT1 files)

**Map Data:**
- DS1 files located in `Diablo2_all/extracted/data/data/global/LEVELS/L1/` (Act 1)
- Referenced DT1 tiles resolved from extracted tiles directory

## Asset Pipeline Configuration

**Python Tool Paths (hardcoded in `tools/`):**
- `BASE_DIR` - Project root
- `DATA_DIR = BASE_DIR / "Diablo2_all" / "extracted" / "data" / "data" / "global"`
- `CHARS_DIR = DATA_DIR / "CHARS"`
- `PALETTE_DIR = DATA_DIR / "palette"`
- `OUTPUT_DIR = BASE_DIR / "demo" / "assets" / "sprites"`
- `TILES_BASE = BASE_DIR / "Diablo2_all" / "extracted" / "tiles" / "data" / "global" / "tiles"`
- `PALETTE_BASE = BASE_DIR / "Diablo2_all" / "extracted" / "data" / "data" / "global" / "palette"`

**Asset Manifest:**
- `demo/assets/sprites/manifest.json` - Lists all character/weapon combinations and available animations
- `demo/assets/maps/act1_town/manifest.json` - Lists map stamps with dimensions and file references

## Client-Server Communication

**Demo Mode:**
- Pure client-side rendering
- Assets loaded via HTTP GET requests
- No API calls or network latency concerns

**Asset Loading:**
```javascript
// From demo/main.js
fetch(`assets/sprites/manifest.json?v=${CB}`)  // Cache-buster
fetch(`assets/maps/act1_town/manifest.json?v=${CB}`)
PIXI.Assets.load(`${basePath}${meta.file}?v=${CB}`)
```

## Cross-Origin & CORS

**CORS Requirements:**
- Not applicable (single-origin static assets)
- If served from different domain, standard CORS headers needed
- No preflight requests required (simple GET requests)

## Rate Limiting & Quotas

**CDN (PixiJS):**
- No rate limiting observed
- jsdelivr.net is a public CDN with generous limits

**Asset Loading:**
- No rate limiting
- Sequential loading (one character at a time)
- Total asset size: ~50-100 MB for all characters (PNG spritesheets)

---

*Integration audit: 2026-03-01*
