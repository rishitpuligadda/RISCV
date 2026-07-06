package instrsel;
  typedef enum logic [2:0] {
    IMM_I = 3'd0,
    IMM_S = 3'd1,
    IMM_B = 3'd2,
    IMM_U = 3'd3,
    IMM_J = 3'd4
  } imm_sel;
endpackage
