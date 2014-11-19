import sys
import numpy as np
sys.path.append("../..")
import pyrtl
from pyrtl import *

# Machine Parameters
argspace = 3  # number of bits to specify arg number
nArgs = pow(2, argspace)  # maximum number of function arguments
localspace = 4  # number of bits to specify local var number
nLocals = pow(2, localspace)  # maximum number of local vars in a function
freevarspace = 8  # number of bits to specify free variable number
nfreevars = pow(2, freevarspace)  # maximum number of free variables
width = 32  # machine width

# Memory sizes
namespace = 10  # number of bits used in IDs
ntablesize = pow(2, namespace)  # possible number of IDs (currently just 1 memory block)
evalstackspace = 15  # number of bits in eval stack addresses
evalstacksize = pow(2, evalstackspace)
heapspace = 16  # number of bits in heap addresses
heapsize = pow(2, heapspace)  # number of words in heap
textspace = 15  # number of bits in text memory addresses (a.k.a. immortal heap)
textsize = pow(2, textspace)  # number of words of immortal heap memory
itablespace = 10  # number of bits in info table memory address

# Info Table structure
itable_entrycode_bits = slice(0,15)
itable_nvars_bits = slice(15,22)
itable_nptrs_bits = slice(22,29)
itable_arity_bits = slice(29,32)

# Instruction structure
instr_opcode_bits = slice(27,32)
instr_dsrc_bits = slice(24,27)
instr_name_bits = slice(0,namespace)
if namespace > 24:
    raise ValueError("Size of names cannot fit in instruction.")
instr_argindex_bits = slice(0, argspace)
instr_freevarindex_bits = slice(0, freevarspace)
instr_litpattern_bits = slice(8,24)
instr_conitable_bits = slice(8,8+itablespace)
if itablespace > 16:
    raise ValueError("Size of instruction table address space cannot fit in instruction.")
instr_nInstrs_bits = slice(0,8)
instr_imm_bits = slice(0,24)

# Mux control constants
PC_INC = Const("2'b00")
PC_NINSTRS = Const("2'b01")
PC_ITABLE = Const("2'b10")
PC_CONTINUATION = Const("2'b11")
SRC_LOCALS = Const("3'b000")
SRC_ARGS = Const("3'b001")
SRC_HEAP = Const("3'b010")
SRC_IMM = Const("3'b011")
SRC_RR = Const("3'b100")
SRC_NAME = Const("3'b101")

def main():

    #test_argregs()
    #test_args_alu_rr()
    buildAll()


def buildAll():

    # Build source mux
    localsOut = WireVector(width, "localsOut")
    argsOut =  WireVector(width, "argsOut")
    heapOut =  WireVector(width, "heapOut")
    immediate =  WireVector(width, "instrImmediate")
    retRegOut = WireVector(width, "returnRegisterOut")
    newName = WireVector(namespace, "NewName")
    dSources = {
        SRC_LOCALS : localsOut,
        SRC_ARGS : argsOut,
        SRC_HEAP : heapOut,
        SRC_IMM : immediate,
        SRC_RR : retRegOut,
        SRC_NAME : newName,
        None : 0
    }    
    dataSrcSelect = WireVector(3, "dataSourceSelect")
    srcMux = switch(dataSrcSelect, dSources)

    # other needed wires
    iheapOut = WireVector(width, "InstrHeapOut")
    itableOut = WireVector(32, "InstrTableOut")
    nLocals = WireVector(localspace, "nLocals")
    exptr = WireVector(textspace, "exptr")
    curclo = WireVector(namespace, "currentClosure")
    continuation = concat(exptr, curclo, nLocals)
    evalStackOut = WireVector(evalstackspace, "evalStackOut")
    cont_nLocals = evalStackOut[0:localspace]
    cont_envclo = evalStackOut[localspace:localspace+namespace]
    cont_exptr = evalStackOut[localspace+namespace:textspace]
    closureTable = heapOut[0:itablespace]

    # Name each component of info table
    itable_arity = itableOut[itable_arity_bits]
    itable_nptrs = itableOut[itable_nptrs_bits]
    itable_nvars = itableOut[itable_nvars_bits]
    itable_entryCode = itableOut[itable_entrycode_bits]

    # Name each possible section of instruction
    instr_opcode = iheapOut[instr_opcode_bits]
    instr_dsrc = iheapOut[instr_dsrc_bits]
    instr_name = iheapOut[instr_name_bits]
    instr_argindex = iheapOut[instr_argindex_bits]
    instr_freevarindex = iheapOut[instr_freevarindex_bits]
    instr_litpattern = iheapOut[instr_litpattern_bits]
    instr_conitable = iheapOut[instr_conitable_bits]
    instr_nInstrs = iheapOut[instr_nInstrs_bits]
    instr_imm = iheapOut[instr_imm_bits]

    # Declare control signals
    ctrl_argwe = WireVector(1, "ctrl_argsWriteEnable")
    ctrl_argSwitch = WireVector(1, "ctrl_argsSwitch")
    ctrl_ALUop = WireVector(8, "ctrl_ALUcontrol")
    ctrl_alu2rr = WireVector(1, "ctrl_ALU-to-returnReg")
    ctrl_loadrr = WireVector(1, "ctrl_loadRR")
    ctrl_exptrsrc = WireVector(1, "ctrl_exptrSource")
    ctrl_exptrload = WireVector(1, "ctrl_exptrLoad")
    ctrl_spDecr = WireVector(1, "ctrl_evalStackDecrement")
    ctrl_clearLocals = WireVector(1, "ctrl_clearLocals")
    ctrl_stackWrite = WireVector(1, "ctrl_stackWrite")
    ctrl_writeContinuation = WireVector(1, "ctrl_writeContinuation")

    args_alu_rr(srcMux, instr_argindex, ctrl_argwe, ctrl_argSwitch, ctrl_ALUop, ctrl_alu2rr,
                ctrl_loadrr, argsOut, retRegOut)
    itable_exptr_iheap(closureTable, ctrl_exptrsrc, ctrl_exptrload, instr_nInstrs, instr_conitable, 
                       itableOut, iheapOut, exptr)
    evalstack(ctrl_spDecr, ctrl_clearLocals, nLocals, ctrl_stackWrite, 
              ctrl_writeContinuation, continuation, srcMux, evalStackOut)

# ######################################################################
#     Instruction Decode
# ######################################################################
def instrdecode():
    pass

# ######################################################################
#     Evaluation Stack
# ######################################################################
def evalstack(ctrl_spDecr, ctrl_spclearLocals, nLocals, ctrl_writeValue, 
              ctrl_writeContinuation, continuation, srcMux, evalStackOut):
    sp = Register(evalstackspace, "EvalStackPointer")
    spinc = ctrl_writeValue | ctrl_writeContinuation  # auto-increment on writes
    toAdd = switch(concat(spinc, ctrl_spDecr, ctrl_spclearLocals), {
        "3'b100" : 0,
        "3'b010" : ~Const(1, bitwidth=evalstackspace),
        "3'b001" : ~nLocals,
        None : 0
    })
    cond = ConditionalUpdate()
    with cond(ctrl_spDecr | ctrl_spclearLocals | spinc):
        sp.next <<= toAdd + 1

    # Instantiate stack memory
    evalStack = MemBlock(width, evalstackspace, "EvaluationStack")

    # Stack ports
    evalStackOut <<= evalStack[sp]  # always read top of stack
    # can write data from srcMux (includes newly allocated names) or continuations
    evalStackWData = mux(ctrl_writeValue, falsecase=continuation, truecase=srcMux)
    EW = MemBlock.EnabledWrite
    nextspace = sp + 1
    evalStack[nextspace[0:evalstackspace]] = EW(evalStackWData, enable=spinc)


# ######################################################################
#     Locals
# ######################################################################
def locals():
    pass

# ######################################################################
#     Name Table and Heap
# ######################################################################
def nametable():
    pass

def heap():
    pass

# ######################################################################
#     Info Tables, Execution Pointer, and Immortal Heap
# ######################################################################
def itable_exptr_iheap(targetTable, ctrl_exptr, ctrl_loadexptr, nInstrs, contTarget, 
                       itableOut, instrOut, exptrOut):
    infoTable = MemBlock(32, itablespace, "infoTable")
    itableOut <<= infoTable[targetTable]
    
    # Execution Pointer (PC)
    exptr = Register(textspace, "ExecutionPointer")
    exptrOut <<= exptr
    itable_entryCode = itableOut[itable_entrycode_bits]
    nextexptr = switch(ctrl_exptr, {
        PC_INC : exptr + 1,
        PC_NINSTRS : nInstrs,
        PC_ITABLE : itable_entryCode,
        PC_CONTINUATION : contTarget,
        None : exptr
    })
    cond = ConditionalUpdate()
    with cond(ctrl_loadexptr):
        exptr.next <<= nextexptr

    # Immortal Heap
    immortalHeap = MemBlock(width, textspace, "ImmortalHeap")
    instrOut <<= immortalHeap[exptr]

# ######################################################################
#     Arg Regs, ALU, and Return Register
# ######################################################################
def args_alu_rr(srcMux, argIndex, ctrl_argwe, ctrl_argSwitch, ctrl_ALUop, ctrl_alu2rr,
                ctrl_loadrr, argsOut, rrOut):

    # Regisers used in this section
    rr = Register(width, "ReturnRegister")  # return register
    nargsreg = Register(argspace, "NumberArgs")  # number of args bound so far

    # Connections from args -> ALU
    arg1 = WireVector(width, "argreg1")
    arg2 = WireVector(width, "argreg2")

    # Instantiate argument regsiter module
    argregs(ctrl_argwe, nargsreg, srcMux, argIndex, argsOut, ctrl_argSwitch, arg1, arg2)

    # Update number of arguments register
    cond = ConditionalUpdate()
    with cond(ctrl_argSwitch):  # Reset to zero when leaving function
        nargsreg.next <<= 0
    with cond(ctrl_argwe):  # When writing arg, increment arg count
        nargsreg.next <<= nargsreg + 1

    # Instantiate ALU; connect to first two args
    ALUout = WireVector(width, "ALUout")
    makeALU(ctrl_ALUop, arg1, arg2, ALUout)

    # Return Register update
    with cond(ctrl_loadrr):  # signal to modify return reg
        with cond(ctrl_alu2rr):  # load rr with ALU output
            rr.next <<= ALUout
        with cond():  # if not loading ALU, load from srcMux
            rr.next <<= srcMux
    rrOut <<= rr  # send result to srcMux


def test_args_alu_rr():

    srcMux = Input(width, "srcMuxVal")
    argIndex = Input(argspace, "argReadIndex")
    ctrl_argwe = Input(1, "writeArg")
    ctrl_argSwitch = Input(1, "switchArgs")
    ctrl_ALUop = Input(8, "ALUop")
    ctrl_alu2rr = Input(1, "alu2rr")
    ctrl_loadrr = Input(1, "loadrr")
    argsOut = Output(width, "argsOut")
    rrOut = Output(width, "rrOut")

    args_alu_rr(srcMux, argIndex, ctrl_argwe, ctrl_argSwitch, ctrl_ALUop, ctrl_alu2rr,
                ctrl_loadrr, argsOut, rrOut)
 

    simvals = {
        srcMux          : "0123450000000000090",
        argIndex        : "0000000012345670000",
        ctrl_argwe     : "0111110000000000000", 
        ctrl_argSwitch : "0000001000000000000",
        ctrl_ALUop      : "0222222222222222220",
        ctrl_alu2rr     : "0111111111111110000",
        ctrl_loadrr     : "0111111111111110010" 
    }

    sim_trace = pyrtl.SimulationTrace()
    sim = pyrtl.Simulation(tracer=sim_trace)
    for cycle in range(len(simvals[srcMux])):
        sim.step({k:int(v[cycle]) for k,v in simvals.items()})
    sim_trace.render_trace()





# ######################################################################
#     Argument Registers
# ######################################################################
def argregs(we, waddr, wdata, raddr, rdata, flipstate, reg1, reg2):
    # Two banks of registers, one for reading one for writing;
    # Internal one-bit state tracks which is which

    # Handle I/O based on internal state
    state = Register(1, 'argstate')
    # In each state, one is read and one is written; on flip, write becomes read and
    #  read is cleared
    # state == 0: args1 is writeargs, args2 is readargs
    # state == 1: args1 is readargs, args2 is writeargs

    args1 = MemBlock(width, argspace, name="args1")
    args2 = MemBlock(width, argspace, name="args2")

    # Output
    read1 = args1[raddr]
    read2 = args2[raddr]
    rdata <<= mux(state, falsecase=read2, truecase=read1)  # mux for output

    # Additional ports to output arg0 and arg1; need both for primitive (ALU) ops
    reg1 <<= mux(state, falsecase=args2[Const("3'b0")], truecase=args1[Const("3'b0")])
    reg2 <<= mux(state, falsecase=args2[Const("3'b1")], truecase=args1[Const("3'b1")])

    # Input
    EW = MemBlock.EnabledWrite
    args1[waddr] = EW(wdata, enable=(we & (state == 0)))
    args2[waddr] = EW(wdata, enable=(we & (state == 1)))

    # Handle state flips
    state.next <<= mux(flipstate, falsecase=state, truecase=~state)

def test_argregs():

    we = Input(1, 'we')
    wdata = Input(width, 'wdata')
    raddr = Input(argspace, 'raddr')
    rdata = Output(width, 'rdata')
    argswitch = Input(1, 'argSwitch')
    arg1 = Output(width, 'arg1')
    arg2 = Output(width, 'arg2')
    nargsreg = Register(argspace, 'nargs')

    # Update number of arguments
    
    cond = ConditionalUpdate()
    with cond(argswitch):  # Clear reg on scope change
        nargsreg.next <<= 0
    with cond(we):  # increment on control signal
        nargsreg.next <<= nargsreg + 1
    

    # connect
    argregs(we, nargsreg, wdata, raddr, rdata, argswitch, arg1, arg2)

    pyrtl.working_block().sanity_check()

    # simulate
    # Write data 1-5, switch, then read out all regs
    # Switch again, read out all data
    # Write new dta, switch while writes ongoing, read out all regs
    # switch, read out all regs
    '''simvals = {
        we:        "0011111111000000000000000",
        wdata:     "0012345678999000000000000",
        raddr:     "0000000000000000012345670",
        argswitch: "0000000000000010000000000"
    }

    '''
    simvals = {
        we:        "0111110000000000000000011111111000000000000000000",
        wdata:     "0123450000000000000000098765432000000000000000000",
        raddr:     "0000000123456700123456755555555012345670012345670",
        argswitch: "0000010000000010000000000000100000000001000000000"
    }

    sim_trace = pyrtl.SimulationTrace()
    sim = pyrtl.Simulation(tracer=sim_trace)
    for cycle in range(len(simvals[we])):
        sim.step({k:int(v[cycle]) for k,v in simvals.items()})
    sim_trace.render_trace()


# ######################################################################
#     Primitive Ops Unit (a.k.a. ALU)
# ######################################################################
def makeALU(control, op1, op2, out):
    '''
        %and    - 8'b0000_0000
        %or     - 8'b0000_0001
        %not    - 8'b0000_0010
        %xor    - 8'b0000_0011
        %iadd   - 8'b0000_0100
        %isub   - 8'b0000_0101
        %eq     - 8'b0000_0110
        %ne     - 8'b0000_0111
        %lt     - 8'b0000_1000
        %le     - 8'b0000_1001
        %gt     - 8'b0000_1010
        %ge     - 8'b0000_1011

        %imul   - 8'b0001_0000
        %idiv   - 8'b0001_0001
        %imod   - 8'b0001_0010

        %lsl    - 8'b0010_0000
        %rsl    - 8'b0010_0001
        %rsa    - 8'b0010_0010
        %lr     - 8'b0010_0011
        %rr     - 8'b0010_0100

        %fadd   - 8'b1000_0000
        %fsub   - 8'b1000_0001
        %fmul   - 8'b1000_0010
        %fdiv   - 8'b1000_0011
    '''

    '''
    Unimplemented for now
    "8'b0001_0000": op1 * op2,
    "8'b0001_0001": op1 / op2,
    "8'b0001_0010": op1 % op2,

    "8'b0010_0000": lsl,
    "8'b0010_0001": rsl,
    "8'b0010_0010": rsa,
    "8'b0010_0011": lr,
    "8'b0010_0100": rr,

    "8'b1000_0000": fadd,
    "8'b1000_0001": fsub,
    "8'b1000_0010": fmul,
    "8'b1000_0011": fdiv,
    '''
    out <<= switch(control, {
        "8'b0000_0000": op1 & op2,
        "8'b0000_0001": op1 | op2,
        "8'b0000_0010": ~op1,
        "8'b0000_0011": op1 ^ op2,
        "8'b0000_0100": op1 + op2,
        "8'b0000_0101": op1 - op2,
        "8'b0000_0110": op1 == op2,
        "8'b0000_0111": op1 != op2,
        "8'b0000_1000": op1 < op2,
        "8'b0000_1001": op1 <= op2,
        "8'b0000_1010": op1 > op2,
        "8'b0000_1011": op1 >= op2,
        None: 0
    })    


class RegisterFile:

    def __init__(self, width, nregs, waddr, wdata, raddr, rdata, we, reset, name=''):

        # declare regs
        regs = []
        for i in range(nregs):
            regs.append(Register(width, name+"_"+str(i)))
        c = ConditionalUpdate()
        # all have reset; if addr matches and write enable high, take value
        for i in range(nregs):
            with c(reset):
                regs[i].next <<= 0
            with c(we & (waddr == i)):
                regs[i].next <<= wdata
        
        # use tree of muxes to choose output
        rdata <<= muxtree(regs, raddr)

        self.regs = regs


def switch(ctrl, logic_dict):
    """ switch finds the matching key in logic_dict and returns the value.                                                            
    The case "None" specifies the default value to return when there is no
    match.  The logic will be a simple linear mux tree of comparisons between
    the key and the ctrl, selecting the appropriate value
    """

    working_result = logic_dict[None]
    for case_value in logic_dict:
        if case_value is None:
            continue
        working_result = mux(
            ctrl == case_value,
            falsecase=working_result,
            truecase=logic_dict[case_value])
    return working_result


def muxtree(vals, select):
    """Recursively build a tree of muxes. Takes a list of wires and a select wire; the list
    should be ordered such that the value of select is the index of the wire passed through."""
    if len(select) == 1:
        if len(vals) != 2:
            raise ValueError("Mismatched values; select should have logN bits")
        return mux(select, falsecase = vals[0], truecase = vals[1])
    else:
        # mux each pair of values into new N/2 new wires, recursively call
        new = []
        for i in range(len(vals)/2):
            new.append(mux(select[0], falsecase=vals[2*i], truecase=vals[2*i+1]))
        return muxtree(new, select[1:])





if __name__ == "__main__":
    main()
