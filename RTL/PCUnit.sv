module PCUnit #(parameter int WIDTH = 32 )(
  output logic [WIDTH-1:0] pc,
  input  logic [WIDTH-1:0] branch_target,
  input  logic             branch_taken,
  input  logic             stall,
  input  logic             clk,
  input  logic             rst_n
  );

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n)            pc <= '0;
    else if (stall)        pc <= pc;
    else if (branch_taken) pc <= branch_target;
    else                   pc <= pc + 32'd4;
  end

  `ifdef FORMAL
    // Reset assumption
    logic reset_done;
    initial reset_done = 1'b0;
    always_ff @(posedge clk) begin
      reset_done <= 1'b1;
    end
    always_comb begin
      if (!reset_done) assume (!rst_n);
      else             assume (rst_n);
    end

    // Property 1: After reset, PC is 0
    always_ff @(posedge clk) begin
      if ($past(!rst_n) && rst_n) assert (pc == '0);
    end

    // Property 2: When stalled, PC holds
    always_ff @(posedge clk) begin
      if (reset_done && $past(rst_n) && $past(stall)) begin
        assert (pc == $past(pc));
      end
    end

    // Property 3: When not stalled and branch_taken, PC = branch_target
    always_ff @(posedge clk) begin
      if (reset_done && $past(rst_n) && !$past(stall) && $past(branch_taken)) begin
        assert (pc == $past(branch_target));
      end
    end

    // Property 4: When not stalled and no branch, PC = old_PC + 4
    always_ff @(posedge clk) begin
      if (reset_done && $past(rst_n) && !$past(stall) && !$past(branch_taken)) begin
        assert (pc == $past(pc) + 32'd4);
      end
    end
  `endif

endmodule
