"""Ragdoll On Command's code signatures: checked against the game.dll dump and written into ragdoll_on_command.lua
between the SIGNATURES markers, with the shared signature engine (tools/sigscan.lua) between the SIGNATURE ENGINE
markers.

Globals and offsets are read from the matched code (rip-relative operands, displacements); functions are found by
their own first instructions, or through a call to them. The optional signature only adds log detail.

Usage (from the workspace root): python -B mods/RagdollOnCommand/research/signatures.py [--check]
  --check   only verify: every signature matches once and the script's blocks are current (exit 1 otherwise)
"""
import sys
from pathlib import Path

MOD = Path(__file__).resolve().parents[1]
ROOT = MOD.parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import sigspec  # noqa: E402

SCRIPT = MOD / 'ragdoll_on_command.lua'

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
