SIM ?= verilator
TOPLEVEL_LANG ?= verilog

VERILOG_SOURCES  = $(PWD)/../../RTL/operation.sv
VERILOG_SOURCES += $(PWD)/../../RTL/instrsel.sv
VERILOG_SOURCES += $(PWD)/../../RTL/decoder.sv

TOPLEVEL = decoder
MODULE = test_decoder

EXTRA_ARGS += --trace --trace-structs -Wno-UNUSEDSIGNAL

include $(shell cocotb-config --makefiles)/Makefile.sim
