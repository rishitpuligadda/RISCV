module decoder 
  import operation::*;
  import instrsel::*;
(
  // Register file
  output logic [4:0]  rs1_addr,
  output logic [4:0]  rs2_addr,
  output logic [4:0]  rd_addr,
  output logic        reg_write,

  // ALU
  output alu_op       alu_op_o,
  output logic        alu_src_a_pc,
  output logic        alu_src_b_imm,

  // Immediate
  output imm_sel      immsel,

  // Memory
  output logic        mem_read,
  output logic        mem_write,
  output logic [1:0]  mem_size,
  output logic        mem_signed,

  // Branch and jump
  output logic        is_branch,
  output logic [2:0]  branch_op,
  output logic        is_jal,
  output logic        is_jalr,

  // Write-back select
  output logic [1:0]  wb_sel,

  // System / CSR
  output logic        is_system,
  output logic [2:0]  csr_op,
  output logic [11:0] csr_addr,

  // Exception
  output logic        illegal_instr,

  //Input
  input  logic [31:0] instr
);

  typedef enum logic [6:0] {
      OP_LUI      = 7'b0110111,
      OP_AUIPC    = 7'b0010111,
      OP_JAL      = 7'b1101111,
      OP_JALR     = 7'b1100111,
      OP_BRANCH   = 7'b1100011,
      OP_LOAD     = 7'b0000011,
      OP_STORE    = 7'b0100011,
      OP_OP_IMM   = 7'b0010011,
      OP_OP       = 7'b0110011,
      OP_MISC_MEM = 7'b0001111,
      OP_SYSTEM   = 7'b1110011
    } opcode;    

  always_comb begin
      rs1_addr      = instr[19:15];
      rs2_addr      = instr[24:20];
      rd_addr       = instr[11:7];
      reg_write     = 1'b0;
      alu_op_o      = ALU_ADD;
      alu_src_a_pc  = 1'b0;
      alu_src_b_imm = 1'b0;
      immsel        = IMM_NONE;
      mem_read      = 1'b0;
      mem_write     = 1'b0;
      mem_size      = 2'd0;
      mem_signed    = 1'b0;
      is_branch     = 1'b0;
      branch_op     = 3'd0;
      is_jal        = 1'b0;
      is_jalr       = 1'b0;
      wb_sel        = 2'd0;
      is_system     = 1'b0;
      csr_op        = 3'd0;
      csr_addr      = 12'd0;
      illegal_instr = 1'b0;
      
    unique case (instr[6:0]) 
      
      OP_LUI: begin 
        immsel        = IMM_U;
        alu_src_b_imm = 1'b1;
        reg_write     = 1'b1;
        wb_sel        = 2'b00;
      end

      OP_AUIPC: begin 
        immsel        = IMM_U;
        alu_src_a_pc  = 1'b1;
        alu_src_b_imm = 1'b1;
        alu_op_o      = ALU_ADD;
        reg_write     = 1'b1;
        wb_sel        = 2'b00;
      end

      OP_JAL: begin
        immsel        = IMM_J;
        alu_src_a_pc  = 1'b1;
        alu_src_b_imm = 1'b1;
        alu_op_o      = ALU_ADD;
        is_jal        = 1'b1;
        wb_sel        = 2'b10;
        reg_write     = 1'b1;
      end 

      OP_JALR: begin
        immsel        = IMM_I;
        alu_src_a_pc  = 1'b0;
        alu_src_b_imm = 1'b1;
        alu_op_o      = ALU_ADD;
        is_jalr       = 1'b1;
        wb_sel        = 2'b10;
        reg_write     = 1'b1;
        if (instr[14:12] != 3'b000) illegal_instr = 1'b1;
      end

      OP_BRANCH: begin
        immsel        = IMM_B;
        is_branch     = 1'b1;
        alu_src_b_imm = 1'b0;
        alu_src_a_pc  = 1'b0;
        alu_op_o      = ALU_SUB;
        unique case (instr[14:12])
          3'b010, 3'b011: illegal_instr = 1'b1;
          default:        branch_op = instr[14:12];
        endcase
      end

      OP_LOAD: begin
        immsel        = IMM_I;
        alu_src_a_pc  = 1'b0;
        alu_src_b_imm = 1'b1;
        alu_op_o      = ALU_ADD;
        mem_read      = 1'b1;
        mem_size      = instr[13:12];
        mem_signed    = ~instr[14];
        reg_write     = 1'b1;
        wb_sel        = 2'b01;
        if (instr[14:12] == 3'b011 || instr[14:12] == 3'b110 || instr[14:12] == 3'b111) illegal_instr = 1'b1;
      end 

      OP_STORE: begin
        immsel        = IMM_S;
        mem_write     = 1'b1;
        mem_size      = instr[13:12];
        alu_src_a_pc  = 1'b0;
        alu_src_b_imm = 1'b0;
        alu_op_o      = ALU_ADD;
        if (instr[14:12] != 3'b000 && instr[14:12] != 3'b001 && instr[14:12] != 3'b010) illegal_instr = 1'b1;
      end

      OP_OP_IMM: begin
        immsel        = IMM_I;
        alu_src_a_pc  = 1'b0;
        alu_src_b_imm = 1'b1;
        reg_write     = 1'b1;
        wb_sel        = 2'b00;
        unique case (instr[14:12]) 
          3'b000: alu_op_o = ALU_ADD;
          3'b010: alu_op_o = ALU_SLT;
          3'b011: alu_op_o = ALU_SLTU;
          3'b100: alu_op_o = ALU_XOR;
          3'b110: alu_op_o = ALU_OR;
          3'b111: alu_op_o = ALU_AND;
          3'b001: begin
            alu_op_o = ALU_SLL;
            if (instr[31:25] != 7'd0) illegal_instr = 1'b1;
          end
          3'b101: begin
            if (instr[31:25] == 7'd0)            alu_op_o = ALU_SRL;
            else if (instr[31:25] == 7'b0100000) alu_op_o = ALU_SRA;
            else                                 illegal_instr = 1'b1;
          end
          default: illegal_instr = 1'b1;
        endcase
      end

      OP_OP: begin
        immsel        = IMM_NONE;
        alu_src_a_pc  = 1'b0;
        alu_src_b_imm = 1'b0;
        reg_write     = 1'b1;
        wb_sel        = 2'b00;
        unique case (instr[14:12])
          3'b000: begin
            if (instr[31:25] == 7'd0)            alu_op_o = ALU_ADD;
            else if (instr[31:25] == 7'b0100000) alu_op_o = ALU_SUB;
            else if (instr[31:25] == 7'b0000001) alu_op_o = ALU_ADD;
            else                                 illegal_instr = 1'b1;
          end
          
          3'b001: begin
            if (instr[31:25] == 7'd0)            alu_op_o = ALU_SLL;
            else if (instr[31:25] == 7'b0000001) alu_op_o = ALU_ADD;
            else                                 illegal_instr = 1'b1;
          end 

          3'b010: begin
            if (instr[31:25] == 7'd0)            alu_op_o = ALU_SLT;
            else if (instr[31:25] == 7'b0000001) alu_op_o = ALU_ADD;
            else                                 illegal_instr = 1'b1;
          end

          3'b011: begin
            if (instr[31:25] == 7'd0)            alu_op_o = ALU_SLTU;
            else if (instr[31:25] == 7'b0000001) alu_op_o = ALU_ADD;
            else                                 illegal_instr = 1'b1;
          end

          3'b100: begin
            if (instr[31:25] == 7'd0)            alu_op_o = ALU_XOR;
            else if (instr[31:25] == 7'b0000001) alu_op_o = ALU_ADD;
            else                                 illegal_instr = 1'b1;
          end

          3'b101: begin
            if (instr[31:25] == 7'd0)            alu_op_o = ALU_SRL;
            else if (instr[31:25] == 7'b0100000) alu_op_o = ALU_SRA;
            else if (instr[31:25] == 7'b0000001) alu_op_o = ALU_ADD;
            else                                 illegal_instr = 1'b1;
          end

          3'b110: begin
            if (instr[31:25] == 7'd0)            alu_op_o = ALU_OR;
            else if (instr[31:25] == 7'b0000001) alu_op_o = ALU_ADD;
            else                                 illegal_instr = 1'b1;
          end

          3'b111: begin
            if (instr[31:25] == 7'd0)            alu_op_o = ALU_AND;
            else if (instr[31:25] == 7'b0000001) alu_op_o = ALU_ADD;
            else                                 illegal_instr = 1'b1;
          end

          default:                               illegal_instr = 1'b1;
        endcase
      end

      OP_MISC_MEM: begin
        ;
      end

      OP_SYSTEM: begin
        is_system = 1'b1;
        csr_op    = instr[14:12];
        csr_addr  = instr[31:20];
        case (instr[14:12]) 
          3'b000: reg_write = 1'b0;

          3'b001, 3'b010, 3'b011, 
          3'b101, 3'b110, 3'b111: begin
            reg_write = 1'b1;
            wb_sel    = 2'b11;
          end
          
          default: illegal_instr = 1'b1;
        endcase
      end

      default: illegal_instr = 1'b1;
    endcase
  end 
endmodule
