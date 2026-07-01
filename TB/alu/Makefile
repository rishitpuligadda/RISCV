SIM ?= verilator

TOPLEVEL_LANG ?= verilog

VERILOG_SOURCES = $(PWD)/../../RTL/operation.sv
VERILOG_SOURCES += $(PWD)/../../RTL/ALU.sv

TOPLEVEL = ALU

MODULE = test_alu

EXTRA_ARGS += --trace --trace-structs

include $(shell cocotb-config --makefiles)/Makefile.sim


