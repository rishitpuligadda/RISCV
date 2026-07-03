"""
Testbench for the Register File module (Registers.sv).

Verifies:
  - Reset behavior (all regs = 0)
  - Write-then-read round trip for every register
  - x0 (register 0) is hardwired to zero (writes ignored, reads return 0)
  - Both read ports operate independently
  - Same-cycle write/read returns OLD value (read-before-write semantics)
  - Random regression against a Python reference model
"""

import random
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


# =============================================================================
# Constants
# =============================================================================
CLK_PERIOD_NS = 10          # 100 MHz — arbitrary, any reasonable value works
NUM_REGS = 32               # Matches DEPTH parameter of the module
WIDTH = 32                  # Matches WIDTH parameter
MASK = (1 << WIDTH) - 1     # 0xFFFFFFFF for 32-bit values


# =============================================================================
# Python Reference Model
# =============================================================================
# Mirrors the DUT's architectural state. Every write and read on the DUT is
# also applied to the model; we then compare DUT output to model output.
# This is the same "golden model" pattern from the ALU testbench, but now
# the model has state that persists across operations.
class RegfileModel:
    def __init__(self):
        # 32 registers, all initialized to 0 (matches DUT reset behavior)
        self.regs = [0] * NUM_REGS

    def write(self, addr, data):
        # Writes to x0 are silently ignored (RV32I spec)
        if addr != 0:
            self.regs[addr] = data & MASK

    def read(self, addr):
        # x0 always reads as 0
        if addr == 0:
            return 0
        return self.regs[addr]

    def reset(self):
        self.regs = [0] * NUM_REGS


# =============================================================================
# Test Helpers
# =============================================================================

async def reset_dut(dut):
    """Initialize inputs, hold reset for 3 cycles, then release."""
    # Set all inputs to known values before releasing reset.
    # Leaving inputs as X during reset can cause weird sim behavior.
    dut.rs1_addr.value = 0
    dut.rs2_addr.value = 0
    dut.rd_addr.value  = 0
    dut.rd_data.value  = 0
    dut.we.value       = 0

    # Assert reset (active-low, so drive to 0)
    dut.rst_n.value = 0

    # Hold reset for 3 cycles — gives async reset time to fully propagate
    for _ in range(3):
        await RisingEdge(dut.clk)

    # Release reset
    dut.rst_n.value = 1

    # Wait one more cycle so reset release settles
    await RisingEdge(dut.clk)


async def write_reg(dut, addr, data):
    """Write `data` into register `addr`. Takes one clock cycle."""
    # Set up the write port inputs
    dut.rd_addr.value = addr
    dut.rd_data.value = data
    dut.we.value      = 1

    # Wait for the posedge — the write happens here
    await RisingEdge(dut.clk)

    # Deassert we so no accidental writes on subsequent cycles
    dut.we.value = 0


async def read_reg_port1(dut, addr):
    """Read register at `addr` via read port 1 (async read)."""
    dut.rs1_addr.value = addr
    # Async read — just wait a tiny bit for propagation, no clock edge needed
    await Timer(1, unit="ns")
    return int(dut.rs1_data.value)


async def read_reg_port2(dut, addr):
    """Read register at `addr` via read port 2 (async read)."""
    dut.rs2_addr.value = addr
    await Timer(1, unit="ns")
    return int(dut.rs2_data.value)


# =============================================================================
# TEST 1: Reset behavior
# All registers should read as 0 right after reset.
# =============================================================================
@cocotb.test()
async def test_reset(dut):
    """Every register reads as 0 after reset."""
    # Start the clock as a background task
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())

    await reset_dut(dut)

    # Check all 32 registers on both ports
    for addr in range(NUM_REGS):
        val1 = await read_reg_port1(dut, addr)
        val2 = await read_reg_port2(dut, addr)
        assert val1 == 0, f"reg[{addr}] read port 1 after reset = 0x{val1:08x}, expected 0"
        assert val2 == 0, f"reg[{addr}] read port 2 after reset = 0x{val2:08x}, expected 0"


# =============================================================================
# TEST 2: Write and read each register
# Write a unique value to each register 1..31, then read it back.
# =============================================================================
@cocotb.test()
async def test_write_readback(dut):
    """Write each register with a unique value, read it back on port 1."""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)

    # Compute a unique 32-bit value for each register address.
    # Using addr * 0x11111111 gives easily-recognizable patterns in waveforms.
    def value_for(addr):
        return (addr * 0x11111111) & MASK

    # Write phase
    for addr in range(1, NUM_REGS):  # skip x0
        await write_reg(dut, addr, value_for(addr))

    # Read phase — verify each register holds the value we wrote
    for addr in range(1, NUM_REGS):
        got = await read_reg_port1(dut, addr)
        expected = value_for(addr)
        assert got == expected, \
            f"reg[{addr}] readback: got 0x{got:08x}, expected 0x{expected:08x}"


# =============================================================================
# TEST 3: x0 is hardwired to zero
# Writes to x0 must be silently ignored. Reads must always return 0.
# =============================================================================
@cocotb.test()
async def test_x0_hardwired(dut):
    """Writing x0 has no effect; reading x0 always returns 0."""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)

    # Try to write x0 with several nonzero values
    for value in [0xFFFFFFFF, 0xDEADBEEF, 0x12345678, 0xAAAAAAAA]:
        await write_reg(dut, 0, value)

        # x0 should still read as 0 on both ports
        val1 = await read_reg_port1(dut, 0)
        val2 = await read_reg_port2(dut, 0)
        assert val1 == 0, f"After writing x0 with 0x{value:08x}, port 1 read = 0x{val1:08x}, expected 0"
        assert val2 == 0, f"After writing x0 with 0x{value:08x}, port 2 read = 0x{val2:08x}, expected 0"


# =============================================================================
# TEST 4: Both read ports work independently
# Read two different registers on the two ports simultaneously.
# =============================================================================
@cocotb.test()
async def test_dual_read_ports(dut):
    """rs1 and rs2 ports read independent addresses correctly."""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)

    # First, populate a few registers with known values
    test_values = {
        1:  0x11111111,
        5:  0x55555555,
        10: 0xAAAAAAAA,
        15: 0xF0F0F0F0,
        20: 0xDEADBEEF,
        31: 0xCAFEBABE,
    }
    for addr, val in test_values.items():
        await write_reg(dut, addr, val)

    # Now, for every pair (a, b), simultaneously read a on port 1 and b on port 2.
    # Verify both are correct.
    addrs = list(test_values.keys())
    for a in addrs:
        for b in addrs:
            # Drive both read addresses at once
            dut.rs1_addr.value = a
            dut.rs2_addr.value = b
            await Timer(1, unit="ns")

            got1 = int(dut.rs1_data.value)
            got2 = int(dut.rs2_data.value)
            exp1 = test_values[a]
            exp2 = test_values[b]

            assert got1 == exp1, \
                f"Simultaneous read: port1 addr={a}, got 0x{got1:08x}, expected 0x{exp1:08x}"
            assert got2 == exp2, \
                f"Simultaneous read: port2 addr={b}, got 0x{got2:08x}, expected 0x{exp2:08x}"


# =============================================================================
# TEST 5: Same-cycle write and read returns OLD value
# This is the "read-before-write" semantic that your pipeline relies on.
# On the cycle when we write x5=42, an in-cycle read of x5 should return
# whatever x5 was BEFORE the write (i.e., 0 if it hasn't been written yet).
# The new value (42) only appears on subsequent cycles.
# =============================================================================
@cocotb.test()
async def test_same_cycle_write_read(dut):
    """Same-cycle read sees the OLD register value, not the new write."""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)

    # First, set x5 to a known baseline value (99)
    await write_reg(dut, 5, 99)

    # Confirm x5 = 99 now
    val = await read_reg_port1(dut, 5)
    assert val == 99, f"Setup: expected x5 = 99, got 0x{val:08x}"

    # Now set up a write of 42 to x5, AND simultaneously read x5 on port 1.
    # Both happen in the same cycle.
    dut.rd_addr.value  = 5
    dut.rd_data.value  = 42
    dut.we.value       = 1
    dut.rs1_addr.value = 5

    # Wait for signals to propagate but NOT for the clock edge.
    # The async read should still see the OLD value (99), because the write
    # hasn't committed yet — it commits on the coming posedge.
    await Timer(1, unit="ns")
    got_before_edge = int(dut.rs1_data.value)
    assert got_before_edge == 99, \
        f"Same-cycle read before posedge: got 0x{got_before_edge:08x}, expected 99 (old value)"

    # Now let the write happen
    await RisingEdge(dut.clk)
    dut.we.value = 0

    # After the posedge, x5 should be 42
    val_after = await read_reg_port1(dut, 5)
    assert val_after == 42, \
        f"After posedge: expected x5 = 42, got 0x{val_after:08x}"


# =============================================================================
# TEST 6: Random regression against reference model
# 500 random operations, DUT vs model.
# =============================================================================
@cocotb.test()
async def test_random(dut):
    """Random writes and reads compared against a Python reference model."""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)

    model = RegfileModel()
    random.seed(0xC0FFEE)  # fixed seed for reproducibility

    for i in range(500):
        # Randomly choose: write or read
        if random.random() < 0.5:
            # Write
            addr = random.randint(0, NUM_REGS - 1)
            data = random.randint(0, MASK)
            await write_reg(dut, addr, data)
            model.write(addr, data)
        else:
            # Read on port 1
            addr = random.randint(0, NUM_REGS - 1)
            got = await read_reg_port1(dut, addr)
            expected = model.read(addr)
            assert got == expected, \
                f"[iter {i}] read reg[{addr}]: got 0x{got:08x}, expected 0x{expected:08x}"
