<img width="1920" height="1080" alt="thumbnail4" src="https://github.com/user-attachments/assets/2675d3d0-b809-4a04-8657-13ed2f553569" />

# Ragdoll On Command

A Helldivers 2 Lua mod for [Bingus Shared Loader](https://github.com/CowboyBingus/BingusSharedLoader) that ragdolls your Helldiver with a key press.

## Features

- A **Ragdoll** key in [Mod Bindings Menu](https://github.com/CowboyBingus/ModBindingsMenu) (Options > Controls > MODS). It starts unbound: give it a key, a gamepad button or both.
- Pressing it knocks your Helldiver down the way an explosion does. The game ends the ragdoll and stands your Helldiver up by itself.
- If the game doesn't allow a ragdoll at that moment, or you're already ragdolled, nothing happens.
- Only your own Helldiver is affected.
- The binding's name follows the game's Text Language.

## Installation

1. Install [Bingus Shared Loader](https://www.nexusmods.com/helldivers2/mods/16292) (v17 or newer).
2. Install [Mod Bindings Menu](https://www.nexusmods.com/helldivers2/mods/16478) (required: it provides the key).
3. Install the ZIP from [Releases](https://github.com/Alomare/RagdollOnCommand/releases) with [HD2 Arsenal](https://www.nexusmods.com/helldivers2/mods/4664) (or HD2 Mod Manager) and deploy. Keep Bingus Shared Loader last in the mod order, so it loads first.

The verdict is the first line of `%LOCALAPPDATA%\CowboyBingus\Helldivers2\Logs\RagdollOnCommand_STATUS.log`.

## Technical Details

- **The ragdoll.** On a key press the mod runs the game's own knockdown sequence on the local Helldiver: `is_ragdolled`, then `can_ragdoll` (the game's own check of whether a ragdoll is allowed right now), then `start_ragdoll`. The game's per-frame ragdoll update ends it.
- **The local Helldiver.** Found as the game's own "is this the local avatar" check finds it: the local player's unit, its entity, then the avatar manager's index for that entity. The native functions are only called after that whole chain was read the same frame and the ragdoll state names the same entity, since these functions crash on an entity that isn't an avatar.
- **Finding the game's code.** Every global, native function and structure offset comes from 5 code signatures generated in one block by `research/signatures.py` from a game.dll dump and checked to match exactly once. Each is tried at the known build's address first, else game.dll's executable sections are searched over a few frames; values are read from the matched instructions, repeated values must agree, and the knockdown's calls must go to the functions found on their own. Anything missing turns the mod off. The search engine (`tools/sigscan.lua` in the author's workspace) is shared with the author's other mods.
- **Texts.** `locales/en.lua` is the English source and `locales/<tag>.lua` the bundled translations, resolved by CowboyBingus' `src/bingus_text.lua` against the game's Text Language; the build places both ahead of the script.
- **Memory access.** Reads go through `ReadProcessMemory` on the game's own process, which fails instead of crashing on a bad address. After the code search at startup, the mod reads nothing until the key is pressed. It never writes game memory itself; the game's own functions do.
- **Tests.** `tests/test_release.py` runs the built entry under LuaJIT against a game.dll dump (not included), with the local avatar chain, the game's ragdoll functions and Mod Bindings Menu simulated.

Research notes: [NOTES.md](NOTES.md). Release notes: [CHANGELOG.md](CHANGELOG.md).

## Credits

- Built on [Bingus Shared Loader](https://github.com/CowboyBingus/BingusSharedLoader) and [Mod Bindings Menu](https://github.com/CowboyBingus/ModBindingsMenu) by CowboyBingus, whose `bingus_text.lua` provides the translations.
- Developed with Claude Opus 5.5 and the [HD2 Lua Mod Skill](https://github.com/MrChengl11/hd2-lua-mod-skill).
