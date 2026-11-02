<img width="1920" height="1080" alt="thumbnail4" src="https://github.com/user-attachments/assets/2675d3d0-b809-4a04-8657-13ed2f553569" />

# Self-Effects

A Helldivers 2 Lua mod for [Bingus Shared Loader](https://github.com/CowboyBingus/BingusSharedLoader) that applies negative effects to your own Helldiver at a key press: ragdoll, fire, stun, gas, bleeding, injuries and more. Formerly **Ragdoll On Command**.

> Version 3 is in development on `main`. The status and injury effects are still being tested in game; the latest release, V2, is still Ragdoll On Command (one Ragdoll key and a delay setting).

## Features

- Three keys in [Mod Bindings Menu](https://github.com/CowboyBingus/ModBindingsMenu) (Options > Controls > MODS): **Effect 1**, **Effect 2** and **Effect 3**. They start unbound, except that Effect 1 keeps the key you gave Ragdoll On Command's Ragdoll binding.
- Each key's effect is chosen in [Mod Options Menu](https://github.com/CowboyBingus/ModOptionsMenu) (escape menu > MODS > Self-Effects). Without it the keys are Ragdoll, Rooted and Stun. The key names show the effect they're set to, for example "Effect 1: Ragdoll".
- The effects:
  - **Ragdoll**: your Helldiver goes limp and falls the way an explosion knocks them down, then gets up.
  - **Statuses**: Set on Fire, Stun, Gas, Bleeding, Confusion, Acid, Slowed, Poisoned.
  - **Injuries**: Injured Leg, Injured Arm, Injured Chest. An injury costs health the way a hit on that limb does, and a stim heals it.
- Every effect is the game's own: the game decides whether your Helldiver can have it right now, applies it and ends it as if an enemy or a hazard had caused it. If it can't happen at that moment, nothing happens.
- Only your own Helldiver is affected.
- The key names and settings follow the game's Text Language.

## Installation

1. Install [Bingus Shared Loader](https://www.nexusmods.com/helldivers2/mods/16292) (v17 or newer).
2. Install [Mod Bindings Menu](https://www.nexusmods.com/helldivers2/mods/16478) (required: it provides the keys).
3. Optional: [Mod Options Menu](https://www.nexusmods.com/helldivers2/mods/16625), to choose each key's effect.
4. Install the ZIP from [Releases](https://github.com/Alomare/SelfEffects/releases) with [HD2 Arsenal](https://www.nexusmods.com/helldivers2/mods/4664) (or HD2 Mod Manager) and deploy. Keep Bingus Shared Loader last in the mod order, so it loads first.

The verdict is the first line of `%LOCALAPPDATA%\CowboyBingus\Helldivers2\Logs\SelfEffects_STATUS.log`.

## Technical Details

- **The ragdoll.** The game's own knockdown sequence on the local Helldiver: `is_ragdolled`, then `can_ragdoll` (the game's own check of whether a ragdoll is allowed right now), then `start_ragdoll`. The game's per-frame ragdoll update ends it.
- **Statuses.** One request per status to the game's status request queue, with your Helldiver as target and instigator, and enough buildup that the status starts at the first press. The game checks that your Helldiver can have the status and applies it like any other. Each status's settings row is checked against the name the game stores for it before the first request.
- **Injuries.** One damage request at the limb's physics actor through the game's damage queue, with the template of the VG-70 Variable's own self-damage: the limb's damage zone loses its remaining health, so the limb is injured.
- **The local Helldiver.** Found as the game's own "is this the local avatar" check finds it: the local player's unit, its entity, then the avatar manager's index for that entity. The native functions are only called after that whole chain was read the same frame and what they get names the same entity.
- **Finding the game's code.** Every global, native function and structure offset comes from 10 code signatures generated in one block by `research/signatures.py` from a game.dll dump and checked to match exactly once. Each is tried at the known build's address first, else game.dll's executable sections are searched over a few frames; values are read from the matched instructions, repeated values must agree, and calls must go to the functions found on their own. If the ragdoll's code is missing the mod turns off; if a family's code is missing (statuses, injuries), only those effects are off. The search engine (`tools/sigscan.lua` in the author's workspace) is shared with the author's other mods.
- **Texts.** `locales/en.lua` is the English source and `locales/<tag>.lua` the bundled translations, resolved by CowboyBingus' `src/bingus_text.lua` against the game's Text Language; the build places both ahead of the script.
- **Memory access.** Reads go through `ReadProcessMemory` on the game's own process, which fails instead of crashing on a bad address. After the code search at startup, the mod reads nothing until a key is pressed (and while an effect it started settles, for its log). It never writes game memory itself; the game's own functions do.
- **Tests.** `tests/test_release.py` runs the built entry under LuaJIT against a game.dll dump (not included), with the local avatar chain, the status and health managers, the request queues, the game's functions, Mod Bindings Menu and Mod Options Menu simulated.

How it works in the game's code: [RESEARCH.md](RESEARCH.md). Contributing: [CONTRIBUTING.md](CONTRIBUTING.md). Release notes: [CHANGELOG.md](CHANGELOG.md).

## Credits

- Uses research from [HD2Runtime](https://github.com/SkyeShade/HD2Runtime) by SkyeShade: the game's status request and damage request functions, the status catalog (types and names), the limb injury template and the engine's actor lookup.
- Built on [Bingus Shared Loader](https://github.com/CowboyBingus/BingusSharedLoader), [Mod Bindings Menu](https://github.com/CowboyBingus/ModBindingsMenu) and [Mod Options Menu](https://github.com/CowboyBingus/ModOptionsMenu) by CowboyBingus, whose `bingus_text.lua` provides the translations.
- Developed with Claude Opus 5.5 and the [HD2 Lua Mod Skill](https://github.com/MrChengl11/hd2-lua-mod-skill).

## License

Copyright (c) 2026 Alomare. Licensed under the [MIT License](LICENSE). `src/bingus_text.lua` is CowboyBingus's, under the Zero-Clause BSD license.
