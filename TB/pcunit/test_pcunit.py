"""
Testbench for the PC Unit (PCUnit.sv).

Verifies:
  - Reset behavior (PC = 0 after reset)
  - Normal PC+4 increment
  - Branch target loading
  - Stall behavior (PC holds)
  - Priority ordering: stall > branch > increment
  - Random regression against Python model
"""

import random
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


CLK_PERIOD_NS = 10
MASK32 = 0xFFFFFFFF


# =============================================================================
# Python reference model
# =============================================================================
class PCModel:
    def __init__(self):
        self.pc = 0

    def step(self, stall, branch_taken, branch_target):
        """Compute next PC given the same priority as the RTL."""
        if stall:
            pass  # PC holds
        elif branch_taken:
            self.pc = branch_target & MASK32
        else:
            self.pc = (self.pc + 4) & MASK32

    def reset(self):
        self.pc = 0

# =============================================================================
# Helpers  (NO DECORATOR — this is a helper, not a test)
# =============================================================================
async def reset_dut(dut):
    """Assert reset for 3 cycles, then release."""
    dut.branch_target.value = 0
    dut.branch_taken.value  = 0
    dut.stall.value         = 0
    dut.rst_n.value         = 0
    for _ in range(3):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    # Reset released. Don't consume an extra cycle here —
    # the caller's next step() will be the first "real" cycle.
    await Timer(1, unit="ns")


async def step(dut, stall=0, branch_taken=0, branch_target=0):
    """Drive control inputs, wait for posedge, return new PC."""
    dut.stall.value         = stall
    dut.branch_taken.value  = branch_taken
    dut.branch_target.value = branch_target
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    return int(dut.pc.value)


# =============================================================================
# TEST 1: Reset behavior   (DECORATOR — this IS a test)
# =============================================================================
@cocotb.test()
async def test_reset(dut):
    """After reset, PC should be 0."""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)
    assert int(dut.pc.value) == 0, f"After reset, PC = 0x{int(dut.pc.value):08x}, expected 0"

# =============================================================================
# TEST 2: Normal increment (PC += 4 every cycle)
# =============================================================================
@cocotb.test()
async def test_increment(dut):
    """With no branch/stall, PC should increment by 4 each cycle."""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)

    expected = 0
    for i in range(20):
        pc = await step(dut, stall=0, branch_taken=0)
        expected += 4
        assert pc == expected, \
            f"[cycle {i}] PC = 0x{pc:08x}, expected 0x{expected:08x}"


# =============================================================================
# TEST 3: Branch target loading
# =============================================================================
@cocotb.test()
async def test_branch(dut):
    """When branch_taken=1, PC should load branch_target."""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)

    # Increment a few times to get PC != 0
    for _ in range(5):
        await step(dut)

    # Now branch to 0x1000
    pc = await step(dut, branch_taken=1, branch_target=0x1000)
    assert pc == 0x1000, f"After branch to 0x1000, PC = 0x{pc:08x}"

    # After branch, continue incrementing from new address
    pc = await step(dut)
    assert pc == 0x1004, f"After branch, next PC = 0x{pc:08x}, expected 0x1004"

    pc = await step(dut)
    assert pc == 0x1008, f"Continuing PC = 0x{pc:08x}, expected 0x1008"


# =============================================================================
# TEST 4: Stall behavior
# =============================================================================
@cocotb.test()
async def test_stall(dut):
    """When stall=1, PC should hold its value."""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)

    # Advance PC to 0x20
    for _ in range(8):
        await step(dut)
    assert int(dut.pc.value) == 0x20, f"Setup: PC should be 0x20, got 0x{int(dut.pc.value):08x}"

    # Stall for 5 cycles — PC should not change
    for i in range(5):
        pc = await step(dut, stall=1)
        assert pc == 0x20, f"[stall cycle {i}] PC = 0x{pc:08x}, expected 0x20"

    # Release stall, PC should continue incrementing
    pc = await step(dut, stall=0)
    assert pc == 0x24, f"After stall, PC = 0x{pc:08x}, expected 0x24"


# =============================================================================
# TEST 5: Priority — stall wins over branch
# =============================================================================
@cocotb.test()
async def test_stall_wins_over_branch(dut):
    """When stall=1 AND branch_taken=1, stall wins — PC holds."""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)

    for _ in range(4):
        await step(dut)
    assert int(dut.pc.value) == 0x10, f"Setup: PC should be 0x10"

    # Assert BOTH stall and branch_taken with a target of 0xDEADBEEF
    # Expected: PC holds at 0x10 because stall > branch in priority
    pc = await step(dut, stall=1, branch_taken=1, branch_target=0xDEADBEEF)
    assert pc == 0x10, f"Stall+branch: PC = 0x{pc:08x}, expected 0x10 (stall should win)"

    # Deassert stall — now branch should take effect if still asserted
    # (In practice, once the branch signal deasserts, PC just increments)
    pc = await step(dut, stall=0, branch_taken=0)
    assert pc == 0x14, f"After stall release, PC = 0x{pc:08x}, expected 0x14"


# =============================================================================
# TEST 6: Random regression
# =============================================================================
@cocotb.test()
async def test_random(dut):
    """500 random operations against Python model."""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)

    model = PCModel()
    random.seed(0xBAD5EED)

    for i in range(500):
        # Randomly choose control signals
        stall         = random.randint(0, 1)
        branch_taken  = random.randint(0, 1)
        # Branch target aligned to 4 bytes (RV32 requirement)
        branch_target = random.randint(0, MASK32) & ~0x3

        pc = await step(dut, stall=stall, branch_taken=branch_taken,
                        branch_target=branch_target)
        model.step(stall, branch_taken, branch_target)

        assert pc == model.pc, (
            f"[iter {i}] stall={stall}, branch_taken={branch_taken}, "
            f"target=0x{branch_target:08x}: DUT PC=0x{pc:08x}, model=0x{model.pc:08x}"
        )
