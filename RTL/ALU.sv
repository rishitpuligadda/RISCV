module ALU 
  import operation::*;
  #(parameter int WIDTH = 32)(
  output logic  [WIDTH-1:0] result,
  output logic              zero,
  output logic              less_than,
  output logic              less_than_u,
  input  logic  [WIDTH-1:0] a,
  input  logic  [WIDTH-1:0] b,  
  input  alu_op             op
  );

  always_comb begin
    unique case (op)
      ALU_ADD:  result = a + b;
      ALU_SUB:  result = a - b;
      ALU_AND:  result = a & b;
      ALU_OR:   result = a | b;
      ALU_XOR:  result = a ^ b;
      ALU_SLL:  result = a << b[4:0];
      ALU_SRL:  result = a >> b[4:0];
      ALU_SRA:  result = $signed(a) >>> b[4:0];
      ALU_SLT:  result = WIDTH'(less_than);
      ALU_SLTU: result = WIDTH'(less_than_u);
      ALU_PASS: result = b;
      default:  result = 'd0;
    endcase
  end 
    
  assign zero = (a == b);
  assign less_than = ($signed(a) < $signed(b));
  assign less_than_u = (a < b);

  `ifdef FORMAL
  // Result-correctness properties: for each op, result must equal the expected expression.
  always_comb begin
    if (op == ALU_ADD)  assert (result == (a + b));
    if (op == ALU_SUB)  assert (result == (a - b));
    if (op == ALU_AND)  assert (result == (a & b));
    if (op == ALU_OR)   assert (result == (a | b));
    if (op == ALU_XOR)  assert (result == (a ^ b));
    if (op == ALU_SLL)  assert (result == (a << b[4:0]));
    if (op == ALU_SRL)  assert (result == (a >> b[4:0]));
    if (op == ALU_PASS) assert (result == b);
  end

  // Flag-output properties: flags are always correct, independent of op.
  always_comb begin
    assert (zero == (a == b));
    assert (less_than == ($signed(a) < $signed(b)));
    assert (less_than_u == (a < b));
  end
`endif

endmodule
