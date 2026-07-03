SIM ?= verilator
TOPLEVEL_LANG ?= verilog 

VERILOG_SOURCES = $(PWD)/../../RTL/Registers.sv

TOPLEVEL = Registers

MODULE = test_regfile

EXTRA_ARGS += --trace --trace-structs

include $(shell cocotb-config --makefiles)/Makefile.sim
