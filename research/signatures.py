"""Self-Effects' code signatures: checked against the game.dll dump and written into self_effects.lua between the
SIGNATURES markers, with the shared signature engine (tools/sigscan.lua) between the SIGNATURE ENGINE markers.

Globals and offsets are read from the matched code (rip-relative operands, displacements); functions are found by
their own first instructions, or through a call to them. Optional signatures add a family of effects (statuses,
injuries) or log detail; the ragdoll needs only the required ones.

Usage (from the workspace root): python -B mods/SelfEffects/research/signatures.py [--check]
  --check   only verify: every signature matches once and the script's blocks are current (exit 1 otherwise)
"""
import sys
from pathlib import Path

MOD = Path(__file__).resolve().parents[1]
ROOT = MOD.parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import sigspec  # noqa: E402

SCRIPT = MOD / 'self_effects.lua'

AVATAR_MAP = {'avatars': (0x3326d20, 'rip'), 'avatar_cap': (0x100, 'u32'), 'avatar_mult': (0x108, 'u32'),
              'avatar_map': (0xf8, 'u32'), 'avatar_empty': (0x104, 'u32')}

SPECS = [
    # The game's "is this the local avatar" check (0xa40070): the players global, the local player's flag and unit,
    # the unit -> entity lookup, the "no entity" id, and the avatar manager's entity -> avatar index map.
    {'name': 'local_avatar', 'start': 0xa40076, 'end': 0xa40124,
     'fields': dict({'players': (0x3326468, 'rip'), 'local_active': (0x88, 'u32'), 'local_unit': (0x3a8, 'u32'),
                     'unit_entity': (0xfd9ba0, 'call'), 'no_entity': (0x3483c20, 'rip')}, **AVATAR_MAP)},
    # The unit -> entity lookup itself: the entity owner global, its unit map and the entity id array (in 8-byte
    # units: an entity's id is at owner + entity_ids * 8 + index * 24).
    {'name': 'unit_lookup', 'start': 0xfd9ba0, 'end': 0xfd9c5b,
     'fields': {'owner': (0x346bf98, 'rip'), 'no_unit': (0x7fff, 'u32'), 'unit_cap': (0xf22ed0, 'u32'),
                'unit_mult': (0xf22ed8, 'u32'), 'unit_map': (0xf22ec8, 'u32'), 'unit_empty': (0xf22ed4, 'u32'),
                'entity_ids': (0x1e65e4, 'u32')}},
    # A knockdown (0x833540): the avatar's ragdoll state (manager + ragdoll_state + index * stride), then the game's
    # own sequence: not ragdolled, allowed, start (state, no mode).
    {'name': 'knockdown', 'start': 0x833680, 'end': 0x8336b3,
     'fields': {'avatar_stride': (0x1238, 'u32'), 'ragdoll_state': (0x53dd48, 'u32'),
                'is_ragdolled': (0xa74700, 'call'), 'can_ragdoll': (0xa74850, 'call'),
                'start_ragdoll': (0xa75fa0, 'call')}},
    # The "is ragdolled" check (0xa74700) by its own body, through its test of bit 36 (0x24) of the avatar's flag
    # word (sibling checks differ only in that bit): the ragdoll state's entity id, the same avatar map, the flags.
    {'name': 'ragdoll_check', 'start': 0xa74700, 'end': 0xa747bf,
     'fields': dict({'state_entity': (0x398, 'u32'), 'no_entity': (0x3483c20, 'rip'), 'avatar_stride': (0x1238, 'u32'),
                     'flags': (0x53e888, 'u32')}, **AVATAR_MAP)},
    # The "can ragdoll" test (inside 0xa74850): the avatar's other flag word, read for the log when a ragdoll is refused.
    {'name': 'ragdoll_flags', 'start': 0xa748fa, 'end': 0xa7491e, 'optional': True,
     'fields': {'avatar_stride': (0x1238, 'u32'), 'flags': (0x53e888, 'u32'), 'state_bits': (0x53e880, 'u32')}},
    # --- Statuses (optional: without them the slots offer only the ragdoll and the injuries).
    # QueueStatusRequest(ignored, type, target, buildup, instigator, variant) (0x129F170), by its own body: the target
    # in the status manager's entity map (slots +0x12C0 {u32 entity, u32 index}, capacity +0x12C8, empty key +0x12CC,
    # multiplier +0x12D0), the "no entity" id, the game's susceptibility check (0x6994F0), then a 28-byte row appended
    # to the request queues (queue count at +0x201134, literal capacity 0x1000). RESEARCH.md, "Statuses".
    {'name': 'status_request', 'start': 0x129f170, 'end': 0x129f225, 'optional': True,
     'fields': {'status': (0x3326620, 'rip'), 'status_cap': (0x12c8, 'u32'), 'status_mult': (0x12d0, 'u32'),
                'status_slots': (0x12c0, 'u32'), 'status_empty': (0x12cc, 'u32'), 'queues': (0x347cf38, 'rip'),
                'no_entity': (0x3483c20, 'rip'), 'call_susceptible': (0x6994f0, 'call'),
                'status_count': (0x201134, 'u32')}},
    # has_status (0x69B1F0), its middle: the status settings table (a pointer per type to the type's 152-byte
    # StatusEffectInfo: +0 the type, +8 its name), then the entity's block (blocks +0x12E8, 0x1228 bytes each by the
    # map's index) whose 16-byte zone masks it tests. The mod checks each status's row before its first request and
    # reads the masks back for the log.
    {'name': 'status_table', 'start': 0x69b2e4, 'end': 0x69b35c, 'optional': True,
     'fields': {'status_settings': (0x37c5c50, 'rip'), 'status_stride': (0x1228, 'u32'),
                'status_blocks': (0x12e8, 'u32')}},
    # --- Injuries (optional: without them the slots offer only the ragdoll and the statuses).
    # QueueDamage(ignored, kind, element, target, damage, ...) (0x129F910), by its own start: the target in the health
    # manager's entity map (slots +0x1030, capacity +0x1038, empty key +0x103C, multiplier +0x1040), the same request
    # queues and "no entity" id, the damage queue's count (+0x201120, literal capacity 0x1000). RESEARCH.md, "Injuries".
    {'name': 'damage_request', 'start': 0x129f910, 'end': 0x129f9d5, 'optional': True,
     'fields': {'health': (0x3326688, 'rip'), 'health_cap': (0x1038, 'u32'), 'health_mult': (0x1040, 'u32'),
                'health_slots': (0x1030, 'u32'), 'health_empty': (0x103c, 'u32'), 'queues': (0x347cf38, 'rip'),
                'no_entity': (0x3483c20, 'rip'), 'damage_count': (0x201120, 'u32')}},
    # A health record lookup (0x659AB5): the same map, then the entity's record (records +0x1058, 0x1B8 bytes each)
    # and its descriptor (descriptors +0x1048: a pointer per index to {u64 type, u32 entity, u32 unit, u32 network id,
    # u32 flags}).
    {'name': 'health_record', 'start': 0x659ab5, 'end': 0x659b3e, 'optional': True,
     'fields': {'health': (0x3326688, 'rip'), 'health_cap': (0x1038, 'u32'), 'health_mult': (0x1040, 'u32'),
                'health_slots': (0x1030, 'u32'), 'health_empty': (0x103c, 'u32'), 'health_records': (0x1058, 'u32'),
                'health_stride': (0x1b8, 'u32'), 'health_descriptors': (0x1048, 'u32')}},
    # The engine's unit actor lookup as game.dll calls it (0x11ADC5C): the engine API global and the lookup's slot in
    # its table: lookup(unit, actor name, null) -> the actor handle (an exe function, checked by its first bytes).
    {'name': 'actor_lookup', 'start': 0x11adc5c, 'end': 0x11adc73, 'optional': True,
     'fields': {'unit_api': (0x3326310, 'rip'), 'actor_slot': (0x10, 'u8')}},
    # --- Launch (optional).
    # SetVelocity(ignored, entity, v) (0x4A7550), by its own start: the "no entity" id, the motion manager's entity map
    # (slots +0x48A0, capacity +0x48A8, empty key +0x48AC, multiplier +0x48B0), then the record it writes (records
    # +0x48C8, 0x84 bytes each, the velocity first). It writes index -1 for an entity missing from the map, so the mod
    # looks the entity up first. RESEARCH.md, "Launch".
    {'name': 'velocity', 'start': 0x4a7550, 'end': 0x4a7603, 'optional': True,
     'fields': {'no_entity': (0x3483c20, 'rip'), 'motion': (0x3326558, 'rip'), 'motion_cap': (0x48a8, 'u32'),
                'motion_mult': (0x48b0, 'u32'), 'motion_slots': (0x48a0, 'u32'), 'motion_empty': (0x48ac, 'u32'),
                'motion_records': (0x48c8, 'u32'), 'motion_stride': (0x84, 'u32')}},
    # --- Explode (optional). RESEARCH.md, "Explode".
    # The game state (`cmp [game + 0xAC21C], 4` in the hellpod launch's mission check: 3 on the ship, 4 in a mission).
    {'name': 'game_state', 'start': 0x11d5b23, 'end': 0x11d5b35, 'optional': True,
     'fields': {'game': (0x3326340, 'rip'), 'game_state': (0xac21c, 'u32')}},
    # The ragdoll start's position read (inside 0xA75FA0): the engine API global, its table at +0x18 and the slot
    # (+0x88) of the engine's world position(unit, node) (an exe function the mod checks by its bytes and then reads
    # the same way, without calling it).
    {'name': 'unit_position', 'start': 0xa76301, 'end': 0xa76344, 'optional': True,
     'fields': {'engine_api': (0x3326308, 'rip'), 'position_table': (0x18, 'u8'), 'position_slot': (0x88, 'u32')}},
]


def main():
    rows = sigspec.build(SPECS)
    sigspec.report(rows)
    if '--check' in sys.argv:
        problems = sigspec.check(SCRIPT, rows)
        for p in problems:
            print('STALE:', p)
        sys.exit(1 if problems else 0)
    sigspec.write(SCRIPT, rows)
    print('written to', SCRIPT.name)


if __name__ == '__main__':
    main()
