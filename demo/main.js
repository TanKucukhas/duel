(async () => {
  // ── D2 Direction Mapping ──
  // DCC 16-direction files use this internal order.
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

  const SCALE = 2.5;
  const MOVE_SPEED = 3;

  // ── PixiJS Setup ──
  const app = new PIXI.Application();
  await app.init({
    width: 900,
    height: 650,
    backgroundColor: 0x111118,
    antialias: false,
    resolution: window.devicePixelRatio || 1,
    autoDensity: true,
  });
  document.body.appendChild(app.canvas);

  // ── Ground Grid ──
  const ground = new PIXI.Graphics();
  ground.setStrokeStyle({ width: 1, color: 0x1a1a2e });
  for (let x = 0; x < 900; x += 50) ground.moveTo(x, 0).lineTo(x, 650);
  for (let y = 0; y < 650; y += 50) ground.moveTo(0, y).lineTo(900, y);
  ground.stroke();
  app.stage.addChild(ground);

  // ── Character Sprite ──
  const character = new PIXI.Sprite(PIXI.Texture.EMPTY);
  character.scale.set(SCALE);
  character.x = app.screen.width / 2;
  character.y = app.screen.height / 2;
  app.stage.addChild(character);

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

  // ── Load Manifest ──
  const CB = Date.now();
  let manifest = null;
  try {
    const resp = await fetch(`assets/sprites/manifest.json?v=${CB}`);
    manifest = await resp.json();
  } catch (e) {
    console.error('Failed to load manifest:', e);
  }

  // ── Build UI ──
  const charButtonsEl = document.getElementById('char-buttons');
  const weaponSelectEl = document.getElementById('weapon-select');
  const loadingEl = document.getElementById('loading');

  const CHAR_NAMES = {
    BA: 'Barbarian', AM: 'Amazon', NE: 'Necromancer',
    PA: 'Paladin', SO: 'Sorceress', DZ: 'Druid', AI: 'Assassin',
  };

  if (manifest) {
    // Create character buttons
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

    // Default to HTH if available, else first weapon
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

    // Skip if already loaded
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

      // Load new spritesheet textures
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

      // Reset animation state
      oneShotAnim = null;
      oneShotCallback = null;
      currentFrame = 0;
      animTimer = 0;

      // Pick a valid initial animation
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
    // Update button states
    document.querySelectorAll('.char-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.char === charCode);
    });

    // Update weapon dropdown
    updateWeaponDropdown(charCode);

    // Load character with selected weapon
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

    // Number keys 1-7 for character selection
    if (manifest && k >= '1' && k <= '9') {
      const chars = Object.keys(manifest.characters);
      const idx = parseInt(k) - 1;
      if (idx < chars.length) {
        selectCharacter(chars[idx]);
        e.preventDefault();
        return;
      }
    }

    // Space = attack
    if (k === ' ' && !oneShotAnim) {
      playOneShot(animations.attack1 ? 'attack1' : 'attack2');
      e.preventDefault();
      return;
    }
    // Q = cast
    if (k === 'q' && !oneShotAnim) {
      playOneShot('cast');
      e.preventDefault();
      return;
    }
    // E = kick
    if (k === 'e' && !oneShotAnim) {
      playOneShot('kick');
      e.preventDefault();
      return;
    }
    // F = skill1 (warcry)
    if (k === 'f' && !oneShotAnim) {
      playOneShot('skill1');
      e.preventDefault();
      return;
    }
    // X = get hit
    if (k === 'x' && !oneShotAnim) {
      playOneShot('gethit');
      e.preventDefault();
      return;
    }
    // B = block
    if (k === 'b' && !oneShotAnim) {
      playOneShot('block');
      e.preventDefault();
      return;
    }
    // R = attack2
    if (k === 'r' && !oneShotAnim) {
      playOneShot('attack2');
      e.preventDefault();
      return;
    }
    // T = throw
    if (k === 't' && !oneShotAnim) {
      playOneShot('throw');
      e.preventDefault();
      return;
    }
    // Z = death
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
      character.x += (vec.x / len) * speed * dt;
      character.y += (vec.y / len) * speed * dt;

      const pad = 80;
      if (character.x < -pad) character.x = app.screen.width + pad;
      if (character.x > app.screen.width + pad) character.x = -pad;
      if (character.y < -pad) character.y = app.screen.height + pad;
      if (character.y > app.screen.height + pad) character.y = -pad;

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

    // ── Debug ──
    debugEl.textContent =
      `${currentCharCode || '?'}/${currentWeapon || '?'} | Anim: ${animName} | Dir: ${currentDir} (row ${dccRow}) | ` +
      `Frame: ${currentFrame + 1}/${anim.meta.framesPerDirection} | ` +
      `FPS: ${fps.toFixed(1)} | ` +
      `${oneShotAnim ? 'ONE-SHOT' : isMoving ? (isRunning ? 'RUNNING' : 'WALKING') : 'IDLE'}`;
  });

  // ── Auto-select first character ──
  if (manifest) {
    const firstChar = Object.keys(manifest.characters)[0];
    if (firstChar) selectCharacter(firstChar);
  }
})();
