# Self-Effects: how it works in the game's code

Self-Effects (formerly Ragdoll On Command) applies negative effects to the local Helldiver on a Mod Bindings Menu key press: three keys, each set to one effect in Mod Options Menu. Every effect goes through the game's own code: the knockdown sequence for the ragdoll, the status request queue for statuses, the damage queue for limb injuries, the movement velocity setter for Launch, and for Explode a killing hit through the damage queue plus particles and a sound only this machine shows. The game decides whether the effect can happen, applies it and ends it.

All addresses are game.dll RVAs for build 25480438 (in a Ghidra session based at 0x7ffcea020000, `FUN_7ffceaa95fa0` is RVA 0xa75fa0). The mod does not depend on them: it finds every global, function and offset by the code signatures below, so it survives updates that move code.

## How the game ragdolls an avatar

The ragdoll code was found from the string `avatar_ragdoll_active` (an animation variable it sets) and the avatar flag writes. The avatar manager is the global 0x3326d20.

- **Avatar index:** the manager's hash map at +0xf8 (data), +0x100 (capacity), +0x104 (empty key), +0x108 (multiplier) maps an avatar entity id to its index. Rows are (key, value) u32 pairs, probed linearly from `key * mult` (low 32 bits), masked by `capacity - 1`. The entity's record pointer is at +0x110 + index * 8.
- **Per avatar,** at manager + 0x53d900 + index * 0x1238 (the avatar controller):
  - +0xf80, +0xf88 and +0xf90 are a 192-bit flag set. Every change goes through the dispatcher 0xa3f220 (controller, mask, on/off).
  - +0xf88 bit 36 (0x1000000000) is **ragdolled**; bit 44 is checked when the ragdoll starts and ends.
  - +0x448 (manager + 0x53dd48 + index * 0x1238) is the **ragdoll state**, with the avatar's entity id at +0x398. The functions below take a pointer to it.
- **0xa74700 `is_ragdolled(state)`:** looks up the state's entity and returns flag bit 36. It has sibling checks with identical code that test other bits, so its signature runs through the `shr rax, 0x24`.
- **0xa74850 `can_ragdoll(state)`:** true when `flags & 0x184080980000040 == 0` and byte +0xf80 bit 2 is set. The meaning of those bits is unknown; it is probably what refuses a ragdoll while diving, swimming, climbing and so on.
- **0xa75fa0 `start_ragdoll(state, mode)`:**
  - Sets flag bit 36 through the dispatcher and clears flag bit 1.
  - Sets the ragdoll mode (0xa77800: 2, or 4 when bit 44 is set; or the mode from the optional `mode` record, NULL for none).
  - Resets the state's timers (+0x34c, +0x350 = 0.1, +0x354 = 0.5) and stores the position.
  - Posts a network event (0xabfe430, id 0x112a8a3b).
- **0xa747d0 `try_ragdoll(state, mode)`:** returns 1 if `!is_ragdolled && can_ragdoll`, and calls start. The knockdown at 0x833540 (avatar manager, entity) inlines the same three calls with mode NULL, after 0x9415a0, a physics or audio call whose purpose is unknown.
- **0xa76630 `end_ragdoll(state)`:**
  - Clears bit 36 and sets mode 0.
  - Posts event 0x85d82942.
  - Restores the stance. The game's per-frame ragdoll update (0xa74ce0, state, dt) decides when to call it, so the Helldiver gets up without the mod's help.
- **0xa76fc0 (physics impact):** accumulates impact force, and when the impact is strong enough it spawns the "ragdoll collision" body and sets the animation variables. Its +0xff0 cooldown (1.5 s) is only read there. This is the explosion path, not a trigger a mod can call.

What the mod does on a key press: resolve the local Helldiver's ragdoll state (next section), then `is_ragdolled`, `can_ragdoll`, `start_ragdoll(state, NULL)`, the same sequence as the knockdown. Live-proven: calling these from the Lua `update` hook through LuaJIT FFI function pointers is safe, the Helldiver ragdolls, and the game stands them up. Whether squadmates see the ragdoll when the caller is a client (not the host) is unknown: `start_ragdoll` posts a network event, but whether a client's call reaches the host has not been tested.

**Native calls are only safe for an avatar in the map.** If an entity is not in the avatar map, the lookup in these functions returns index 0xffffffff, and they read manager + 0xffffffff * 0x1238, which crashes. The mod calls them only after it has read the whole chain itself (with `ReadProcessMemory`, which fails instead of crashing) in the same frame, and the ragdoll state names the same entity.

## The local Helldiver

The game's "is this the local avatar" check at 0xa40070 shows the chain:

1. Players: the global 0x3326468. The local player is active when +0x88 is non-zero; its unit is at +0x3a8 (0x7fff = none).
2. Unit to entity (0xfd9ba0): the entity owner global 0x346bf98 has a unit map at +0xf22ec8 (data), +0xf22ed0 (capacity), +0xf22ed4 (empty key) and +0xf22ed8 (multiplier), the same kind of hash map as the avatar index. The entity id is at owner + 0x1e65e4 * 8 + index * 24: the entity records are 24 bytes each from owner + 0xf32f18, with the id at +8 (0x1e65e4 * 8 = 0xf32f20).
3. The entity id is checked against the "no entity" id (the global 0x3483c20), then looked up in the avatar map. The ragdoll state is manager + 0x53dd48 + avatar index * 0x1238.

This is the same chain Shallow Water Diving reads for the local avatar.

## Statuses

Live-proven on the host's own Helldiver (3-recon-2, 2026-10-19): Fire, Gas (with Gas_Confusion), Blind, Deaf, Confusion, Electric, Acid Splash, Slowed and Poison all showed in the Helldiver's zone masks within 0.1 s of the request and ended after about their settings durations (Fire 1.6 s, Gas 0.6 s and Gas_Confusion 4.9 s, Confusion 12 s, Electric 4.9 s, Acid 4.1 s, Slowed 4 s, Poison 6 s). HD2Runtime (SkyeShade) had proved the request on enemies, as the host: `fire` with buildup 100 applied to a live enemy.

- **The request: 0x129f170 `QueueStatusRequest(ignored, type, target, buildup, instigator, variant)`** (HD2Runtime's name). It looks the target up in the status manager's entity map (the global 0x3326620: slots +0x12c0 {u32 entity, u32 index}, capacity +0x12c8, empty key +0x12cc, multiplier +0x12d0; index -1 = none), returns if the target is the "no entity" id or has no index, then asks 0x6994f0 (target, type) whether the target can have that status, and only then appends a 28-byte row to the request queues (the global 0x347cf38: count +0x201134, at most 0x1000 rows, rows from +0xe778 * 0x1c: target, type, instigator twice, variant, buildup, a value from 0x129f4b0). There is no host check in it; the queue's drain routes the request. `buildup` is a float in xmm3.
- **The game's own requests** use buildup 100.0 (the float at 0x23c77f0): an avatar effect at 0x607ed0 queues Stun Medium (38), and 0x864cc0 / 0xb91e00 pick Stun Small, Medium or Large (37-39) at random by distance. Most statuses on Helldivers come from the status slots of damage rows (HD2Runtime's `docs/status-effects.md`), not from this queue.
- **Buildup:** the float is buildup, not strength (HD2Runtime's `docs/events.md`): each request adds it, and the status starts when the target's buildup reaches its susceptibility threshold. With 100, Poison on a Helldiver twice needed a second request 1-2 s later (both requests accepted, the status shown only after the second), while Fire started at every request. The mod sends 1000, HD2Runtime's upper bound; the duration comes from the status settings either way.
- **What the mod does:** for each status of the effect (Gas is two: Gas 42 and Gas_Confusion 44), it checks the type's settings row, reads the queue count, calls the request with the Helldiver as target and instigator, buildup 1000 and variant 0, and reads the count again: one more row means the game accepted the request; the same count means the target lookup or the susceptibility check refused it.
- **The settings table: 0x37c5c50**, one pointer per status type to its 152-byte StatusEffectInfo: +0 the type, +8 its name (a C string: "Fire", "Stun Medium", "Gas_Confusion"...), +40 the duration. The mod requests a type only when its row holds that type and that name (an unreadable name is accepted and logged), so a renumbered table can't make a key apply another status.
- **Types** (HD2Runtime's catalog for this build, its order plus one; FileDiver's enum is older and off from 6 on): Blind 1, Bleed 2, Deaf 3, Confusion 4, Fire 5, Slowed 8, Rooted 9, Acid Splash 10, Choked 14, RadiationHeavy 34, Electric 35, Stun Small / Medium / Large / Massive 37-40, Gas 42 (Gas_2 43), Gas_Confusion 44 (45), Inverted_Aim_Assist 46, Tremor 52, TornadoStun 57, Dark Fluid 58, Illuminate Scrambler 63, Gloom 68, Poison 70. Bleed's settings duration is 9999 s: it lasts until a stim. The game bounds no type: one of 128 or more corrupts the stack (HD2Runtime), so the mod only requests the catalogued types above.
- **Reading a status back:** has_status (0x69b1f0) finds the entity in the same map and tests the type's bit in the entity's block (blocks +0x12e8, 0x1228 bytes each by the map's index): one 128-bit mask a zone, 16 bytes each from +0. The mod reads 8 zones after a request and logs when each requested status shows and ends.

## Injuries

Not yet confirmed in game (HD2Runtime ships the same request as `hd2.actions.injure`, also not live-tested). 3-recon-2 never sent it: it required the descriptor's unit to equal the players list's unit id (+0x3a8), and they differ. They are different ids: the players list's is the key of the entity owner's unit map, the descriptor's is the engine unit handle HD2Runtime passes to the actor lookup.

- **The request: 0x129f910 `QueueDamage(ignored, kind, element, target, damage, a6, dealer, owner, creditor, a10, f11, f12, f13, direction, position, actor, a17, a18, f19)`** (HD2Runtime's research). It looks the target up in the health manager's entity map (the global 0x3326688: slots +0x1030, capacity +0x1038, empty key +0x103c, multiplier +0x1040) and appends a 0x70-byte row to the same request queues (count +0x201120, at most 0x1000). The game's drain applies it later in the frame like any hit: the damage zone that lists the actor loses the damage, main health loses the zone's share, and a zone at 0 health is an injured limb.
- **The template** is the VG-70 Variable's own self-damage, as HD2Runtime recorded it: kind 6, element 0, a6 = 1, dealer and owner the Helldiver's network id, the record's current last-hit creditor, a10 = 0, f11-f13 = 0, direction (0, 0, -1), position (0, 0, 0), the limb's actor, a17 = 9, a18 = 0, f19 = 1.0.
- **The limb's actor:** the engine's unit actor lookup `(unit, actor name hash, null) -> actor handle` (0xFFFFFFFF = none), an exe function game.dll calls through its engine API table: `[[0x3326310] + 0x10]` (for example at 0x11adc5c). In the exe of this build it is RVA 0x799de0, starting `48 89 6C 24 20 56 48 81 EC 80 00 00 00 49 8B F0 8B EA`; the mod checks those bytes before every call. The actor names the mod uses, as the game's code passes them: chest 0x37ef0820, r_hand 0x248004f5, l_knee 0x8fd2dfec (also head 0x8c5570c9, l_hand 0x5c0c68d3, r_knee 0x3ac8154a).
- **The health record** (records +0x1058, 0x1b8 bytes each by the map's index): +0x14 health, +0x20 the zones' states (2 bits each; 2 = injured), +0x38 the last-hit creditor (u64), +0xf8 + 4 x zone each zone's health (Helldiver zones: 0 head 85, 1 chest 60, 2 left arm 35, 3 right arm 35, 4 left leg 45, 5 right leg 45), +0x19c the life state (0 alive, 1 downed). The descriptors (+0x1048) are a pointer per index to {u64 type, u32 entity, u32 unit, u32 network id, u32 flags (bit 0: this machine owns it)}.
- **What the mod does:** it reads the Helldiver's descriptor (it must name the same entity, have a unit, be owned by this machine and have a network id below 0x7fff) and record (alive, the zone not already at 0), looks the limb's actor up on the descriptor's unit, and requests the zone's remaining health (at most its full health) as damage, so one request injures the limb. Armor passives and boosters apply as they do to any hit, so the zone can lose less.

## Launch

Not yet confirmed in game (HD2Runtime ships the same call as `hd2.actions.add_velocity`, also not live-tested).

- **The setter: 0x4a7550 `SetVelocity(ignored, entity, const float v[3])`** (HD2Runtime's research): the velocity the avatar's movement and the jump pack's thrust use. It looks the entity up in the motion manager's map (the global 0x3326558: slots +0x48a0, capacity +0x48a8, empty key +0x48ac, multiplier +0x48b0) and writes v to the record (records +0x48c8, 0x84 bytes each, the velocity at +0) and to a second array (+0x48d0, 0xa4 bytes each: v at +0xc, its length at +0x48). **It does not check that the lookup found the entity**: a missing entity gives index 0xFFFFFFFF and the write lands far outside the arrays. The ragdoll's end calls it too.
- **What the mod does:** it looks the Helldiver up in the same map first (refused when missing), reads the current velocity from the record, adds 14 m/s up and calls the setter with the sum when the result stays at most 50 m/s (HD2Runtime's bound). It then logs the vertical velocity for 1.5 s. What ground movement does with the new velocity on the next frame is the open question: the game's own avatar launch (5.8 m/s forward, 3.3 m/s up) also switches the avatar's movement state.

## Explode

Not yet confirmed in game. No explosion is requested: the effect is one hit on the Helldiver alone, which kills it and lets the game tear the body apart, plus a blast that only this machine shows. Nothing and nobody else is damaged or pushed.

- **The killing hit** goes through the same `QueueDamage` as the injuries, with the injury template except: actor 0xFFFFFFFF (none), damage 5000, f11 (the push the severed parts get) 200, direction (0, 0, 1), position the Helldiver's root. The drain turns the "no actor" handle into actor name 0 (0x12a7d77), so ApplyDamage matches no damage zone and main health takes the whole hit (0x923d0d to 0x923d4f), with no zone cap.
- **Why it tears the body apart:** ApplyDamage runs the gore check (0x9251a8) only when the hit kills (the Helldiver's six damage zones are immortal, so a zone's death never starts it; kind 8, drowning, never runs it). In the gore evaluator (0x9057d0), actor name 0 on an avatar (the avatar map 0x3326d20, 0x905a19) walks every gore group (0x905ac0 to 0x905b97) and severs each one whose threshold the damage reaches (0x903c70). The hit class must not be 0 or 5 (0x9058b9, 0x9058db); 9 is fine. The gore result is sent to the other machines (0x925334).
- **The Helldiver's gore (`avatar_helldiver`, GoreComponentData record 30):** six groups: head (threshold 140), each arm (l_shoulder, r_shoulder: 550), each lower leg (l_knee, r_knee: 550), hips (550). None is a whole-body group (flag +866), and none has gib piece entities, so the body comes apart limb by limb but never bursts like a Warrior. Main health 125.
- **The blast** (this machine only), through the engine's Lua API in the world that holds a Helldiver unit (`avatar_helldiver`, resource 0x4d1c334d294dfa97) within 2 m of the position: `World.create_particles(world, IdString64 0x6d2bad783480d272, position, Quaternion.identity())`, the W.A.S.P. Launcher's impact particles (explosion rows 87 and 158 use them), listed by `packages/content/effects_mission`, only after `Application.can_get('particles', ...)` says they are loaded (creating a missing resource is an engine assert); and `WwiseWorld.trigger_event(Wwise.wwise_world(world), 'hd2runtime_0wyiw_n', position)` after `Wwise.has_event`: that name hashes (FNV-1, lower case) to the event 0x4fbdbb61, the explosion sound about 15 explosion rows share, in the `content/audio/weapons_superearth` bank (HD2Runtime's research).
- **The position:** the ragdoll start (0xa75fa0) reads the avatar's position through the engine API: `[[0x3326308] + 0x18] + 0x88` is `world_position(unit, node)`, an exe function (RVA 0x1fd190 in this build's exe). It calls the engine's unit object lookup (exe 0x9d8c0: the registry global, `index = unit & 0x3fffff` below the count at +0x98, the generation byte `unit >> 22` in the array at +0xa0, the object pointer in the array at +0x88), then the object's scene graph method (vtable +0xe8, `lea rax, [rcx + 0x60]; ret`), and returns `[graph + 0x28] + node * 64 + 0x30`, the node's world translation. The mod checks the bytes of all three functions and reads the same path with ReadProcessMemory instead of calling it (the lookup returns null for a stale unit, which the caller then dereferences), node 0 (the root), for the unit in the Helldiver's health descriptor. The unit object's +8 must name the unit (HD2Runtime's check).
- **Missions only:** the game state (`[0x3326340] + 0xac21c`, as the hellpod launch compares it) must be 4.
- It is a real death (it uses a reinforcement). Whether the severed parts fly or only vanish behind blood effects, and how far the push throws them, is for the live test.

## Signatures (research/signatures.py)

| Signature | Code | What the mod reads |
|---|---|---|
| `local_avatar` | 0xa40076, through the function's tail (a shorter span also matches 0x18ba436) | players, local flag and unit, the unit lookup's call, no-entity id, avatar map |
| `unit_lookup` | 0xfd9ba0 | owner, no-unit id, unit map, entity id array |
| `knockdown` | 0x833680 (inside the knockdown at 0x833540) | ragdoll state offset and avatar stride, and the calls to the three functions |
| `ragdoll_check` | 0xa74700 | state entity offset, flag word (+0x53e888), the same avatar map |
| `ragdoll_flags` (optional) | 0xa748fa (inside `can_ragdoll`) | the +0xf80 word (+0x53e880), only for refusal logs |
| `status_request` (optional: statuses) | 0x129f170, the request from its start through the count check | status manager, its map, the request queues, no-entity id, the susceptibility call, the status count |
| `status_table` (optional: statuses) | 0x69b2e4 (inside has_status) | the settings table, the status blocks and their stride |
| `damage_request` (optional: injuries) | 0x129f910, the request from its start through the count check | health manager, its map, the request queues, no-entity id, the damage count |
| `health_record` (optional: injuries) | 0x659ab5 (a health record lookup) | the same map, the records and their stride, the descriptors |
| `actor_lookup` (optional: injuries) | 0x11adc5c | the engine API global and the actor lookup's slot |
| `velocity` (optional: Launch) | 0x4a7550, SetVelocity from its start through the record write | no-entity id, motion manager, its map, the records and their stride |
| `game_state` (optional: Explode) | 0x11d5b23 (the hellpod launch's mission check) | the game global and the state offset |
| `unit_position` (optional: Explode) | 0xa76301 (inside the ragdoll start) | the engine API global, its function table and the world position's slot |

Fields shared between signatures must agree. The mod also checks that the knockdown's `is_ragdolled` call and the local-avatar check's unit-lookup call go to the functions found by their own bodies. If a required signature is missing or a check fails, the mod does nothing; if an optional family's signature is missing, only that family's effects are off.

## Prior art and credits

- The avatar manager global and the local avatar chain are the ones [Shallow Water Diving](https://github.com/CowboyBingus/ShallowWaterDiving) by CowboyBingus reads; its working chain on this build confirmed the reading of the game's local avatar check.
- Uses research from [HD2Runtime](https://github.com/SkyeShade/HD2Runtime) by SkyeShade: `QueueStatusRequest` and `QueueDamage` (their addresses, arguments and queues), the status catalog's types and stored names, the VG-70 self-damage template, the limb actors and the engine actor lookup's slot and first bytes; `SetVelocity` and the motion map; the explosion catalogue's particle rows and packages, the shared explosion sound's event name, and the engine unit registry's layout. The mod's own checks of them against the game.dll and exe dumps are in the sections above.
- The status manager's map and zone masks follow the author's Helmet Passives Reborn (RESEARCH.md, "VITALS MONITOR: enemy health bars").
- Built on [Bingus Shared Loader](https://github.com/CowboyBingus/BingusSharedLoader), [Mod Bindings Menu](https://github.com/CowboyBingus/ModBindingsMenu) and [Mod Options Menu](https://github.com/CowboyBingus/ModOptionsMenu) by CowboyBingus; `src/bingus_text.lua` (his, Zero-Clause BSD) resolves the translations.

## Research tools

- `research/signatures.py`: generates the signatures from a game.dll dump, checks each matches exactly once, and writes them (with the shared signature engine) into the script; `--check` only verifies.
- `tests/test_release.py`: runs the built entry under LuaJIT against a game.dll dump (not included), with the local avatar chain, the status and health managers, the request queues, the game's functions, Mod Bindings Menu and Mod Options Menu simulated.
