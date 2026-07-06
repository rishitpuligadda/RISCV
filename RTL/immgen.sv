module immgen
  import instrsel ::*; 
  #(parameter int LEN = 32)(
  output logic [LEN-1:0] imm,
  input  logic [LEN-1:0] instr,
  input  imm_sel         immsel
  );
  
  always_comb begin 
    unique case (immsel)
      IMM_I:   imm = {{20{instr[31]}}, instr[31:20]};
      IMM_S:   imm = {{20{instr[31]}}, instr[31:25], instr[11:7]};
      IMM_B:   imm = {{20{instr[31]}}, instr[7], instr[30:25], instr[11:8], 1'b0};
      IMM_U:   imm = {instr[31:12], 12'b0};
      IMM_J:   imm = {{12{instr[31]}}, instr[19:12], instr[20], instr[30:21], 1'b0};
      default: imm = 'd0;
    endcase
  end
  
  `ifdef FORMAL
    always_comb begin
      unique case (immsel)
        IMM_I: assert (imm == {{20{instr[31]}}, instr[31:20]});
        IMM_S: assert (imm == {{20{instr[31]}}, instr[31:25], instr[11:7]});
        IMM_B: assert (imm == {{20{instr[31]}}, instr[7], instr[30:25], instr[11:8], 1'b0});
        IMM_U: assert (imm == {instr[31:12], 12'b0});
        IMM_J: assert (imm == {{12{instr[31]}}, instr[19:12], instr[20], instr[30:21], 1'b0});
        default: assert (imm == '0);
      endcase
    end
  `endif
endmodule
