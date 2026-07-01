import random 
import cocotb
from cocotb.triggers import Timer

ALU_ADD  = 0
ALU_SUB  = 1
ALU_AND  = 2
ALU_OR   = 3
ALU_XOR  = 4
ALU_SLL  = 5
ALU_SRL  = 6
ALU_SRA  = 7
ALU_SLT  = 8
ALU_SLTU = 9
ALU_PASS = 10

OP_NAMES = {
    ALU_ADD:  "ALU_ADD",
    ALU_SUB:  "ALU_SUB",
    ALU_AND:  "ALU_AND",
    ALU_OR:   "ALU_OR",
    ALU_XOR:  "ALU_XOR",
    ALU_SLL:  "ALU_SLL",
    ALU_SRL:  "ALU_SRL",
    ALU_SRA:  "ALU_SRA",
    ALU_SLT:  "ALU_SLT",
    ALU_SLTU: "ALU_SLTU",
    ALU_PASS: "ALU_PASS",
}

MASK32 = 0xFFFFFFFF

def to_signed32(x):
    x &= MASK32
    return x - (1 << 32) if x & (1 << 31) else x

def ref(op, a, b):
    a &= MASK32
    b &= MASK32
    shamt = b & 0x1F

    if op == ALU_ADD:
        result = (a + b) & MASK32
    elif op == ALU_SUB:
        result = (a - b) & MASK32
    elif op == ALU_AND:
        result = a & b
    elif op == ALU_OR:
        result = a | b
    elif op == ALU_XOR:
        result = a ^ b
    elif op == ALU_SLL:
        result = (a << shamt) & MASK32
    elif op == ALU_SRL:
        result = (a >> shamt) & MASK32
    elif op == ALU_SRA:
        # Arithmetic right shift: convert to signed first, then shift.
        # Python's >> on a signed int does sign-extending shift, which is what we want.
        result = (to_signed32(a) >> shamt) & MASK32
    elif op == ALU_SLT:
        result = 1 if to_signed32(a) < to_signed32(b) else 0
    elif op == ALU_SLTU:
        result = 1 if a < b else 0
    elif op == ALU_PASS:
        result = b
    else:
        # Default case in the RTL produces 0
        result = 0

    # Flags are computed independently of op
    zero        = 1 if a == b else 0
    less_than   = 1 if to_signed32(a) < to_signed32(b) else 0
    less_than_u = 1 if a < b else 0

    return result, zero, less_than, less_than_u

async def apply_and_check(dut, op, a, b, label=""):
    dut.op.value = op
    dut.a.value = a
    dut.b.value = b

    await Timer(1, units="ns")

    got_result = int(dut.result.value)
    got_zero = int(dut.zero.value)
    got_less_than = int(dut.less_than.value)
    got_less_than_u = int(dut.less_than_u.value)

    exp_result, exp_zero, exp_lt, exp_ltu = ref(op, a, b)

    op_name = OP_NAMES.get(op, f"UNKNOWN({op})")

    assert got_result == exp_result, (
        f"[{label}] {op_name}: a=0x{a:08x} b=0x{b:08x}"
        f"-> result: got 0x{got_result:08x}, expected 0x{exp_result:08x}"
            )

    assert got_zero == exp_zero, (
        f"[{label}] {op_name}: a=0x{a:08x} b=0x{b:08x}"
        f"-> zero: got 0x{got_zero}, expected 0x{exp_zero}"
            )

    assert got_less_than == exp_lt, (
        f"[{label}] {op_name}: a=0x{a:08x} b=0x{b:08x}"
        f"-> less_than: got 0x{got_less_than}, expected 0x{exp_lt}"
            )

    assert got_zero == exp_zero, (
        f"[{label}] {op_name}: a=0x{a:08x} b=0x{b:08x}"
        f"-> less_than_u: got 0x{got_less_than_u}, expected 0x{exp_ltu}"
            )

# =============================================================================
# TEST 1: Sanity check with a handful of directed vectors per op.
# Catches gross bugs ("ALU_ADD doesn't add") immediately.
# =============================================================================
@cocotb.test()
async def test_sanity(dut):
    """Directed tests, one or two vectors per operation."""
    vectors = [
        # (op,        a,            b,            description)
        (ALU_ADD,  5,           3,           "5 + 3"),
        (ALU_ADD,  0xFFFFFFFF,  1,           "wrap: -1 + 1"),
        (ALU_SUB,  10,          3,           "10 - 3"),
        (ALU_SUB,  0,           1,           "underflow: 0 - 1"),
        (ALU_AND,  0xF0F0F0F0,  0x0F0F0F0F,  "AND mask"),
        (ALU_OR,   0xF0F0F0F0,  0x0F0F0F0F,  "OR fill"),
        (ALU_XOR,  0xAAAAAAAA,  0xFFFFFFFF,  "XOR invert"),
        (ALU_SLL,  0x1,         4,           "1 << 4"),
        (ALU_SRL,  0x80000000,  1,           "logical shift right"),
        (ALU_SRA,  0x80000000,  1,           "arithmetic shift right"),
        (ALU_SLT,  0xFFFFFFFF,  1,           "signed: -1 < 1"),
        (ALU_SLTU, 0xFFFFFFFF,  1,           "unsigned: big > 1"),
        (ALU_PASS, 0xDEADBEEF,  0xCAFEBABE,  "PASS returns b"),
    ]
    for op, a, b, desc in vectors:
        await apply_and_check(dut, op, a, b, label=f"sanity:{desc}")


# =============================================================================
# TEST 2: Corner-case sweep — every op against pairs of "interesting" values.
# Catches sign-boundary bugs, wrap-around bugs, edge cases.
# =============================================================================
@cocotb.test()
async def test_corners(dut):
    """Exhaustive corner-case combinations."""
    corners = [
        0x00000000,  # all zeros
        0x00000001,  # smallest positive
        0xFFFFFFFF,  # all ones (-1 signed, max unsigned)
        0x7FFFFFFF,  # INT_MAX signed
        0x80000000,  # INT_MIN signed (sign-bit boundary)
        0x55555555,  # alternating bits
        0xAAAAAAAA,  # alternating bits (inverted)
        42,          # arbitrary mid-range value
    ]
    for op in range(11):  # iterate through every defined op
        for a in corners:
            for b in corners:
                await apply_and_check(dut, op, a, b, label="corner")


# =============================================================================
# TEST 3: Random vectors per op.
# Catches "middle of the range" bugs that corner tests miss.
# =============================================================================
@cocotb.test()
async def test_random(dut):
    """Random vectors for each operation."""
    random.seed(0xC0FFEE)  # fixed seed for reproducibility
    for op in range(11):
        for _ in range(200):  # 200 vectors per op = 2200 total
            a = random.randint(0, MASK32)
            b = random.randint(0, MASK32)
            await apply_and_check(dut, op, a, b, label="random")


# =============================================================================
# TEST 4: Shift amount sweep.
# Specifically exercises shifters across all valid shift amounts (0..31).
# Critical for verifying SRA's sign extension is correct at every shift.
# =============================================================================
@cocotb.test()
async def test_shifts(dut):
    """Sweep shift amounts 0 through 31, including the b[4:0] masking case."""
    operands = [
        0x00000001,  # single bit, walks during shift
        0x80000001,  # MSB + LSB set, easy to see SRA sign-extension
        0xFFFFFFFF,  # all ones
        0x55555555,  # alternating bits
    ]
    for op in [ALU_SLL, ALU_SRL, ALU_SRA]:
        for a in operands:
            for shamt in range(32):
                await apply_and_check(dut, op, a, shamt, label="shift")
            # Also test that b values >= 32 only use lower 5 bits.
            # shamt = 32 should behave like shamt = 0.
            # shamt = 33 should behave like shamt = 1.
            for shamt in [32, 33, 63, 100, 0xFFFFFFFF]:
                await apply_and_check(dut, op, a, shamt, label="shift-mask")


# =============================================================================
# TEST 5: Flag-output verification.
# Flags (zero, less_than, less_than_u) are independent of op.
# Test them in isolation, especially around sign boundaries.
# =============================================================================
@cocotb.test()
async def test_flags(dut):
    """Verify zero, less_than, less_than_u outputs."""
    flag_vectors = [
        # (a,           b,           description)
        (5,           5,           "equal -> zero=1"),
        (0,           0,           "both zero -> zero=1"),
        (5,           6,           "5 < 6 signed and unsigned"),
        (6,           5,           "6 > 5 signed and unsigned"),
        (0xFFFFFFFF,  1,           "signed: -1 < 1; unsigned: big > 1 (sign boundary)"),
        (1,           0xFFFFFFFF,  "reverse of above"),
        (0x80000000,  0x7FFFFFFF,  "INT_MIN < INT_MAX signed; reverse unsigned"),
        (0x7FFFFFFF,  0x80000000,  "INT_MAX > INT_MIN signed; reverse unsigned"),
    ]
    for a, b, desc in flag_vectors:
        # Op doesn't matter for flag outputs; use ALU_ADD as a neutral choice.
        await apply_and_check(dut, ALU_ADD, a, b, label=f"flags:{desc}")

    # Also random vectors to cover the space broadly
    random.seed(0xBEEF)
    for _ in range(200):
        a = random.randint(0, MASK32)
        b = random.randint(0, MASK32)
        await apply_and_check(dut, ALU_ADD, a, b, label="flags-random")
