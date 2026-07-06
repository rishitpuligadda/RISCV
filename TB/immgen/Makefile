SIM ?= verilator
TOPLEVEL_LANG ?= verilog

VERILOG_SOURCES  = $(PWD)/../../RTL/instrsel.sv
VERILOG_SOURCES += $(PWD)/../../RTL/immgen.sv

TOPLEVEL = immgen
MODULE = test_immgen

# --lint-off UNUSEDSIGNAL because instr[6:0] is intentionally unused by immgen
EXTRA_ARGS += --trace --trace-structs -Wno-UNUSEDSIGNAL

include $(shell cocotb-config --makefiles)/Makefile.sim
