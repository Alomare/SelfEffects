-- Self-Effects: English texts, the source of every translation.
-- Translators: see TRANSLATING.md in Mod Options Menu's repository (the same files and tool work for this mod).
-- These show in Mod Bindings Menu (Options > Controls > MODS), which upper-cases them, and in Mod Options Menu
-- (escape menu > MODS), which upper-cases the mod name and the choices.
return {
    mod = 'self_effects',
    title = 'Self-Effects',
    language = 'en',
    strings = {
        -- The mod's name: its section in Mod Bindings Menu and its category button in Mod Options Menu.
        ['option.mod'] = 'Self-Effects',
        -- A key binding's name: {n} is the key's number (1 to 3), {effect} the effect it is set to (one of the
        -- effect names below), as in "Effect 1: Ragdoll".
        ['binding.effect'] = 'Effect {n}: {effect}',
        -- Mod Options Menu rows (escape menu > MODS): which effect each key applies. One description for the three.
        ['option.effect_1'] = 'Effect 1',
        ['option.effect_2'] = 'Effect 2',
        ['option.effect_3'] = 'Effect 3',
        ['option.effect.description'] = 'What this key does to your own Helldiver. Set the keys in Options > Controls > MODS (Effect 1 to 3). Every effect is the game\'s own, as if an enemy or a hazard had caused it.',
        -- The effects: choices in Mod Options Menu and part of the key names above. Each happens to your Helldiver.
        -- Ragdoll: your Helldiver goes limp and falls, then gets up.
        ['effect.ragdoll'] = 'Ragdoll',
        ['effect.fire'] = 'Set on Fire',
        ['effect.stun'] = 'Stun',
        ['effect.gas'] = 'Gas',
        ['effect.bleed'] = 'Bleeding',
        ['effect.confusion'] = 'Confusion',
        ['effect.acid'] = 'Acid',
        ['effect.slowed'] = 'Slowed',
        ['effect.poison'] = 'Poisoned',
        -- Injuries: a leg (limping), an arm (aim sway), the chest. A stim heals them.
        ['effect.leg'] = 'Injured Leg',
        ['effect.arm'] = 'Injured Arm',
        ['effect.chest'] = 'Injured Chest',
        -- Rooted: unable to move. Choked: the coughing of a gas cloud. Long Stun: a longer stun than Stun.
        ['effect.rooted'] = 'Rooted',
        ['effect.choked'] = 'Choked',
        ['effect.long_stun'] = 'Long Stun',
        ['effect.radiation'] = 'Radiation',
        -- Inverted Aim: the aim assist pushes the aim away from targets.
        ['effect.inverted_aim'] = 'Inverted Aim',
        -- Tremor: the ground shaking of a quake. Tornado: the stun of being caught by a tornado.
        ['effect.tremor'] = 'Tremor',
        ['effect.tornado'] = 'Tornado',
        -- Dark Fluid: the status of the game's Dark Fluid. Scrambled: the Illuminate's scrambling of the HUD.
        ['effect.dark_fluid'] = 'Dark Fluid',
        ['effect.scrambled'] = 'Scrambled',
        -- Gloom: the toxic spore fog of Gloom planets.
        ['effect.gloom'] = 'Gloom',
        -- Heavy fire: the strong burning of napalm, of thermite, and of lava.
        ['effect.burning_heavy'] = 'Napalm Fire',
        ['effect.thermite'] = 'Thermite',
        ['effect.lava'] = 'Lava',
        -- Launch: your Helldiver is thrown up into the air. Explode: your Helldiver blows apart (and dies); no one else is hurt.
        ['effect.launch'] = 'Launch',
        ['effect.explode'] = 'Explode',
    },
    -- Mod Bindings Menu's and Mod Options Menu's limits, in characters.
    limits = {['option.mod'] = 40, ['binding.effect'] = 64, ['option.effect_1'] = 64, ['option.effect_2'] = 64,
              ['option.effect_3'] = 64, ['option.effect.description'] = 400,
              ['effect.ragdoll'] = 48, ['effect.fire'] = 48, ['effect.stun'] = 48, ['effect.gas'] = 48,
              ['effect.bleed'] = 48, ['effect.confusion'] = 48, ['effect.acid'] = 48, ['effect.slowed'] = 48,
              ['effect.poison'] = 48, ['effect.leg'] = 48, ['effect.arm'] = 48, ['effect.chest'] = 48,
              ['effect.rooted'] = 48, ['effect.choked'] = 48, ['effect.long_stun'] = 48, ['effect.radiation'] = 48,
              ['effect.inverted_aim'] = 48, ['effect.tremor'] = 48, ['effect.tornado'] = 48,
              ['effect.dark_fluid'] = 48, ['effect.scrambled'] = 48, ['effect.gloom'] = 48,
              ['effect.burning_heavy'] = 48, ['effect.thermite'] = 48, ['effect.lava'] = 48, ['effect.launch'] = 48,
              ['effect.explode'] = 48},
}
