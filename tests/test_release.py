"""Offline test of Ragdoll On Command under LuaJIT, with the real game.dll code as fake process memory.

The Ghidra-ready dump (_research/game_25480438.dll, offsets == RVAs) is mapped at a fake base, so the signatures and
the values read from the matched code are checked against the game's own code; the local avatar chain (players,
entity owner, avatar manager) is simulated on a fake heap, and the game's three ragdoll functions are stubs that
record their calls.

Run from the mod folder:  python -B tests/test_release.py
"""
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

SOURCE = entry_text(MOD, 'ragdoll_on_command.lua')
DUMP = (ROOT / '_research' / 'game_25480438.dll').read_bytes()

BASE, P, O, A, D1, D2 = 0x40000000, 0x20000000, 0x30000000, 0x50000000, 0x60000000, 0x61000000
UNIT, IDX, ENTITY, AI = 0x123, 5, 0xABCD, 2
MULT1, MULT2 = 0x9E3779B1, 0x85EBCA6B
STRIDE = 0x1238


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
fake = {menu = false, calls = {}, ragdolled = false, allowed = true}
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
    GetCurrentProcess = function() return nil end,
    GetModuleHandleA = function(name) return ffi.cast('void *', BASE) end,
    ReadProcessMemory = function(p, addr, buf, size, got)
        local s = read_mem(tonumber(ffi.cast('uint64_t', addr)), tonumber(size))
        if not s then return 0 end
        ffi.copy(buf, s, #s); got[0] = #s; return 1
    end,
}
local stubs = {}
local function stub(kind, address)
    return function(state, mode)
        fake.calls[#fake.calls + 1] = string.format('%s %x 0x%x %s', kind, tonumber(address) - BASE,
                                                    tonumber(state), tostring(mode))
        if kind == 'start' then fake.ragdolled = true; if fake.on_start then fake.on_start() end; return end
        if kind == 'check' and tonumber(address) - BASE == 0xa74700 then return fake.ragdolled and 1 or 0 end
        return fake.allowed and 1 or 0
    end
end
package.loaded.ffi = setmetatable({
    load = function(name) return k32 end,
    cast = function(t, v)
        if t == 'RagdollOnCommandCheck' then return stub('check', v) end
        if t == 'RagdollOnCommandStart' then return stub('start', v) end
        return real_ffi.cast(t, v)
    end}, {__index = real_ffi})
ModBindingsMenu = {api = 1, register_binding = function(id, label, slot, o)
    fake.bound = id .. '|' .. label .. '|' .. tostring(slot) .. '|' .. o.category; return true end,
                   is_down = function(id) return fake.menu end}
'''


def run():
    logdir = Path(tempfile.mkdtemp())
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute(HARNESS, str(logdir), DUMP)
    f = lua.globals().fake
    ok = []

    def check(cond, what):
        ok.append(cond)
        print('PASS' if cond else 'FAIL', what)

    # The players global -> players: local active, local unit.
    f.patch(0x3326468, struct.pack('<Q', P))
    players = bytearray(0x400)
    struct.pack_into('<I', players, 0x88, 1)
    struct.pack_into('<I', players, 0x3a8, UNIT)
    f.heap(P, bytes(players))
    # The entity owner: unit map header (+0xf22ec8 data, +0xf22ed0 cap, +0xf22ed4 empty, +0xf22ed8 mult), entity ids.
    f.patch(0x346bf98, struct.pack('<Q', O))
    f.heap(O + 0xf22ec8, struct.pack('<QIII', D1, 16, 0xffffffff, MULT1) + b'\0' * 8)
    f.heap(D1, map_blob(16, MULT1, UNIT, IDX))
    f.heap(O + 0xf32f20 + IDX * 24, struct.pack('<I', ENTITY) + b'\0' * 20)
    # The avatar manager: its map (+0xf8 data, +0x100 cap, +0x104 empty, +0x108 mult), ragdoll state, flags.
    f.patch(0x3326d20, struct.pack('<Q', A))
    f.heap(A + 0xf8, struct.pack('<QIII', D2, 8, 0xffffffff, MULT2) + b'\0' * 8)
    f.heap(D2, map_blob(8, MULT2, ENTITY, AI))
    state = A + 0x53dd48 + AI * STRIDE
    f.heap(state + 0x398, struct.pack('<I', ENTITY))
    flags_at = A + 0x53e880 + AI * STRIDE
    f.heap(flags_at, struct.pack('<QQ', 0x4, 0))
    lua.execute('function fake.on_start() fake.heap(%d, string.char(4,0,0,0,0,0,0,0) .. '
                'string.char(0,0,0,0,0x10,0,0,0)) end' % flags_at)

    check(not sigspec.check(signatures.SCRIPT, sigspec.build(signatures.SPECS)),
          "the script's signature blocks match research/signatures.py")
    lua.execute(SOURCE)
    lua.execute('for i = 1, 5 do update(0.016) end')
    M = lua.globals().RagdollOnCommand
    log = lambda: (logdir / 'RagdollOnCommand.log').read_text()
    check(M.ready, 'ready: every signature at its rva, values read')
    check('Ready: avatar state = avatars + 0x53dd48 + index * 0x1238, entity at +0x398' in log(), 'offsets from code')
    a = lua.eval('RagdollOnCommand._test.local_avatar()')
    check(a and a.state == state and a.entity == ENTITY and a.index == AI, 'local avatar chain resolves the state')
    check(f.bound == 'alomare.ragdoll_on_command.ragdoll|Ragdoll|nil|Ragdoll On Command', 'binding registered')
    status = (logdir / 'RagdollOnCommand_STATUS.log').read_text()
    check(status.startswith('OK - set the Ragdoll key'), 'status OK: %r' % status.splitlines()[0])
    # A press: the game's sequence on the local state.
    lua.execute('fake.menu = true; update(0.016); update(0.016); fake.menu = false; update(0.016)')
    calls = list(f.calls.values())
    check(calls == ['check a74700 0x%x nil' % state, 'check a74850 0x%x nil' % state, 'start a75fa0 0x%x 0' % state,
                    'check a74700 0x%x nil' % state], 'one press (held two frames): check, allowed, start, check: %r'
          % calls)
    check('Ragdolled' in log(), 'logged as ragdolled')
    # It ends: the flag clears.
    lua.execute('fake.heap(%d, string.rep("\\0", 16)); for i = 1, 30 do update(0.016) end' % flags_at)
    check('Ragdoll ended after' in log(), 'the end is logged')
    # Refused, and not found.
    lua.execute('fake.allowed = false; fake.ragdolled = false; fake.menu = true; update(0.016); fake.menu = false; '
                'update(0.016)')
    check('not allowed right now (flags 0000000000000000, state bits 0000000000000000)' in log(), 'refusal logged')
    players[0x3a8:0x3ac] = struct.pack('<I', 0x7fff)
    f.heap(P, bytes(players))
    n = len(f.calls)
    lua.execute('fake.allowed = true; fake.menu = true; update(0.016); fake.menu = false; update(0.016)')
    check(len(f.calls) == n and 'Ragdoll key: no Helldiver (no unit)' in log(), 'no Helldiver: nothing called')
    # Another entity in the state: nothing called.
    players[0x3a8:0x3ac] = struct.pack('<I', UNIT)
    f.heap(P, bytes(players))
    f.heap(state + 0x398, struct.pack('<I', ENTITY + 1))
    lua.execute('fake.menu = true; update(0.016); fake.menu = false; update(0.016)')
    check(len(f.calls) == n and 'ragdoll state names another entity' in log(), 'state of another entity: nothing called')
    # Mod Bindings Menu v2.1 (version 3): the label and section are functions in the current language.
    lua2 = LuaRuntime(unpack_returned_tuples=True)
    lua2.execute(HARNESS, str(Path(tempfile.mkdtemp())), DUMP)
    lua2.execute("ModBindingsMenu.version = 3; ModBindingsMenu.register_binding = function(id, label, slot, o) "
                 "fake.label, fake.category = label, o.category; return true end")
    lua2.execute(SOURCE)
    lua2.execute('for i = 1, 3 do update(0.016) end')
    f2 = lua2.globals().fake
    check(callable(f2.label) and f2.label() == 'Ragdoll' and f2.category() == 'Ragdoll On Command',
          'v2.1 bindings: label and section passed as functions')
    print('%d/%d' % (sum(ok), len(ok)))
    return all(ok)


if __name__ == '__main__':
    sys.exit(0 if run() else 1)
