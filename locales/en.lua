-- Ragdoll On Command: English texts, the source of every translation.
-- Translators: see TRANSLATING.md in Mod Options Menu's repository (the same files and tool work for this mod).
-- These show in Mod Bindings Menu (Options > Controls > MODS), which upper-cases them, and in Mod Options Menu
-- (escape menu > MODS), which upper-cases the mod name.
return {
    mod = 'ragdoll_on_command',
    title = 'Ragdoll On Command',
    language = 'en',
    strings = {
        -- The mod's name: its section in Mod Bindings Menu and its category button in Mod Options Menu.
        ['option.mod'] = 'Ragdoll On Command',
        -- The key binding's name: the key that makes your Helldiver go limp and fall (ragdoll).
        ['binding.ragdoll'] = 'Ragdoll',
        -- A Mod Options Menu slider (escape menu > MODS): the time between pressing the Ragdoll key and the ragdoll.
        ['option.delay.label'] = 'Delay After Key Press (Milliseconds)',
        ['option.delay.description'] = 'Time between pressing the Ragdoll key and your Helldiver going limp. At 0, it happens at once.',
    },
    -- Mod Bindings Menu's and Mod Options Menu's limits, in characters.
    limits = {['option.mod'] = 40, ['binding.ragdoll'] = 64, ['option.delay.label'] = 64,
              ['option.delay.description'] = 400},
}
