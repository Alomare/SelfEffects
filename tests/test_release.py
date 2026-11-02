"""Offline test of Self-Effects under LuaJIT, with the real game.dll code as fake process memory.

The Ghidra-ready dump (_research/game_25480438.dll, offsets == RVAs) is mapped at a fake base, so the signatures and
the values read from the matched code are checked against the game's own code; the local avatar chain (players,
entity owner, avatar manager), the status manager and its settings rows, the health manager, the request queues and
the engine's actor lookup are simulated on a fake heap, and the game's functions are stubs that record their calls.

Run from the workspace root:  python -B mods/SelfEffects/tests/test_release.py
"""
import re
import struct
import sys
import tempfile
from pathlib import Path

from lupa.luajit21 import LuaRuntime

MOD = Path(__file__).resolve().parent.parent
ROOT = MOD.parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(MOD / 'research'))
from entry import entry_text  # noqa: E402
import signatures  # noqa: E402
import sigspec  # noqa: E402

SOURCE = entry_text(MOD, 'self_effects.lua')
DUMP = (ROOT / '_research' / 'game_25480438.dll').read_bytes()

BASE, P, O, A, D1, D2 = 0x40000000, 0x20000000, 0x30000000, 0x50000000, 0x60000000, 0x61000000
S, SMAP, SBLOCKS, ROWS, NAMES, Q = 0x70000000, 0x71000000, 0x72000000, 0x73000000, 0x74000000, 0x75000000
H, HMAP, HDESC, DESC, HREC, API, LOOKUP = (0x76000000, 0x77000000, 0x78000000, 0x79000000, 0x7a000000, 0x7b000000,
                                           0x7c000000)
UNIT, IDX, ENTITY, AI, SIDX, HIDX, NETWORK, ACTOR = 0x123, 5, 0xABCD, 2, 3, 7, 0x41, 0x5150
ENGINE_UNIT = 0x2468  # the health descriptor's unit: the engine handle, not the players list's unit id
MULT1, MULT2, MULT3, MULT4 = 0x9E3779B1, 0x85EBCA6B, 0xC2B2AE35, 0x27D4EB2F
STRIDE, SSTRIDE, HSTRIDE = 0x1238, 0x1228, 0x1b8
LOOKUP_START = bytes.fromhex('48 89 6C 24 20 56 48 81 EC 80 00 00 00 49 8B F0 8B EA')
# The statuses the mod offers: type -> the name the game's settings row stores.
NAMES_BY_TYPE = {5: 'Fire', 38: 'Stun Medium', 42: 'Gas', 44: 'Gas_Confusion', 2: 'Bleed', 4: 'Confusion',
                 10: 'Acid Splash', 8: 'Slowed', 70: 'Poison', 9: 'Rooted', 14: 'Choked', 40: 'Stun Massive',
                 34: 'RadiationHeavy', 46: 'Inverted_Aim_Assist', 52: 'Tremor', 57: 'TornadoStun', 58: 'Dark Fluid',
                 63: 'Illuminate Scrambler', 68: 'Gloom', 32: 'BurningHeavy', 12: 'Thermite', 6: 'Lava'}
# Each key's list: Effect 1 and 3 the classics, Effect 2 the other statuses (choice numbers below).
CLASSICS_COUNT, STATUSES_COUNT = 14, 13
LAUNCH, EXPLODE, RADIATION, LAVA = 13, 14, 4, 13
# Launch and Explode: the motion manager, the game, and the engine's side (an API struct, its function table, the world position and unit object functions, the unit registry
# and its global, the generations, the objects, one unit object, its method table, its scene graph method, its poses).
MOT, MSLOTS, MREC, GAME = 0x80000000, 0x81000000, 0x82000000, 0x83000000
EAPI, ETAB, POSFN, OBJFN, REGG, REG, GENS, OBJS, OBJ, VT, GRAPHFN, POSES = (
    0x87000000, 0x88000000, 0x89000000, 0x8a000000, 0x8b000000, 0x8c000000, 0x8d000000, 0x8e000000, 0x8f000000,
    0x90000000, 0x91000000, 0x92000000)
MIDX, MULT5 = 9, 0x165667B1
POSITION = (12.5, -40.25, 3.0)
# The exe dump (the engine side): the world position function, the unit object lookup it calls, the scene graph
# method (rvas in helldivers2_25480438.exe; HD2Runtime pins the last one too).
EXE = (ROOT / '_research' / 'helldivers2_25480438.exe').read_bytes()
EXE_POSITION, EXE_UNIT_OBJECT, EXE_SCENE_GRAPH = 0x1fd190, 0x9d8c0, 0x2bd870
ZONES = {'l_knee': 4, 'r_hand': 3, 'chest': 1}


def mul32(a, b):
    return (a * b) & 0xffffffff


def map_blob(cap, mult, key, value):
    rows = [struct.pack('<II', 0xffffffff, 0)] * cap
    rows[mul32(key, mult) % cap] = struct.pack('<II', key, value)
    return b''.join(rows)


HARNESS = r'''
local logdir, image = ...
local real_ffi = require('ffi')
local ffi = real_ffi
local BASE = 0x40000000
fake = {menu = {}, calls = {}, ragdolled = false, allowed = true}
CowboyBingusModLoader = {api = 1, open_log = function(name)
    if type(name) ~= 'string' or not name:match('^[%w_-]+%.log$') then return nil end
    return io.open(logdir .. '/' .. name, 'w')
end}
local patches, heap = {}, {}
local function read_mem(a, n)
    if a >= BASE and a + n <= BASE + #image then
        local s = image:sub(a - BASE + 1, a - BASE + n)
        for _, p in ipairs(patches) do
            local lo, hi = math.max(a, p[1]), math.min(a + n, p[1] + #p[2])
            if lo < hi then s = s:sub(1, lo - a) .. p[2]:sub(lo - p[1] + 1, hi - p[1]) .. s:sub(hi - a + 1) end
        end
        return s
    end
    for k, v in pairs(heap) do
        if k <= a and a + n <= k + #v then return v:sub(a - k + 1, a - k + n) end
    end
end
fake.patch = function(rva, bytes) patches[#patches + 1] = {BASE + rva, bytes} end
fake.heap = function(a, bytes) heap[a] = bytes end
local k32 = {
    self_effects_GetCurrentProcess = function() return nil end,
    self_effects_GetModuleHandleA = function(name) return ffi.cast('void *', BASE) end,
    self_effects_ReadProcessMemory = function(p, addr, buf, size, got)
        local s = read_mem(tonumber(ffi.cast('uint64_t', addr)), tonumber(size))
        if not s then return 0 end
        ffi.copy(buf, s, #s); got[0] = #s; return 1
    end,
}
local function stub(kind, address)
    local rva = tonumber(address) - BASE
    if kind == 'status' then
        return function(ignored, ty, target, buildup, instigator, variant)
            fake.calls[#fake.calls + 1] = string.format('status %x %s %d %d %g %d %d', rva, tostring(ignored), ty,
                                                        target, buildup, instigator, variant)
            if fake.on_status then fake.on_status(ty) end
        end
    elseif kind == 'damage' then
        return function(ignored, kind_, element, target, damage, a6, dealer, owner, creditor, a10, f11, f12, f13,
                        direction, position, actor, a17, a18, f19)
            fake.calls[#fake.calls + 1] = string.format(
                'damage %x %s %d %d %d %d %d %d %d %s %d %g %g %g (%g %g %g) (%g %g %g) %d %d %d %g', rva,
                tostring(ignored), kind_, element, target, damage, a6, dealer, owner, tostring(creditor), a10, f11,
                f12, f13, direction[0], direction[1], direction[2], position[0], position[1], position[2], actor, a17,
                a18, f19)
            if fake.on_damage then fake.on_damage(damage) end
        end
    elseif kind == 'actor' then
        return function(unit, name, out)
            fake.calls[#fake.calls + 1] = string.format('actor %x %d 0x%x %s', rva, unit, name, tostring(out))
            return fake.actor or 0xFFFFFFFF
        end
    elseif kind == 'velocity' then
        return function(ignored, entity, v)
            fake.calls[#fake.calls + 1] = string.format('velocity %x %s %d (%g %g %g)', rva, tostring(ignored), entity,
                                                        v[0], v[1], v[2])
            if fake.on_velocity then fake.on_velocity(v[0], v[1], v[2]) end
        end
    end
    return function(state, mode)
        fake.calls[#fake.calls + 1] = string.format('%s %x 0x%x %s', kind, rva, tonumber(state), tostring(mode))
        if kind == 'start' then fake.ragdolled = true; if fake.on_start then fake.on_start() end; return end
        if kind == 'check' and rva == 0xa74700 then return fake.ragdolled and 1 or 0 end
        return fake.allowed and 1 or 0
    end
end
local KINDS = {SelfEffectsCheck = 'check', SelfEffectsStart = 'start', SelfEffectsStatus = 'status',
               SelfEffectsDamage = 'damage', SelfEffectsActor = 'actor', SelfEffectsVelocity = 'velocity'}
package.loaded.ffi = setmetatable({
    load = function(name) return k32 end,
    cast = function(t, v)
        if KINDS[t] then return stub(KINDS[t], v) end
        return real_ffi.cast(t, v)
    end}, {__index = real_ffi})
fake.bound, fake.labels, fake.categories = {}, {}, {}
ModBindingsMenu = {api = 1, register_binding = function(id, label, slot, o)
    fake.bound[#fake.bound + 1] = id .. '|' .. tostring(label) .. '|' .. tostring(slot) .. '|' .. tostring(o.category)
    fake.labels[id], fake.categories[id] = label, o.category
    return true end,
                   is_down = function(id) return fake.menu[id] or false end}
-- Mod Options Menu (installed by tests that set it): registrations, the applied values, callbacks.
fake.options, fake.values, fake.changed = {}, {}, {}
fake.option_menu = {api = 1, version = 3,
    register_option = function(id, spec) fake.options[id] = spec; return true end,
    get = function(id) return fake.values[id] end,
    on_change = function(id, fn) fake.changed[id] = fn; return true end}
-- The engine's Lua API for the blast: two worlds, the local Helldiver's unit in the second; particle and sound calls
-- recorded.
fake.blast = {loaded = true, sound = true, helldiver_at = {12.5, -40.25, 3.0}}
local worlds = {'ship', 'mission'}
stingray = {
    Application = {worlds = function() return worlds end,
                   can_get = function(kind, name) return kind == 'particles' and fake.blast.loaded
                                                     and name.hex == '6d2bad783480d272' end},
    IdString64 = {from_hex = function(h) return {hex = h} end},
    World = {units_by_resource = function(world, name)
                 if world == 'mission' and name.hex == '4d1c334d294dfa97' then return {helldiver = 'helldiver'} end
                 return {}
             end,
             create_particles = function(world, name, position, rotation)
                 fake.calls[#fake.calls + 1] = string.format('particles %s %s (%g %g %g) %s', world, name.hex,
                                                             position.x, position.y, position.z, rotation)
                 return 1
             end},
    Unit = {alive = function(u) return true end,
            world_position = function(u, node)
                local p = fake.blast.helldiver_at
                return {x = p[1], y = p[2], z = p[3]}
            end},
    Vector3 = function(x, y, z) return {x = x, y = y, z = z} end,
    Quaternion = {identity = function() return 'identity' end},
    Wwise = {has_event = function(name) return fake.blast.sound and name == 'hd2runtime_0wyiw_n' end,
             wwise_world = function(world) return 'wwise:' .. world end},
    WwiseWorld = {trigger_event = function(ww, name, position)
        fake.calls[#fake.calls + 1] = string.format('sound %s %s (%g %g %g)', ww, name, position.x, position.y,
                                                    position.z)
    end},
}
function fake.press(id) fake.menu[id] = true; update(0.016); fake.menu[id] = false; update(0.016) end
'''

KEY1, KEY2, KEY3 = 'alomare.ragdoll_on_command.ragdoll', 'alomare.self_effects.effect_2', 'alomare.self_effects.effect_3'


class World:
    """The game's state on the fake heap, and the side effects of the game's functions."""

    def __init__(self, lua):
        self.lua, self.f = lua, lua.globals().fake
        f = self.f
        # The players global -> players: local active, local unit.
        f.patch(0x3326468, struct.pack('<Q', P))
        self.players = bytearray(0x400)
        struct.pack_into('<I', self.players, 0x88, 1)
        struct.pack_into('<I', self.players, 0x3a8, UNIT)
        f.heap(P, bytes(self.players))
        # The entity owner: unit map header (+0xf22ec8 data, +0xf22ed0 cap, +0xf22ed4 empty, +0xf22ed8 mult), ids.
        f.patch(0x346bf98, struct.pack('<Q', O))
        f.heap(O + 0xf22ec8, struct.pack('<QIII', D1, 16, 0xffffffff, MULT1) + b'\0' * 8)
        f.heap(D1, map_blob(16, MULT1, UNIT, IDX))
        f.heap(O + 0xf32f20 + IDX * 24, struct.pack('<I', ENTITY) + b'\0' * 20)
        # The avatar manager: its map (+0xf8 data, +0x100 cap, +0x104 empty, +0x108 mult), ragdoll state, flags.
        f.patch(0x3326d20, struct.pack('<Q', A))
        f.heap(A + 0xf8, struct.pack('<QIII', D2, 8, 0xffffffff, MULT2) + b'\0' * 8)
        f.heap(D2, map_blob(8, MULT2, ENTITY, AI))
        self.state = A + 0x53dd48 + AI * STRIDE
        f.heap(self.state + 0x398, struct.pack('<I', ENTITY))
        self.flags_at = A + 0x53e880 + AI * STRIDE
        f.heap(self.flags_at, struct.pack('<QQ', 0x4, 0))
        lua.execute('function fake.on_start() fake.heap(%d, string.char(4,0,0,0,0,0,0,0) .. '
                    'string.char(0,0,0,0,0x10,0,0,0)) end' % self.flags_at)
        # The status manager: its map (+0x12c0 slots, +0x12c8 cap, +0x12cc empty, +0x12d0 mult), blocks (+0x12e8).
        f.patch(0x3326620, struct.pack('<Q', S))
        f.heap(S + 0x12c0, struct.pack('<QIII', SMAP, 8, 0xffffffff, MULT3) + b'\0' * 20 + struct.pack('<Q', SBLOCKS))
        f.heap(SMAP, map_blob(8, MULT3, ENTITY, SIDX))
        self.masks = bytearray(128)
        self.write_masks()
        # The status settings table: a pointer per type to {type, name pointer}.
        self.rows = {}
        for ty, name in NAMES_BY_TYPE.items():
            self.set_row(ty, ty, name)
        # The request queues: the damage count (+0x201120) and the status count (+0x201134).
        f.patch(0x347cf38, struct.pack('<Q', Q))
        self.counts = {'damage': 0, 'status': 0}
        self.write_counts()
        self.accept_status = True
        f.on_status = self.on_status
        # The health manager: its map (+0x1030 slots, +0x1038 cap, +0x103c empty, +0x1040 mult), descriptors
        # (+0x1048: a pointer per index), records (+0x1058, 0x1b8 bytes each).
        f.patch(0x3326688, struct.pack('<Q', H))
        f.heap(H + 0x1030, struct.pack('<QIIIIQQQ', HMAP, 16, 0xffffffff, MULT4, 0, HDESC, 0, HREC))
        f.heap(HMAP, map_blob(16, MULT4, ENTITY, HIDX))
        f.heap(HDESC + HIDX * 8, struct.pack('<Q', DESC))
        self.set_descriptor()
        self.record = bytearray(HSTRIDE)
        struct.pack_into('<i', self.record, 0x14, 150)
        struct.pack_into('<Q', self.record, 0x38, 0x1122334455667788)
        for zone, hp in enumerate((85, 60, 35, 35, 45, 45)):
            struct.pack_into('<i', self.record, 0xf8 + 4 * zone, hp)
        self.write_record()
        f.on_damage = self.on_damage
        # The engine API table: slot +0x10 holds the actor lookup, whose first bytes the mod checks.
        f.patch(0x3326310, struct.pack('<Q', API))
        f.heap(API + 0x10, struct.pack('<Q', LOOKUP))
        f.heap(LOOKUP, LOOKUP_START + b'\0' * 14)
        f.actor = ACTOR
        # The motion manager: its map (+0x48a0 slots, +0x48a8 cap, +0x48ac empty, +0x48b0 mult), records (+0x48c8,
        # 0x84 bytes each, the velocity first). SetVelocity writes the record.
        f.patch(0x3326558, struct.pack('<Q', MOT))
        f.heap(MOT + 0x48a0, struct.pack('<QIII', MSLOTS, 16, 0xffffffff, MULT5) + b'\0' * 20 + struct.pack('<Q', MREC))
        f.heap(MSLOTS, map_blob(16, MULT5, ENTITY, MIDX))
        self.velocity((1.0, 2.0, -0.5))
        f.on_velocity = lambda x, y, z: self.velocity((x, y, z))
        # The game state (4 in a mission).
        f.patch(0x3326340, struct.pack('<Q', GAME))
        self.game_state(4)
        # The engine: the API struct (+0x18: a function table), the world position at +0x88 of it, which calls the
        # unit object lookup, whose global points at the registry: count +0x98, generations +0xa0, objects +0x88.
        # The functions are the exe's own bytes, their rel32 operands moved to the fake addresses.
        f.patch(0x3326308, struct.pack('<Q', EAPI))
        f.heap(EAPI, b'\0' * 0x18 + struct.pack('<Q', ETAB))
        f.heap(ETAB, b'\0' * 0x88 + struct.pack('<Q', POSFN))
        code = bytearray(EXE[EXE_POSITION:EXE_POSITION + 0x33])
        struct.pack_into('<i', code, 10, OBJFN - (POSFN + 14))
        self.position_code = bytes(code)
        f.heap(POSFN, self.position_code)
        code = bytearray(EXE[EXE_UNIT_OBJECT:EXE_UNIT_OBJECT + 0x58])
        struct.pack_into('<i', code, 18, REGG - (OBJFN + 22))
        f.heap(OBJFN, bytes(code))
        f.heap(REGG, struct.pack('<Q', REG))
        index = ENGINE_UNIT & 0x3fffff
        f.heap(REG + 0x88, struct.pack('<QQIIQ', OBJS, 0, index + 1, 0, GENS))
        self.generation(ENGINE_UNIT >> 22)
        f.heap(OBJS + index * 8, struct.pack('<Q', OBJ))
        obj = bytearray(0x90)
        struct.pack_into('<QI', obj, 0, VT, ENGINE_UNIT)
        struct.pack_into('<Q', obj, 0x60 + 0x28, POSES)
        f.heap(OBJ, bytes(obj))
        f.heap(VT, b'\0' * 0xe8 + struct.pack('<Q', GRAPHFN))
        f.heap(GRAPHFN, EXE[EXE_SCENE_GRAPH:EXE_SCENE_GRAPH + 5])
        f.heap(POSES, b'\0' * 0x30 + struct.pack('<fff', *POSITION))

    def velocity(self, v):
        self.f.heap(MREC + MIDX * 0x84, struct.pack('<fff', *v))

    def game_state(self, state):
        self.f.heap(GAME + 0xac21c, struct.pack('<I', state))

    def generation(self, g):
        self.f.heap(GENS + (ENGINE_UNIT & 0x3fffff), bytes([g]))

    def set_row(self, ty, held, name):
        row, text = ROWS + ty * 0x10, NAMES + ty * 0x40
        self.f.patch(0x37c5c50 + ty * 8, struct.pack('<Q', row))
        self.f.heap(row, struct.pack('<IIQ', held, 0, text))
        self.f.heap(text, name.encode() + b'\0' * (0x40 - len(name)))

    def set_descriptor(self, entity=ENTITY, unit=ENGINE_UNIT, network=NETWORK, flags=1):
        self.f.heap(DESC, struct.pack('<QIIII', 0x4D1C334D294DFA97, entity, unit, network, flags))

    def write_masks(self):
        self.f.heap(SBLOCKS + SIDX * SSTRIDE, bytes(self.masks))

    def write_counts(self):
        self.f.heap(Q + 0x201120, struct.pack('<I', self.counts['damage']) + b'\0' * 16
                    + struct.pack('<I', self.counts['status']) + b'\0' * 8)

    def write_record(self):
        self.f.heap(HREC + HIDX * HSTRIDE, bytes(self.record))

    def set_status(self, ty, on, zone=2):
        byte = zone * 16 + ty // 8
        if on:
            self.masks[byte] |= 1 << (ty % 8)
        else:
            self.masks[byte] &= ~(1 << (ty % 8)) & 0xff
        self.write_masks()

    def on_status(self, ty):
        if self.accept_status:
            self.counts['status'] += 1
            self.write_counts()

    def on_damage(self, damage):
        self.counts['damage'] += 1
        self.write_counts()

    def zone(self, zone, hp):
        struct.pack_into('<i', self.record, 0xf8 + 4 * zone, hp)
        self.write_record()


def runtime(options=None, version=None, extended=False):
    logdir = Path(tempfile.mkdtemp())
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute(HARNESS, str(logdir), DUMP)
    w = World(lua)
    if version:
        lua.execute('ModBindingsMenu.version = %d' % version)
    if extended:  # Mod Bindings Menu v2.3 with every native action held: the keys become extended bindings
        lua.execute("ModBindingsMenu.binding_info = function(id) return {backend = 'extended', state = 'default'} end")
    if options is not None:
        for key, value in options.items():
            lua.execute("fake.values['%s'] = %d" % (key, value))
        lua.execute('ModOptionsMenu = fake.option_menu')
    lua.execute(SOURCE)
    lua.execute('for i = 1, 5 do update(0.016) end')
    log = lambda: (logdir / 'SelfEffects.log').read_text()
    status = lambda: (logdir / 'SelfEffects_STATUS.log').read_text()
    return lua, w, log, status


def calls(f, prefix=None):
    out = list(f.calls.values())
    return [c for c in out if c.startswith(prefix)] if prefix else out


def run():
    ok = []

    def check(cond, what):
        ok.append(bool(cond))
        print('PASS' if cond else 'FAIL', what)

    check(not sigspec.check(signatures.SCRIPT, sigspec.build(signatures.SPECS)),
          "the script's signature blocks match research/signatures.py")
    # The Windows functions are declared under the mod's own names: another mod's declarations of the bare names,
    # with other types, would otherwise take over every call (One Click Armor Set's VirtualQuery report).
    check(not re.search(r'\b(GetCurrentProcess|GetModuleHandleA|ReadProcessMemory|WriteProcessMemory)\(', SOURCE)
          and 'self_effects_ReadProcessMemory(void *process' in SOURCE and '__asm__("ReadProcessMemory")' in SOURCE,
          "Windows functions under the mod's own names (self_effects_..., bound to the real exports)")

    # --- Without Mod Options Menu: the keys are Ragdoll, Fire and Stun.
    lua, w, log, status = runtime()
    f = w.f
    M = lua.globals().SelfEffects
    check(M.ready, 'ready: every signature at its rva, values read')
    check('Effects (status): available' in log() and 'Effects (injury): available' in log(),
          'both effect families available')
    check('Ready: avatar state = avatars + 0x53dd48 + index * 0x1238, entity at +0x398' in log(), 'offsets from code')
    a = lua.eval('SelfEffects._test.local_avatar()')
    check(a and a.state == w.state and a.entity == ENTITY and a.unit == UNIT and a.index == AI,
          'local avatar chain resolves the state')
    bound = list(f.bound.values())
    check(bound == ['%s|Effect %d: %s|nil|Self-Effects' % (k, i, e) for i, (k, e) in
                    enumerate(((KEY1, 'Ragdoll'), (KEY2, 'Rooted'), (KEY3, 'Stun')), 1)],
          'three keys registered, Effect 1 under the Ragdoll key\'s old id: %r' % bound)
    check(status().startswith('OK - set the Effect keys in Options > Controls > MODS\n'),
          'status OK: %r' % status().splitlines()[0])
    status_x = runtime(extended=True)[3]
    check(status_x().startswith('OK - set the Effect keys in Options > Controls > MORE MODS\n'),
          'keys made extended bindings (native pool full): the status names MORE MODS: %r' % status_x().splitlines()[0])

    # Effect 1: the ragdoll, the game's sequence on the local state.
    lua.execute("fake.press('%s')" % KEY1)
    st = w.state
    check(calls(f) == ['check a74700 0x%x nil' % st, 'check a74850 0x%x nil' % st, 'start a75fa0 0x%x 0' % st,
                       'check a74700 0x%x nil' % st], 'Effect 1 (Ragdoll): check, allowed, start, check: %r'
          % calls(f))
    check('Effect 1 key: ragdoll' in log() and 'Ragdolled' in log(), 'logged as ragdolled')
    lua.execute('fake.heap(%d, string.rep("\\0", 16)); for i = 1, 30 do update(0.016) end' % w.flags_at)
    check('Ragdoll ended after' in log(), 'the end is logged')
    lua.execute('fake.allowed = false; fake.ragdolled = false')
    lua.execute("fake.press('%s')" % KEY1)
    check('Ragdoll: not allowed right now (flags 0000000000000000, state bits 0000000000000000)' in log(),
          'refusal logged')
    lua.execute('fake.allowed = true; fake.calls = {}')

    # Effect 2: rooted, one request on the local Helldiver as target and instigator, buildup 1000, variant 0.
    lua.execute("fake.press('%s')" % KEY2)
    check(calls(f) == ['status 129f170 nil 9 %d 1000 %d 0' % (ENTITY, ENTITY)],
          'Effect 2 (Rooted): QueueStatusRequest(nil, 9, Helldiver, 1000, Helldiver, 0): %r' % calls(f))
    check('Status 9 (Rooted): settings row checked' in log()
          and 'rooted: status 9 (Rooted) requested (it was off)' in log(), 'the settings row checked, the request logged')
    w.set_status(9, True)
    lua.execute('for i = 1, 20 do update(0.016) end')
    w.set_status(9, False)
    lua.execute('for i = 1, 20 do update(0.016) end')
    check(re.search(r'rooted: Rooted on after 0\.\d s', log())
          and re.search(r'rooted: Rooted ended after \d\.\d s', log()),
          'the status read back from the masks: on, then ended')
    # Refused by the game (its susceptibility check: the queue count doesn't move).
    w.accept_status = False
    lua.execute("fake.calls = {}; fake.press('%s')" % KEY2)
    check(len(calls(f, 'status')) == 1 and 'rooted: status 9 (Rooted) refused by the game' in log(),
          'a request the game drops is logged as refused')
    lua.execute('for i = 1, 300 do update(0.016) end')
    w.accept_status = True
    # A settings row that holds another type, or another name: no request.
    w.set_row(38, 39, 'Stun Large')
    lua.execute("fake.calls = {}; fake.press('%s')" % KEY3)
    check(not calls(f, 'status') and 'stun: status 38 not requested: settings row holds type 39' in log(),
          'a settings row of another type: no request')
    w.set_row(38, 38, 'Stun Large')
    lua.execute("fake.press('%s')" % KEY3)
    check(not calls(f, 'status') and 'stun: status 38 not requested: settings row named "Stun Large"' in log(),
          'a settings row with another name: no request')
    w.set_row(38, 38, 'Stun Medium')
    lua.execute("fake.press('%s')" % KEY3)
    check(calls(f, 'status') == ['status 129f170 nil 38 %d 1000 %d 0' % (ENTITY, ENTITY)],
          'Effect 3 (Stun): the catalogued row, one request')
    lua.execute('for i = 1, 300 do update(0.016) end')
    check('stun: Stun Medium never showed in 3 s' in log(), 'a status that never shows is logged')
    # The queue full: no request.
    w.counts['status'] = 0x1000
    w.write_counts()
    lua.execute("fake.calls = {}; fake.press('%s')" % KEY2)
    check(not calls(f, 'status') and 'not requested: the queue is full' in log(), 'a full queue: no request')
    w.counts['status'] = 0
    w.write_counts()

    # No Helldiver, or a state of another entity: nothing called.
    w.players[0x3a8:0x3ac] = struct.pack('<I', 0x7fff)
    f.heap(P, bytes(w.players))
    lua.execute("fake.calls = {}; fake.press('%s'); fake.press('%s')" % (KEY1, KEY2))
    check(not calls(f) and 'Effect 1 key (ragdoll): no Helldiver (no unit)' in log()
          and 'Effect 2 key (rooted): no Helldiver (no unit)' in log(), 'no Helldiver: nothing called')
    w.players[0x3a8:0x3ac] = struct.pack('<I', UNIT)
    f.heap(P, bytes(w.players))
    f.heap(w.state + 0x398, struct.pack('<I', ENTITY + 1))
    lua.execute("fake.press('%s')" % KEY1)
    check(not calls(f) and 'ragdoll state names another entity' in log(), 'state of another entity: nothing called')
    f.heap(w.state + 0x398, struct.pack('<I', ENTITY))

    # --- Mod Options Menu: a list per key (at most 16, the game's selector limit); Effect 1 set to the leg, Effect 2 to
    # radiation, Effect 3 to the arm.
    lua, w, log, status = runtime({'alomare.self_effects.effect_1': 10, 'alomare.self_effects.effect_2': RADIATION,
                                   'alomare.self_effects.effect_3': 11}, version=3)
    f = w.f
    o = f.options['alomare.self_effects.effect_1']
    o2, o3 = f.options['alomare.self_effects.effect_2'], f.options['alomare.self_effects.effect_3']
    names = [o.choices[i]() for i in range(1, len(o.choices) + 1)]
    names2 = [o2.choices[i]() for i in range(1, len(o2.choices) + 1)]
    check(o.type == 'choice' and o.mod_id == 'alomare.self_effects' and o.default == 1 and o.label() == 'Effect 1'
          and o.mod() == 'Self-Effects' and names[0] == 'Ragdoll'
          and names[9:12] == ['Injured Leg', 'Injured Arm', 'Injured Chest'] and names[-2:] == ['Launch', 'Explode']
          and len(names) == CLASSICS_COUNT and names2[0] == 'Rooted'
          and names2[-3:] == ['Napalm Fire', 'Thermite', 'Lava'] and len(names2) == STATUSES_COUNT
          and [o3.choices[i]() for i in range(1, len(o3.choices) + 1)] == names
          and o2.default == 1 and o3.default == 3,
          'three choice options: the classics (%d), the statuses (%d), the classics; defaults Ragdoll / Rooted / Stun: '
          '%r %r' % (CLASSICS_COUNT, STATUSES_COUNT, names, names2))
    check(all(len(x.choices) <= 16 for x in (o, o2, o3)), 'no list over 16 choices (Mod Options Menu refuses those)')
    # Every status effect's catalogued row is checked and requested (the survey effects included).
    for slot, key, listed in ((1, KEY1, names), (2, KEY2, names2)):
        for k in range(1, len(listed) + 1):
            lua.execute("fake.changed['alomare.self_effects.effect_%d'](%d)" % (slot, k))
            kind = lua.eval("SelfEffects._test.effect(%d).kind" % slot)
            if kind == 'status':
                lua.execute("fake.calls = {}; fake.press('%s')" % key)
                check(calls(f, 'status') and all(' 1000 ' in c for c in calls(f, 'status')),
                      'Effect %d choice %d (%s): requested: %r' % (slot, k, listed[k - 1], calls(f, 'status')))
    lua.execute("fake.changed['alomare.self_effects.effect_1'](10); fake.changed['alomare.self_effects.effect_2'](%d);"
                " for i = 1, 400 do update(0.016) end" % RADIATION)
    check('Effect 1 set to leg' in log() and 'Effect 2 set to radiation' in log(), 'the saved choices are read')
    check(f.labels[KEY1]() == 'Effect 1: Injured Leg' and f.labels[KEY3]() == 'Effect 3: Injured Arm'
          and f.categories[KEY2]() == 'Self-Effects',
          'v2.1 bindings: labels are functions that name the chosen effect')
    # Gas: two requests (gas, gas confusion).
    lua.execute("fake.changed['alomare.self_effects.effect_1'](4); fake.calls = {}; fake.press('%s')" % KEY1)
    check(calls(f, 'status') == ['status 129f170 nil %d %d 1000 %d 0' % (ty, ENTITY, ENTITY) for ty in (42, 44)],
          'Gas: two requests, gas then gas confusion: %r' % calls(f, 'status'))
    lua.execute("fake.changed['alomare.self_effects.effect_1'](10)")
    # The leg: one damage request at the left knee's actor, for the zone's remaining health.
    lua.execute("fake.calls = {}; fake.press('%s')" % KEY1)
    damage = calls(f, 'damage')
    expect = ('damage 129f910 nil 6 0 %d 45 1 %d %d 1234605616436508552ULL 0 0 0 0 (0 0 -1) (0 0 0) %d 9 0 1'
              % (ENTITY, NETWORK, NETWORK, ACTOR))
    check(calls(f, 'actor') == ['actor %x %d 0x8fd2dfec nil' % (LOOKUP - BASE, ENGINE_UNIT)] and damage == [expect],
          "Injured Leg: the actor lookup on the descriptor's unit, then QueueDamage with the VG-70 template: %r"
          % damage)
    w.zone(4, 0)
    lua.execute('for i = 1, 20 do update(0.016) end')
    check(re.search(r'leg: after \d\.\d s, zone 4 health 45 -> 0', log()), 'the injury read back from the record')
    lua.execute("fake.calls = {}; fake.press('%s')" % KEY1)
    check(not calls(f) and 'leg: l_knee already injured (zone health 0' in log(), 'an injured limb: no request')
    # The arm, partly damaged: the remaining zone health only.
    w.zone(3, 20)
    lua.execute("fake.press('%s')" % KEY3)
    check(re.match(r'damage 129f910 nil 6 0 \d+ 20 ', (calls(f, 'damage') or [''])[0]), 'a damaged arm: 20, its rest')
    # Refusals: downed, no engine unit, not owned, no actor, a changed actor lookup.
    w.zone(3, 35)
    struct.pack_into('<I', w.record, 0x19c, 1)
    w.write_record()
    lua.execute("fake.calls = {}; fake.press('%s')" % KEY3)
    check(not calls(f) and 'arm: not while downed' in log(), 'downed: no request')
    struct.pack_into('<I', w.record, 0x19c, 0)
    w.write_record()
    w.set_descriptor(unit=0)
    lua.execute("fake.press('%s')" % KEY3)
    check(not calls(f) and 'arm: the Helldiver has no engine unit' in log(), 'no engine unit: no request')
    w.set_descriptor(flags=0)
    lua.execute("fake.press('%s')" % KEY3)
    check(not calls(f) and 'arm: this machine does not own the Helldiver' in log(), 'not owned: no request')
    w.set_descriptor()
    lua.execute("fake.actor = nil; fake.press('%s')" % KEY3)
    check(not calls(f, 'damage') and 'arm: the Helldiver has no r_hand actor now' in log(), 'no actor: no request')
    lua.execute('fake.actor = %d' % ACTOR)
    f.heap(LOOKUP, b'\xcc' + LOOKUP_START[1:] + b'\0' * 14)
    lua.execute("fake.calls = {}; fake.press('%s')" % KEY3)
    check(not calls(f) and 'arm: the engine actor lookup changed' in log(), 'a changed engine lookup: not called')
    # A choice changed in the menu applies at once.
    lua.execute("fake.changed['alomare.self_effects.effect_3'](1); fake.ragdolled = false; fake.calls = {}")
    lua.execute("fake.press('%s')" % KEY3)
    check(calls(f, 'start') and 'Effect 3 set to ragdoll' in log(), 'Effect 3 changed to Ragdoll: the key ragdolls')

    # --- Launch and Explode (Effect 1 and Effect 2).
    patterns = dict(re.findall(r"local (POSITION_CODE|UNIT_OBJECT_CODE|SCENE_GRAPH_CODE) = ('[^\n]*'(?:\n *\.\. '[^\n]*')*)",
                               SOURCE))
    exe_at = {'POSITION_CODE': EXE_POSITION, 'UNIT_OBJECT_CODE': EXE_UNIT_OBJECT, 'SCENE_GRAPH_CODE': EXE_SCENE_GRAPH}
    for name, text in patterns.items():
        hexes = ''.join(re.findall(r"'([^']*)'", text)).split()
        at = exe_at[name]
        check(len(hexes) > 4 and all(h == '??' or int(h, 16) == EXE[at + k] for k, h in enumerate(hexes)),
              "%s matches the exe dump's code at 0x%x (%d bytes)" % (name, at, len(hexes)))
    check(len(patterns) == 3, 'the three engine code patterns found in the script')
    lua, w, log, status = runtime({'alomare.self_effects.effect_1': LAUNCH, 'alomare.self_effects.effect_2': LAVA,
                                   'alomare.self_effects.effect_3': EXPLODE}, version=3)
    f = w.f
    check('Effects (launch): available' in log() and 'Effects (explode): available' in log(),
          'the Launch and Explode families available')
    check(f.labels[KEY1]() == 'Effect 1: Launch' and f.labels[KEY2]() == 'Effect 2: Lava'
          and f.labels[KEY3]() == 'Effect 3: Explode', 'labels: Launch, Lava, Explode')
    # Launch: the current velocity plus 14 m/s up, through SetVelocity on the Helldiver.
    lua.execute("fake.calls = {}; fake.press('%s')" % KEY1)
    check(calls(f) == ['velocity 4a7550 nil %d (1 2 13.5)' % ENTITY],
          'Launch: SetVelocity(nil, Helldiver, current + (0, 0, 14)): %r' % calls(f))
    check('launch: velocity (1.0, 2.0, -0.5) -> (1.0, 2.0, 13.5), read back (1.0, 2.0, 13.5)' in log(),
          'the velocity read back')
    lua.execute('for i = 1, 120 do update(0.016) end')
    check(re.search(r'launch: vertical velocity every 10 frames: 13\.5( 13\.5)+', log()), 'the vertical velocity watched')
    # Too fast afterwards, or a Helldiver missing from the motion map: not called.
    w.velocity((0.0, 0.0, 40.0))
    lua.execute("fake.calls = {}; fake.press('%s')" % KEY1)
    check(not calls(f) and 'launch: not now, the Helldiver would move at 54.0 m/s' in log(), 'too fast: not called')
    w.velocity((0.0, 0.0, 0.0))
    f.heap(MSLOTS, map_blob(16, MULT5, ENTITY + 1, MIDX))
    lua.execute("fake.press('%s')" % KEY1)
    check(not calls(f) and 'launch: not in the motion map (not in map)' in log(), 'no motion record: not called')
    # Explode: on the ship, refused.
    w.game_state(3)
    lua.execute("fake.press('%s')" % KEY3)
    check(not calls(f) and 'explode: only in a mission' in log(), 'Explode on the ship: not requested')
    w.game_state(4)
    # A changed engine function, a unit the engine no longer has, a full damage queue: nothing.
    f.heap(POSFN, b'\xcc' + w.position_code[1:])
    lua.execute("fake.press('%s')" % KEY3)
    check(not calls(f) and 'explode: the engine world position changed' in log(), 'a changed engine function: refused')
    f.heap(POSFN, w.position_code)
    w.generation((ENGINE_UNIT >> 22) + 1)
    lua.execute("fake.press('%s')" % KEY3)
    check(not calls(f) and 'explode: the engine unit is gone' in log(), 'a stale engine unit: refused')
    w.generation(ENGINE_UNIT >> 22)
    w.counts['damage'] = 0x1000
    w.write_counts()
    lua.execute("fake.press('%s')" % KEY3)
    check(not calls(f) and 'explode: the damage queue is full' in log(), 'a full damage queue: refused')
    w.counts['damage'] = 0
    w.write_counts()
    # The kill: one hit on the Helldiver alone at no actor, pushing up from its position; then the blast this machine
    # shows (particles, sound) in the world where the Helldiver is.
    lua.execute("fake.press('%s')" % KEY3)
    hit = ('damage 129f910 nil 6 0 %d 5000 1 %d %d 1234605616436508552ULL 0 200 0 0 (0 0 1) (%g %g %g) 4294967295 9 0 1'
           % ((ENTITY, NETWORK, NETWORK) + POSITION))
    check(calls(f) == [hit, 'particles mission 6d2bad783480d272 (%g %g %g) identity' % POSITION,
                       'sound wwise:mission hd2runtime_0wyiw_n (%g %g %g)' % POSITION],
          'Explode: QueueDamage(5000, no actor, push 200 up) on the Helldiver, then particles and sound: %r' % calls(f))
    check('explode: 5000 damage at no actor (Helldiver health 150, life state 0) requested' in log()
          and 'explode: blast at (12.5, -40.2, 3.0): particles, sound' in log()
          and log().index('first particles call') < log().index('blast at'), 'the hit and the blast logged')
    struct.pack_into('<i', w.record, 0x14, 0)
    struct.pack_into('<I', w.record, 0x19c, 2)
    w.write_record()
    lua.execute('for i = 1, 20 do update(0.016) end')
    check(re.search(r'explode: after 0\.\d s, Helldiver health 150 -> 0, life state 0 -> 2', log()),
          'the outcome read back from the health record')
    lua.execute("fake.calls = {}; fake.press('%s')" % KEY3)
    check(not calls(f) and 'explode: not while dead' in log(), 'dead: not requested')
    struct.pack_into('<i', w.record, 0x14, 150)
    struct.pack_into('<I', w.record, 0x19c, 0)
    w.write_record()
    # Particles or sound not loaded, or no world with the Helldiver there: the kill still, without that part.
    lua.execute("fake.blast.loaded = false; fake.blast.sound = false; fake.calls = {}; fake.press('%s')" % KEY3)
    check(calls(f) == [hit] and 'explode: blast at (12.5, -40.2, 3.0): particles not loaded, sound not loaded' in log(),
          'nothing loaded: the hit only: %r' % calls(f))
    lua.execute("fake.blast.loaded = true; fake.blast.sound = true; fake.blast.helldiver_at = {30, 0, 0}")
    lua.execute("fake.calls = {}; fake.press('%s')" % KEY3)
    check(calls(f) == [hit] and 'blast at (12.5, -40.2, 3.0): no world with the Helldiver at that position' in log(),
          'no Helldiver unit at the position: no blast')

    # --- Without the status code: the family is off, the ragdoll still works.
    logdir = Path(tempfile.mkdtemp())
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute(HARNESS, str(logdir), DUMP)
    w = World(lua)
    w.f.patch(0x129f170, b'\xcc' * 16)
    lua.execute(SOURCE)
    lua.execute('for i = 1, 400 do update(0.016) end')
    text = (logdir / 'SelfEffects.log').read_text()
    check(lua.globals().SelfEffects.ready and 'Effects (status): code not found: status_request' in text
          and 'status effects unavailable' in (logdir / 'SelfEffects_STATUS.log').read_text(),
          'status code missing: statuses off, the rest ready, the status line says so')
    lua.execute("fake.press('%s')" % KEY2)
    check(not calls(w.f, 'status') and 'rooted: statuses unavailable' in (logdir / 'SelfEffects.log').read_text(),
          'a status key without the status code: nothing called')

    print('%d/%d' % (sum(ok), len(ok)))
    return all(ok)


if __name__ == '__main__':
    sys.exit(0 if run() else 1)
