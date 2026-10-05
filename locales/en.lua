-- Ragdoll On Command: English texts, the source of every translation.
-- Translators: see TRANSLATING.md in Mod Options Menu's repository (the same files and tool work for this mod).
-- These show in Mod Bindings Menu (Options > Controls > MODS), which upper-cases them.
return {
    mod = 'ragdoll_on_command',
    title = 'Ragdoll On Command',
    language = 'en',
    strings = {
        -- The mod's name: its section in Mod Bindings Menu.
        ['option.mod'] = 'Ragdoll On Command',
        -- The key binding's name: the key that makes your Helldiver go limp and fall (ragdoll).
        ['binding.ragdoll'] = 'Ragdoll',
    },
    -- Mod Bindings Menu's limits, in characters.
    limits = {['option.mod'] = 64, ['binding.ragdoll'] = 64},
}
