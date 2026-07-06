"""
Testbench for the Immediate Generator (immgen.sv).

Tests all 5 RV32I immediate formats (I, S, B, U, J) against a Python
reference model that implements the same bit-swizzling.

Directed tests use hand-computed values from real RISC-V instructions.
Random tests generate 32-bit instructions and compare DUT vs reference.
"""

import random
import cocotb
from cocotb.triggers import Timer


# =============================================================================
# Format select values — must match instrsel.sv enum encoding
# =============================================================================
IMM_I = 0
IMM_S = 1
IMM_B = 2
IMM_U = 3
IMM_J = 4

FMT_NAMES = {IMM_I: "I", IMM_S: "S", IMM_B: "B", IMM_U: "U", IMM_J: "J"}

MASK32 = 0xFFFFFFFF


# =============================================================================
# Python reference model — extracts and sign-extends immediates
# =============================================================================
def sign_extend(value, bits):
    """Sign-extend a `bits`-wide value to 32 bits."""
    sign_bit = 1 << (bits - 1)
    # If sign bit set, subtract 2^bits to make it a negative Python int,
    # then mask to 32 bits.
    if value & sign_bit:
        value = value - (1 << bits)
    return value & MASK32


def ref_immediate(instr, immsel):
    """Return the 32-bit sign-extended immediate for the given instr/format."""
    instr &= MASK32

    if immsel == IMM_I:
        # I-type: bits [31:20] of instr are the 12-bit immediate
        raw = (instr >> 20) & 0xFFF
        return sign_extend(raw, 12)

    elif immsel == IMM_S:
        # S-type: bits [31:25] and [11:7], 12-bit immediate
        upper = (instr >> 25) & 0x7F      # 7 bits: [31:25]
        lower = (instr >> 7) & 0x1F       # 5 bits: [11:7]
        raw = (upper << 5) | lower
        return sign_extend(raw, 12)

    elif immsel == IMM_B:
        # B-type: bits [31] [7] [30:25] [11:8] then implicit 0 at LSB
        # 13 bits total (with LSB=0), sign-extended to 32
        b12 = (instr >> 31) & 0x1         # bit 12 of imm from bit 31 of instr
        b11 = (instr >> 7)  & 0x1         # bit 11 of imm from bit 7 of instr
        b10_5 = (instr >> 25) & 0x3F      # bits 10..5 of imm from bits 30..25
        b4_1  = (instr >> 8)  & 0xF       # bits 4..1 of imm from bits 11..8
        raw = (b12 << 12) | (b11 << 11) | (b10_5 << 5) | (b4_1 << 1)
        # raw is a 13-bit value (bit 12 is sign)
        return sign_extend(raw, 13)

    elif immsel == IMM_U:
        # U-type: bits [31:12] of instr, placed in imm[31:12], low 12 bits zero
        return instr & 0xFFFFF000

    elif immsel == IMM_J:
        # J-type: bits [31] [19:12] [20] [30:21] then implicit 0 at LSB
        # 21 bits total (with LSB=0), sign-extended to 32
        b20    = (instr >> 31) & 0x1
        b19_12 = (instr >> 12) & 0xFF
        b11    = (instr >> 20) & 0x1
        b10_1  = (instr >> 21) & 0x3FF
        raw = (b20 << 20) | (b19_12 << 12) | (b11 << 11) | (b10_1 << 1)
        return sign_extend(raw, 21)

    else:
        return 0


# =============================================================================
# Helper: drive inputs, wait, read output, compare
# =============================================================================
async def apply_and_check(dut, instr, immsel, label=""):
    dut.instr.value = instr
    dut.immsel.value = immsel
    await Timer(1, unit="ns")
    got = int(dut.imm.value)
    expected = ref_immediate(instr, immsel)

    assert got == expected, (
        f"[{label}] fmt={FMT_NAMES.get(immsel, '?')} instr=0x{instr:08x}: "
        f"got imm=0x{got:08x}, expected 0x{expected:08x}"
    )

# =============================================================================
# TEST 1: Directed vectors — hand-computed from real instructions
# =============================================================================
@cocotb.test()
async def test_directed(dut):
    """Directed test vectors from known RISC-V instructions."""
    vectors = [
        # ---------------- I-type ----------------
        # ADDI x1, x0, 42   -> imm = 42 (0x2A)
        # Encoding: imm[11:0]=0x02A, rs1=0, funct3=000, rd=1, op=0010011
        (0x02A00093, IMM_I, 0x0000002A, "ADDI x1, x0, 42"),
        # ADDI x1, x0, -1   -> imm = -1 (0xFFFFFFFF)
        (0xFFF00093, IMM_I, 0xFFFFFFFF, "ADDI x1, x0, -1"),
        # ADDI x1, x0, -2048 (min 12-bit signed) -> imm = 0xFFFFF800
        (0x80000093, IMM_I, 0xFFFFF800, "ADDI x1, x0, -2048"),
        # ADDI x1, x0, 2047 (max 12-bit signed) -> imm = 0x000007FF
        (0x7FF00093, IMM_I, 0x000007FF, "ADDI x1, x0, 2047"),

        # ---------------- S-type ----------------
        # SW x5, 100(x6)   -> imm = 100 (0x64)
        # Encoding: imm[11:5]=0x03, rs2=5, rs1=6, funct3=010, imm[4:0]=0x04, op=0100011
        (0x06532223, IMM_S, 0x00000064, "SW x5, 100(x6)"),
        # SW x5, -4(x6)   -> imm = -4 (0xFFFFFFFC)
        (0xFE532E23, IMM_S, 0xFFFFFFFC, "SW x5, -4(x6)"),

        # ---------------- B-type ----------------
        # BEQ x1, x2, +8   -> imm = 8
        (0x00208463, IMM_B, 0x00000008, "BEQ x1, x2, +8"),
        # BEQ x1, x2, -8   -> imm = -8 (0xFFFFFFF8)
        (0xFE208CE3, IMM_B, 0xFFFFFFF8, "BEQ x1, x2, -8"),

        # ---------------- U-type ----------------
        # LUI x1, 0x12345   -> imm = 0x12345000
        (0x123450B7, IMM_U, 0x12345000, "LUI x1, 0x12345"),
        # LUI x1, 0xFFFFF   -> imm = 0xFFFFF000
        (0xFFFFF0B7, IMM_U, 0xFFFFF000, "LUI x1, 0xFFFFF"),
        # AUIPC x1, 0x00001 -> imm = 0x00001000
        (0x00001097, IMM_U, 0x00001000, "AUIPC x1, 0x00001"),

        # ---------------- J-type ----------------
        # JAL x1, +16   -> imm = 16
        (0x010000EF, IMM_J, 0x00000010, "JAL x1, +16"),
        # JAL x1, -16   -> imm = -16 (0xFFFFFFF0)
        (0xFF1FF0EF, IMM_J, 0xFFFFFFF0, "JAL x1, -16"),
    ]
    for instr, immsel, expected, desc in vectors:
        computed = ref_immediate(instr, immsel)
        # Cross-check: does the Python reference match the hand-computed value?
        assert computed == expected, (
            f"Python model bug: {desc} -> model returned 0x{computed:08x}, "
            f"hand-computed 0x{expected:08x}"
        )
        # Then check DUT against reference
        await apply_and_check(dut, instr, immsel, label=f"directed:{desc}")


# =============================================================================
# TEST 2: Boundary values per format
# =============================================================================
@cocotb.test()
async def test_boundaries(dut):
    """Check min/max/zero of each format's immediate."""
    # For each format, create an instruction where the immediate field is
    # all zeros, all ones, or half-and-half — and check the extracted imm.
    formats = [IMM_I, IMM_S, IMM_B, IMM_U, IMM_J]

    # All zeros -> immediate is 0
    for fmt in formats:
        await apply_and_check(dut, 0x00000000, fmt, label="all_zeros")

    # All ones -> various results per format; ref_immediate is the source of truth
    for fmt in formats:
        await apply_and_check(dut, 0xFFFFFFFF, fmt, label="all_ones")

    # Only the sign bit set (instr[31] = 1, rest 0)
    for fmt in formats:
        await apply_and_check(dut, 0x80000000, fmt, label="sign_bit_only")


# =============================================================================
# TEST 3: Random regression per format
# =============================================================================
@cocotb.test()
async def test_random(dut):
    """Random 32-bit instructions per format, DUT vs reference model."""
    random.seed(0xBEEF)
    for fmt in [IMM_I, IMM_S, IMM_B, IMM_U, IMM_J]:
        for _ in range(300):
            instr = random.randint(0, MASK32)
            await apply_and_check(dut, instr, fmt, label=f"random:{FMT_NAMES[fmt]}")
