module Registers#(
  parameter int WIDTH = 32, 
  parameter int DEPTH = 32
  )(
  output logic [WIDTH-1:0]         rs1_data,
  output logic [WIDTH-1:0]         rs2_data,
  input  logic [$clog2(DEPTH)-1:0] rs1_addr,
  input  logic [$clog2(DEPTH)-1:0] rs2_addr,
  input  logic [WIDTH-1:0]         rd_data,
  input  logic [$clog2(DEPTH)-1:0] rd_addr,
  input  logic                     we,
  input  logic                     clk,
  input  logic                     rst_n
  );

  logic [WIDTH-1:0] registers [0:DEPTH-1];


  always_ff @(posedge clk or negedge rst_n) begin
    if(!rst_n) 
      registers <= '{default: '0};
    else if (we && (rd_addr != '0)) 
      registers[rd_addr] <= rd_data;
  end

  assign rs1_data = (rs1_addr != '0) ? registers[rs1_addr] : '0;
  assign rs2_data = (rs2_addr != '0) ? registers[rs2_addr] : '0;

  `ifdef FORMAL
  logic reset_done;
  initial reset_done = 1'b0;
  always_ff @(posedge clk) begin
    reset_done <= 1'b1;
  end
  always_comb begin
    if (!reset_done) assume (!rst_n);
    else             assume (rst_n);
  end
  always_comb begin
    if (rst_n) begin
      if (rs1_addr == '0) assert (rs1_data == '0);
      if (rs2_addr == '0) assert (rs2_data == '0);
    end
  end
  always_comb begin
    if (rst_n && (rs1_addr != '0)) assert (rs1_data == registers[rs1_addr]);
    if (rst_n && (rs2_addr != '0)) assert (rs2_data == registers[rs2_addr]);
  end
  always_ff @(posedge clk) begin
    if (rst_n && we && (rd_addr == '0)) begin
      assert (registers[0] == $past(registers[0]));
    end
  end
  always_ff @(posedge clk) begin
    if (rst_n && $past(rst_n) && $past(we) && ($past(rd_addr) != '0)) begin
      assert (registers[$past(rd_addr)] == $past(rd_data));
    end
  end
`endif

endmodule
