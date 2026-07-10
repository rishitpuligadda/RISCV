"""
Testbench for the Decoder module (decoder.sv).

Tests all RV32IM instructions by driving hand-encoded instruction words
and verifying each control signal output.
"""

import random
import cocotb
from cocotb.triggers import Timer


# =============================================================================
# Enum encodings — must match RTL packages
# =============================================================================

# ALU op encoding (from operation.sv)
ALU_ADD, ALU_SUB, ALU_AND, ALU_OR, ALU_XOR = 0, 1, 2, 3, 4
ALU_SLL, ALU_SRL, ALU_SRA = 5, 6, 7
ALU_SLT, ALU_SLTU = 8, 9
ALU_PASS = 10

# Immediate select (from instrsel.sv)
IMM_I, IMM_S, IMM_B, IMM_U, IMM_J, IMM_NONE = 0, 1, 2, 3, 4, 5

# Writeback select (encoded directly in decoder)
WB_ALU, WB_MEM, WB_PC4, WB_CSR = 0, 1, 2, 3


# =============================================================================
# Helper: drive instruction, wait, return all outputs as a dict
# =============================================================================
async def decode(dut, instr):
    """Drive `instr` into the DUT and return all outputs as a dict."""
    dut.instr.value = instr
    await Timer(1, unit="ns")
    return {
        "rs1_addr":      int(dut.rs1_addr.value),
        "rs2_addr":      int(dut.rs2_addr.value),
        "rd_addr":       int(dut.rd_addr.value),
        "reg_write":     int(dut.reg_write.value),
        "alu_op_o":      int(dut.alu_op_o.value),
        "alu_src_a_pc":  int(dut.alu_src_a_pc.value),
        "alu_src_b_imm": int(dut.alu_src_b_imm.value),
        "immsel":        int(dut.immsel.value),
        "mem_read":      int(dut.mem_read.value),
        "mem_write":     int(dut.mem_write.value),
        "mem_size":      int(dut.mem_size.value),
        "mem_signed":    int(dut.mem_signed.value),
        "is_branch":     int(dut.is_branch.value),
        "branch_op":     int(dut.branch_op.value),
        "is_jal":        int(dut.is_jal.value),
        "is_jalr":       int(dut.is_jalr.value),
        "wb_sel":        int(dut.wb_sel.value),
        "is_system":     int(dut.is_system.value),
        "csr_op":        int(dut.csr_op.value),
        "csr_addr":      int(dut.csr_addr.value),
        "illegal_instr": int(dut.illegal_instr.value),
    }


# =============================================================================
# Helper: check a subset of expected outputs
# =============================================================================
def check(dut, actual, expected, label):
    """Compare a dict of actual outputs against a dict of expected values."""
    for key, exp in expected.items():
        got = actual[key]
        assert got == exp, (
            f"[{label}] signal '{key}': got {got}, expected {exp}. "
            f"Full actual: {actual}"
        )


# =============================================================================
# TEST 1: U-type instructions (LUI, AUIPC)
# =============================================================================
@cocotb.test()
async def test_u_type(dut):
    """LUI and AUIPC."""

    # LUI x1, 0x12345  ->  0x123450b7
    result = await decode(dut, 0x123450B7)
    check(dut, result, {
        "immsel":        IMM_U,
        "alu_src_b_imm": 1,
        "reg_write":     1,
        "wb_sel":        WB_ALU,
        "rd_addr":       1,
        "illegal_instr": 0,
    }, "LUI x1, 0x12345")

    # AUIPC x1, 0x00001  ->  0x00001097
    result = await decode(dut, 0x00001097)
    check(dut, result, {
        "immsel":        IMM_U,
        "alu_src_a_pc":  1,
        "alu_src_b_imm": 1,
        "alu_op_o":      ALU_ADD,
        "reg_write":     1,
        "wb_sel":        WB_ALU,
        "rd_addr":       1,
        "illegal_instr": 0,
    }, "AUIPC x1, 0x00001")


# =============================================================================
# TEST 2: Jumps (JAL, JALR)
# =============================================================================
@cocotb.test()
async def test_jumps(dut):
    """JAL and JALR."""

    # JAL x1, +16  ->  0x010000ef
    result = await decode(dut, 0x010000EF)
    check(dut, result, {
        "immsel":       IMM_J,
        "alu_src_a_pc": 1,
        "alu_op_o":     ALU_ADD,
        "is_jal":       1,
        "wb_sel":       WB_PC4,
        "reg_write":    1,
        "rd_addr":      1,
        "illegal_instr": 0,
    }, "JAL x1, +16")

    # JALR x1, x2, 0  ->  0x000100e7
    result = await decode(dut, 0x000100E7)
    check(dut, result, {
        "immsel":        IMM_I,
        "alu_src_a_pc":  0,
        "alu_src_b_imm": 1,
        "alu_op_o":      ALU_ADD,
        "is_jalr":       1,
        "wb_sel":        WB_PC4,
        "reg_write":     1,
        "rd_addr":       1,
        "rs1_addr":      2,
        "illegal_instr": 0,
    }, "JALR x1, x2, 0")


# =============================================================================
# TEST 3: Branches (BEQ, BNE, BLT, BGE, BLTU, BGEU)
# =============================================================================
@cocotb.test()
async def test_branches(dut):
    """All 6 conditional branches."""

    # BEQ x1, x2, +8  ->  0x00208463
    result = await decode(dut, 0x00208463)
    check(dut, result, {
        "immsel":        IMM_B,
        "is_branch":     1,
        "alu_op_o":      ALU_SUB,
        "branch_op":     0b000,   # BEQ = funct3 000
        "rs1_addr":      1,
        "rs2_addr":      2,
        "reg_write":     0,       # branches don't write regfile
        "illegal_instr": 0,
    }, "BEQ x1, x2, +8")

    # BNE x1, x2, +8  ->  0x00209463
    result = await decode(dut, 0x00209463)
    check(dut, result, {"branch_op": 0b001, "illegal_instr": 0}, "BNE")

    # BLT x1, x2, +8  ->  0x0020C463
    result = await decode(dut, 0x0020C463)
    check(dut, result, {"branch_op": 0b100, "illegal_instr": 0}, "BLT")

    # BGE x1, x2, +8  ->  0x0020D463
    result = await decode(dut, 0x0020D463)
    check(dut, result, {"branch_op": 0b101, "illegal_instr": 0}, "BGE")

    # BLTU x1, x2, +8  ->  0x0020E463
    result = await decode(dut, 0x0020E463)
    check(dut, result, {"branch_op": 0b110, "illegal_instr": 0}, "BLTU")

    # BGEU x1, x2, +8  ->  0x0020F463
    result = await decode(dut, 0x0020F463)
    check(dut, result, {"branch_op": 0b111, "illegal_instr": 0}, "BGEU")

    # Illegal branch (funct3=010)  ->  0x0020A463
    result = await decode(dut, 0x0020A463)
    check(dut, result, {"illegal_instr": 1}, "illegal branch funct3=010")


# =============================================================================
# TEST 4: Loads (LB, LH, LW, LBU, LHU)
# =============================================================================
@cocotb.test()
async def test_loads(dut):
    """All 5 legal load types."""

    # LB x1, 0(x2)   ->  0x00010083
    result = await decode(dut, 0x00010083)
    check(dut, result, {
        "immsel":        IMM_I,
        "alu_op_o":      ALU_ADD,
        "mem_read":      1,
        "mem_size":      0b00,    # byte
        "mem_signed":    1,       # signed
        "reg_write":     1,
        "wb_sel":        WB_MEM,
        "rd_addr":       1,
        "rs1_addr":      2,
        "illegal_instr": 0,
    }, "LB x1, 0(x2)")

    # LH x1, 0(x2)   ->  0x00011083
    result = await decode(dut, 0x00011083)
    check(dut, result, {
        "mem_size":      0b01,    # halfword
        "mem_signed":    1,       # signed
        "illegal_instr": 0,
    }, "LH")

    # LW x1, 0(x2)   ->  0x00012083
    result = await decode(dut, 0x00012083)
    check(dut, result, {
        "mem_size":      0b10,    # word
        "mem_signed":    1,       # signed (funct3 bit 2 = 0)
        "illegal_instr": 0,
    }, "LW")

    # LBU x1, 0(x2)   ->  0x00014083
    result = await decode(dut, 0x00014083)
    check(dut, result, {
        "mem_size":      0b00,    # byte
        "mem_signed":    0,       # unsigned
        "illegal_instr": 0,
    }, "LBU")

    # LHU x1, 0(x2)   ->  0x00015083
    result = await decode(dut, 0x00015083)
    check(dut, result, {
        "mem_size":      0b01,    # halfword
        "mem_signed":    0,       # unsigned
        "illegal_instr": 0,
    }, "LHU")

    # Illegal load (funct3=011)  ->  0x00013083
    result = await decode(dut, 0x00013083)
    check(dut, result, {"illegal_instr": 1}, "illegal load funct3=011")


# =============================================================================
# TEST 5: Stores (SB, SH, SW)
# =============================================================================
@cocotb.test()
async def test_stores(dut):
    """All 3 legal store types."""

    # SB x1, 0(x2)   ->  0x00110023
    result = await decode(dut, 0x00110023)
    check(dut, result, {
        "immsel":     IMM_S,
        "alu_op_o":   ALU_ADD,
        "mem_write":  1,
        "mem_size":   0b00,       # byte
        "reg_write":  0,          # stores don't write regfile
        "rs1_addr":   2,
        "rs2_addr":   1,
        "illegal_instr": 0,
    }, "SB x1, 0(x2)")

    # SH x1, 0(x2)   ->  0x00111023
    result = await decode(dut, 0x00111023)
    check(dut, result, {"mem_size": 0b01, "mem_write": 1, "illegal_instr": 0}, "SH")

    # SW x1, 0(x2)   ->  0x00112023
    result = await decode(dut, 0x00112023)
    check(dut, result, {"mem_size": 0b10, "mem_write": 1, "illegal_instr": 0}, "SW")

    # Illegal store (funct3=011)  ->  0x00113023
    result = await decode(dut, 0x00113023)
    check(dut, result, {"illegal_instr": 1}, "illegal store funct3=011")


# =============================================================================
# TEST 6: OP-IMM (ADDI, SLTI, SLTIU, XORI, ORI, ANDI, SLLI, SRLI, SRAI)
# =============================================================================
@cocotb.test()
async def test_op_imm(dut):
    """I-type ALU ops."""

    # ADDI x1, x2, 0  ->  0x00010093
    result = await decode(dut, 0x00010093)
    check(dut, result, {
        "immsel":        IMM_I,
        "alu_op_o":      ALU_ADD,
        "alu_src_b_imm": 1,
        "reg_write":     1,
        "illegal_instr": 0,
    }, "ADDI")

    # SLTI x1, x2, 0  ->  0x00012093
    result = await decode(dut, 0x00012093)
    check(dut, result, {"alu_op_o": ALU_SLT, "illegal_instr": 0}, "SLTI")

    # SLTIU x1, x2, 0  ->  0x00013093
    result = await decode(dut, 0x00013093)
    check(dut, result, {"alu_op_o": ALU_SLTU, "illegal_instr": 0}, "SLTIU")

    # XORI x1, x2, 0  ->  0x00014093
    result = await decode(dut, 0x00014093)
    check(dut, result, {"alu_op_o": ALU_XOR, "illegal_instr": 0}, "XORI")

    # ORI x1, x2, 0  ->  0x00016093
    result = await decode(dut, 0x00016093)
    check(dut, result, {"alu_op_o": ALU_OR, "illegal_instr": 0}, "ORI")

    # ANDI x1, x2, 0  ->  0x00017093
    result = await decode(dut, 0x00017093)
    check(dut, result, {"alu_op_o": ALU_AND, "illegal_instr": 0}, "ANDI")

    # SLLI x1, x2, 5  ->  0x00511093
    result = await decode(dut, 0x00511093)
    check(dut, result, {"alu_op_o": ALU_SLL, "illegal_instr": 0}, "SLLI")

    # SRLI x1, x2, 5  ->  0x00515093
    result = await decode(dut, 0x00515093)
    check(dut, result, {"alu_op_o": ALU_SRL, "illegal_instr": 0}, "SRLI")

    # SRAI x1, x2, 5  ->  0x40515093
    result = await decode(dut, 0x40515093)
    check(dut, result, {"alu_op_o": ALU_SRA, "illegal_instr": 0}, "SRAI")


# =============================================================================
# TEST 7: OP (R-type ALU ops)
# =============================================================================
@cocotb.test()
async def test_op(dut):
    """R-type ALU ops."""

    # ADD x1, x2, x3  ->  0x003100b3
    result = await decode(dut, 0x003100B3)
    check(dut, result, {
        "immsel":        IMM_NONE,
        "alu_op_o":      ALU_ADD,
        "alu_src_b_imm": 0,
        "reg_write":     1,
        "rs1_addr":      2,
        "rs2_addr":      3,
        "illegal_instr": 0,
    }, "ADD x1, x2, x3")

    # SUB x1, x2, x3  ->  0x403100b3
    result = await decode(dut, 0x403100B3)
    check(dut, result, {"alu_op_o": ALU_SUB, "illegal_instr": 0}, "SUB")

    # SLL x1, x2, x3  ->  0x003110b3
    result = await decode(dut, 0x003110B3)
    check(dut, result, {"alu_op_o": ALU_SLL, "illegal_instr": 0}, "SLL")

    # SLT x1, x2, x3  ->  0x003120b3
    result = await decode(dut, 0x003120B3)
    check(dut, result, {"alu_op_o": ALU_SLT, "illegal_instr": 0}, "SLT")

    # SLTU x1, x2, x3  ->  0x003130b3
    result = await decode(dut, 0x003130B3)
    check(dut, result, {"alu_op_o": ALU_SLTU, "illegal_instr": 0}, "SLTU")

    # XOR x1, x2, x3  ->  0x003140b3
    result = await decode(dut, 0x003140B3)
    check(dut, result, {"alu_op_o": ALU_XOR, "illegal_instr": 0}, "XOR")

    # SRL x1, x2, x3  ->  0x003150b3
    result = await decode(dut, 0x003150B3)
    check(dut, result, {"alu_op_o": ALU_SRL, "illegal_instr": 0}, "SRL")

    # SRA x1, x2, x3  ->  0x403150b3
    result = await decode(dut, 0x403150B3)
    check(dut, result, {"alu_op_o": ALU_SRA, "illegal_instr": 0}, "SRA")

    # OR x1, x2, x3  ->  0x003160b3
    result = await decode(dut, 0x003160B3)
    check(dut, result, {"alu_op_o": ALU_OR, "illegal_instr": 0}, "OR")

    # AND x1, x2, x3  ->  0x003170b3
    result = await decode(dut, 0x003170B3)
    check(dut, result, {"alu_op_o": ALU_AND, "illegal_instr": 0}, "AND")

    # Illegal R-type (unknown funct7)
    # ADD with funct7=0x2A (illegal)  ->  0x543100b3
    result = await decode(dut, 0x543100B3)
    check(dut, result, {"illegal_instr": 1}, "illegal R-type funct7")


# =============================================================================
# TEST 8: SYSTEM (ECALL, EBREAK, CSR ops)
# =============================================================================
@cocotb.test()
async def test_system(dut):
    """SYSTEM instructions."""

    # ECALL  ->  0x00000073
    result = await decode(dut, 0x00000073)
    check(dut, result, {
        "is_system":     1,
        "reg_write":     0,
        "illegal_instr": 0,
    }, "ECALL")

    # EBREAK  ->  0x00100073
    result = await decode(dut, 0x00100073)
    check(dut, result, {
        "is_system":     1,
        "reg_write":     0,
        "illegal_instr": 0,
    }, "EBREAK")

    # CSRRW x1, mstatus, x2  ->  0x30011073 (mstatus = 0x300)
    result = await decode(dut, 0x30011073)
    check(dut, result, {
        "is_system":     1,
        "csr_op":        0b001,   # CSRRW
        "csr_addr":      0x300,   # mstatus
        "reg_write":     1,
        "wb_sel":        WB_CSR,
        "illegal_instr": 0,
    }, "CSRRW mstatus")


# =============================================================================
# TEST 9: FENCE (NOP)
# =============================================================================
@cocotb.test()
async def test_fence(dut):
    """FENCE is a NOP in this design."""

    # FENCE (any variant)  ->  0x0000000F
    result = await decode(dut, 0x0000000F)
    check(dut, result, {
        "reg_write":     0,
        "mem_read":      0,
        "mem_write":     0,
        "is_branch":     0,
        "illegal_instr": 0,
    }, "FENCE")


# =============================================================================
# TEST 10: Unknown opcode is illegal
# =============================================================================
@cocotb.test()
async def test_illegal_opcode(dut):
    """Instructions with unknown opcodes should raise illegal_instr."""

    # Opcode = 7'b0001011 (unassigned)  ->  0x0000000B
    result = await decode(dut, 0x0000000B)
    check(dut, result, {"illegal_instr": 1}, "unknown opcode")

    # Opcode = 7'b1111111 (unassigned)  ->  0x0000007F
    result = await decode(dut, 0x0000007F)
    check(dut, result, {"illegal_instr": 1}, "unknown opcode")
