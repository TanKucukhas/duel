(async () => {
  // ── D2 Direction Mapping ──
  const DIR_MAP = {
    S: 4, SW: 0, W: 5, NW: 1, N: 6, NE: 2, E: 7, SE: 3,
  };
  const DIR_VECTORS = {
    S:  { x:  0, y:  1 },
    SW: { x: -1, y:  1 },
    W:  { x: -1, y:  0 },
    NW: { x: -1, y: -1 },
    N:  { x:  0, y: -1 },
    NE: { x:  1, y: -1 },
    E:  { x:  1, y:  0 },
    SE: { x:  1, y:  1 },
  };

  const SCALE = 1.25;
  const MOVE_SPEED = 3;

  // ── PixiJS Setup ──
  const app = new PIXI.Application();
  await app.init({
    resizeTo: window,
    backgroundColor: 0x0a0a12,
    antialias: false,
    resolution: window.devicePixelRatio || 1,
    autoDensity: true,
  });
  document.body.appendChild(app.canvas);

  // ── World Container (camera follows character) ──
  const world = new PIXI.Container();
  app.stage.addChild(world);

  // ── Map Layer ──
  const mapContainer = new PIXI.Container();
  world.addChild(mapContainer);

  // ── Character Sprite ──
  const character = new PIXI.Sprite(PIXI.Texture.EMPTY);
  character.scale.set(SCALE);
  character.zIndex = 10;
  world.addChild(character);

  // World position of the character (in map pixels)
  let charWorldX = 0;
  let charWorldY = 0;

  // ── Animation State ──
  let animations = {};
  let currentAnim = 'neutral';
  let currentDir = 'S';
  let currentFrame = 0;
  let animTimer = 0;
  let isMoving = false;
  let isRunning = false;
  let oneShotAnim = null;
  let oneShotCallback = null;
  let currentCharCode = null;
  let currentWeapon = null;

  // ── Map state ──
  let mapLoaded = false;
  let mapWidth = 0;
  let mapHeight = 0;

  // ── Load Manifest ──
  const CB = Date.now();
  let manifest = null;
  try {
    const resp = await fetch(`assets/sprites/manifest.json?v=${CB}`);
    manifest = await resp.json();
  } catch (e) {
    console.error('Failed to load manifest:', e);
  }

  // ── Load Map ──
  async function loadMap() {
    try {
      const resp = await fetch(`assets/maps/act1_town/manifest.json?v=${CB}`);
      const mapManifest = await resp.json();

      // Load the main town stamp (townN1 is the north quarter)
      const stamps = Object.entries(mapManifest.stamps);
      if (stamps.length === 0) return;

      // Load the first stamp as the map
      const [name, info] = stamps[0];
      const tex = await PIXI.Assets.load(`assets/maps/act1_town/${info.file}?v=${CB}`);
      tex.source.scaleMode = 'nearest';

      const mapSprite = new PIXI.Sprite(tex);
      mapSprite.scale.set(1);
      mapContainer.addChild(mapSprite);

      mapWidth = info.width;
      mapHeight = info.height;
      mapLoaded = true;

      // Place character near the center of the map
      charWorldX = mapWidth / 2;
      charWorldY = mapHeight / 2;

      console.log(`Map loaded: ${name} (${mapWidth}x${mapHeight})`);
    } catch (e) {
      console.warn('No map available, using grid background:', e.message);
      _createFallbackGrid();
    }
  }

  function _createFallbackGrid() {
    const ground = new PIXI.Graphics();
    ground.setStrokeStyle({ width: 1, color: 0x1a1a2e });
    const size = 4000;
    for (let x = -size; x <= size; x += 50) ground.moveTo(x, -size).lineTo(x, size);
    for (let y = -size; y <= size; y += 50) ground.moveTo(-size, y).lineTo(size, y);
    ground.stroke();
    mapContainer.addChild(ground);
    mapWidth = size * 2;
    mapHeight = size * 2;
    charWorldX = 0;
    charWorldY = 0;
  }

  await loadMap();

  // ── Build UI ──
  const charButtonsEl = document.getElementById('char-buttons');
  const weaponSelectEl = document.getElementById('weapon-select');
  const loadingEl = document.getElementById('loading');

  const CHAR_NAMES = {
    BA: 'Barbarian', AM: 'Amazon', NE: 'Necromancer',
    PA: 'Paladin', SO: 'Sorceress', DZ: 'Druid', AI: 'Assassin',
  };

  if (manifest) {
    for (const charCode of Object.keys(manifest.characters)) {
      const btn = document.createElement('button');
      btn.className = 'char-btn';
      btn.textContent = CHAR_NAMES[charCode] || charCode;
      btn.dataset.char = charCode;
      btn.addEventListener('click', () => selectCharacter(charCode));
      charButtonsEl.appendChild(btn);
    }
  }

  function updateWeaponDropdown(charCode) {
    weaponSelectEl.innerHTML = '';
    if (!manifest || !manifest.characters[charCode]) return;

    const weapons = manifest.characters[charCode].weapons;
    for (const [code, info] of Object.entries(weapons)) {
      const opt = document.createElement('option');
      opt.value = code;
      opt.textContent = `${info.name} (${code})`;
      weaponSelectEl.appendChild(opt);
    }

    if (weapons['HTH']) {
      weaponSelectEl.value = 'HTH';
    }
  }

  weaponSelectEl.addEventListener('change', () => {
    loadCharacter(currentCharCode, weaponSelectEl.value);
  });

  // ── Load Character Animations ──
  async function loadCharacter(charCode, weapon) {
    if (!manifest || !manifest.characters[charCode]) return;
    const weaponInfo = manifest.characters[charCode].weapons[weapon];
    if (!weaponInfo) return;

    if (currentCharCode === charCode && currentWeapon === weapon) return;

    loadingEl.style.display = 'inline';

    try {
      const atlasPath = `assets/sprites/${weaponInfo.path}?v=${CB}`;
      const atlasResp = await fetch(atlasPath);
      const atlas = await atlasResp.json();

      // Destroy old textures
      for (const anim of Object.values(animations)) {
        for (const dirFrames of anim.frames) {
          for (const tex of dirFrames) {
            if (tex !== PIXI.Texture.EMPTY) tex.destroy(false);
          }
        }
      }

      const newAnimations = {};
      const basePath = `assets/sprites/${charCode.toLowerCase()}/${weapon}/`;

      for (const [name, meta] of Object.entries(atlas.animations)) {
        const tex = await PIXI.Assets.load(`${basePath}${meta.file}?v=${CB}`);
        tex.source.scaleMode = 'nearest';

        const frames = [];
        for (let dir = 0; dir < meta.directions; dir++) {
          const dirFrames = [];
          for (let f = 0; f < meta.framesPerDirection; f++) {
            const rect = new PIXI.Rectangle(
              f * meta.frameWidth,
              dir * meta.frameHeight,
              meta.frameWidth,
              meta.frameHeight,
            );
            dirFrames.push(new PIXI.Texture({ source: tex.source, frame: rect }));
          }
          frames.push(dirFrames);
        }

        newAnimations[name] = { frames, meta };
      }

      animations = newAnimations;
      currentCharCode = charCode;
      currentWeapon = weapon;

      oneShotAnim = null;
      oneShotCallback = null;
      currentFrame = 0;
      animTimer = 0;

      if (animations.neutral) {
        currentAnim = 'neutral';
      } else {
        currentAnim = Object.keys(animations)[0] || 'neutral';
      }

      console.log(`Loaded ${charCode}/${weapon}:`, Object.keys(animations));
    } catch (e) {
      console.error(`Failed to load ${charCode}/${weapon}:`, e);
    }

    loadingEl.style.display = 'none';
  }

  function selectCharacter(charCode) {
    document.querySelectorAll('.char-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.char === charCode);
    });

    updateWeaponDropdown(charCode);
    loadCharacter(charCode, weaponSelectEl.value);
  }

  // ── Animation Helpers ──
  function setAnimation(name) {
    if (!animations[name]) return;
    if (currentAnim === name && !oneShotAnim) return;
    currentAnim = name;
    currentFrame = 0;
    animTimer = 0;
  }

  function playOneShot(name, callback) {
    if (!animations[name]) return;
    oneShotAnim = name;
    currentAnim = name;
    currentFrame = 0;
    animTimer = 0;
    oneShotCallback = callback || null;
  }

  function getAnimFPS(name) {
    const meta = animations[name]?.meta;
    if (!meta) return 15;
    if (meta.speed > 0) {
      return 25 * meta.speed / 256;
    }
    const defaults = {
      attack1: 18, attack2: 18, block: 12, cast: 16,
      gethit: 12, kick: 18, skill1: 16, death: 12,
      dead: 1, town_walk: 15, town_neutral: 10, throw: 16,
    };
    return defaults[name] || 15;
  }

  // ── Input ──
  const keys = {};
  window.addEventListener('keydown', (e) => {
    const k = e.key.toLowerCase();
    if (!keys[k]) keys[k] = true;

    if (manifest && k >= '1' && k <= '9') {
      const chars = Object.keys(manifest.characters);
      const idx = parseInt(k) - 1;
      if (idx < chars.length) {
        selectCharacter(chars[idx]);
        e.preventDefault();
        return;
      }
    }

    if (k === ' ' && !oneShotAnim) {
      playOneShot(animations.attack1 ? 'attack1' : 'attack2');
      e.preventDefault();
      return;
    }
    if (k === 'q' && !oneShotAnim) {
      playOneShot('cast');
      e.preventDefault();
      return;
    }
    if (k === 'e' && !oneShotAnim) {
      playOneShot('kick');
      e.preventDefault();
      return;
    }
    if (k === 'f' && !oneShotAnim) {
      playOneShot('skill1');
      e.preventDefault();
      return;
    }
    if (k === 'x' && !oneShotAnim) {
      playOneShot('gethit');
      e.preventDefault();
      return;
    }
    if (k === 'b' && !oneShotAnim) {
      playOneShot('block');
      e.preventDefault();
      return;
    }
    if (k === 'r' && !oneShotAnim) {
      playOneShot('attack2');
      e.preventDefault();
      return;
    }
    if (k === 't' && !oneShotAnim) {
      playOneShot('throw');
      e.preventDefault();
      return;
    }
    if (k === 'z' && !oneShotAnim) {
      playOneShot('death', () => {
        if (animations.dead) {
          currentAnim = 'dead';
          currentFrame = 0;
          setTimeout(() => { oneShotAnim = null; }, 2000);
        }
      });
      e.preventDefault();
      return;
    }

    e.preventDefault();
  });

  window.addEventListener('keyup', (e) => {
    keys[e.key.toLowerCase()] = false;
    e.preventDefault();
  });

  // ── Zoom with mouse wheel ──
  let zoomLevel = 1.5;
  const MIN_ZOOM = 0.2;
  const MAX_ZOOM = 5;
  window.addEventListener('wheel', (e) => {
    const delta = e.deltaY > 0 ? -0.1 : 0.1;
    zoomLevel = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, zoomLevel + delta));
    e.preventDefault();
  }, { passive: false });

  // ── Get Input Direction ──
  function getInputDirection() {
    const up    = keys['w'] || keys['arrowup'];
    const down  = keys['s'] || keys['arrowdown'];
    const left  = keys['a'] || keys['arrowleft'];
    const right = keys['d'] || keys['arrowright'];

    if (up && left)    return 'NW';
    if (up && right)   return 'NE';
    if (down && left)  return 'SW';
    if (down && right) return 'SE';
    if (up)            return 'N';
    if (down)          return 'S';
    if (left)          return 'W';
    if (right)         return 'E';
    return null;
  }

  // ── UI Elements ──
  const debugEl = document.getElementById('debug');

  // ── Game Loop ──
  app.ticker.add((ticker) => {
    const dt = ticker.deltaTime;
    const dir = getInputDirection();
    isRunning = keys['shift'];

    // ── Movement ──
    if (dir && !oneShotAnim) {
      isMoving = true;
      currentDir = dir;

      const vec = DIR_VECTORS[dir];
      const len = Math.sqrt(vec.x * vec.x + vec.y * vec.y);
      const speed = isRunning ? MOVE_SPEED * 1.8 : MOVE_SPEED;
      charWorldX += (vec.x / len) * speed * dt;
      charWorldY += (vec.y / len) * speed * dt;

      // Clamp to map bounds
      if (mapLoaded) {
        charWorldX = Math.max(0, Math.min(mapWidth, charWorldX));
        charWorldY = Math.max(0, Math.min(mapHeight, charWorldY));
      }

      const moveAnim = isRunning && animations.run ? 'run' : 'walk';
      if (currentAnim !== moveAnim) setAnimation(moveAnim);
    } else if (!oneShotAnim) {
      if (isMoving) {
        isMoving = false;
        setAnimation('neutral');
      }
    }

    // ── Animation Update ──
    const animName = currentAnim;
    const anim = animations[animName];
    if (!anim) return;

    const fps = getAnimFPS(animName);
    const frameInterval = 1000 / fps;

    animTimer += ticker.deltaMS;
    if (animTimer >= frameInterval) {
      animTimer -= frameInterval;
      currentFrame++;

      if (currentFrame >= anim.meta.framesPerDirection) {
        if (oneShotAnim) {
          const cb = oneShotCallback;
          oneShotAnim = null;
          oneShotCallback = null;
          currentFrame = 0;
          if (cb) {
            cb();
          } else {
            setAnimation(isMoving ? (isRunning ? 'run' : 'walk') : 'neutral');
          }
        } else {
          currentFrame = 0;
        }
      }
    }

    currentFrame = Math.min(currentFrame, anim.meta.framesPerDirection - 1);

    // ── Update Sprite ──
    const dccRow = DIR_MAP[currentDir];
    if (anim.frames[dccRow] && anim.frames[dccRow][currentFrame]) {
      character.texture = anim.frames[dccRow][currentFrame];
    }

    character.anchor.set(
      anim.meta.anchorX / anim.meta.frameWidth,
      anim.meta.anchorY / anim.meta.frameHeight,
    );

    // ── Position character in world space ──
    character.x = charWorldX;
    character.y = charWorldY;

    // ── Camera: center the world so character is on screen center ──
    world.scale.set(zoomLevel);
    world.x = app.screen.width / 2 - charWorldX * zoomLevel;
    world.y = app.screen.height / 2 - charWorldY * zoomLevel;

    // ── Debug ──
    debugEl.textContent =
      `${currentCharCode || '?'}/${currentWeapon || '?'} | Anim: ${animName} | Dir: ${currentDir} (row ${dccRow}) | ` +
      `Frame: ${currentFrame + 1}/${anim.meta.framesPerDirection} | ` +
      `FPS: ${fps.toFixed(1)} | Zoom: ${zoomLevel.toFixed(1)}x | ` +
      `Pos: ${Math.round(charWorldX)},${Math.round(charWorldY)} | ` +
      `${oneShotAnim ? 'ONE-SHOT' : isMoving ? (isRunning ? 'RUNNING' : 'WALKING') : 'IDLE'}`;
  });

  // ── Auto-select first character ──
  if (manifest) {
    const firstChar = Object.keys(manifest.characters)[0];
    if (firstChar) selectCharacter(firstChar);
  }
})();
