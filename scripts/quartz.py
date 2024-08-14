# Creates a Quartus project to execute any stage of the FPGA toolchain
# workflow. This script has the ability to override the top-level generics
# through the writing of a TCL script to eventually get called by Quartus.
#
# The script can auto-detect an Intel FPGA connected to the PC to program
# with a .pof or .sof bitstream file.
#
# References:
#   https://www.intel.co.jp/content/dam/altera-www/global/ja_JP/pdfs/literature/an/an312.pdf
#   https://community.intel.com/t5/Intel-Quartus-Prime-Software/Passing-parameter-generic-to-the-top-level-in-Quartus-tcl/td-p/239039

from mod import Command, Env, Generic, Blueprint, Step, Tcl
from typing import List
import os
import argparse
import toml

def main():
    # temporarily appends quartus installation path to PATH env variable
    Env.add_path(Env.read("ORBIT_ENV_QUARTUS_DIR", missing_ok=True))

    ## Handle command-line arguments

    parser = argparse.ArgumentParser(prog='quartz', allow_abbrev=False)

    parser.add_argument("--synth", action="store_true", default=False, help="execute analysize and synthesis")
    parser.add_argument("--route", action="store_true", default=False, help="execute place and route")
    parser.add_argument("--sta", action="store_true", default=False, help="execute static timing analysis")
    parser.add_argument("--bit", action="store_true", default=False, help="generate bitstream file")

    parser.add_argument("--open", action="store_true", default=False, help="open quartus project in gui")
    parser.add_argument("--compile", action="store_true", default=False, help="full toolflow")
    parser.add_argument("--eda-netlist", action="store_true", default=False, help="generate eda timing netlist")

    parser.add_argument("--board", action="store", default=None, type=str, help="board configuration file name")
    parser.add_argument("--prog-sram", action="store_true", default=False, help="program with temporary bitfile")
    parser.add_argument("--prog-flash", action="store_true", default=False, help="program with permanent bitfile")

    parser.add_argument("--family", action="store", default=None, type=str, help="targeted fpga family")
    parser.add_argument("--device", action="store", default=None, type=str, help="targeted fpga device")

    parser.add_argument('--generic', '-g', action='append', type=Generic.from_arg, default=[], metavar='key=value', help='override top-level VHDL generics')

    args = parser.parse_args()

    generics: List[Generic] = args.generic

    # determine if to program the FPGA board
    pgm_temporary = args.prog_sram
    pgm_permanent = args.prog_flash

    # device selected here is read from .board file if is None
    FAMILY = args.family
    DEVICE = args.device

    # the quartus project will reside in a folder the same name as the IP
    PROJECT = Env.read("ORBIT_IP_NAME", missing_ok=False)

    # will be overridden when programming to board with auto-detection by quartus
    CABLE = "USB-Blaster"

    # determine if to open the quartus project in GUI
    open_project = args.open

    # default flow is none (won't execute any flow)
    flow = None
    synth = impl = asm = sta = eda_netlist = False
    if args.compile == True:
        flow = '-compile'
    else:
        # run up through synthesis
        if args.synth == True:
            synth = True
        # run up through fitting
        if args.route == True:
            synth = impl = True
        # run up through static timing analysis
        if args.sta == True:
            synth = impl = sta = True
        # run up through assembly
        if args.bit == True:
            synth = impl = sta = asm = True
        # run up through generating eda timing netlist
        if args.eda_netlist == True:
            synth = impl = sta = asm = eda_netlist = True
        # use a supported device to generate .SDO and .VHO files for timing simulation
        if eda_netlist == True:
            FAMILY = "MAXII"
            DEVICE = "EPM2210F324I5"
        pass

    ## Collect data from the blueprint

    # list of (lib, path)
    src_files = []
    # list of paths to board design files
    bdf_files = []

    board_config = None
    # read/parse blueprint file
    for step in Blueprint().parse():
        if step.is_builtin():
            src_files += [step]
        elif step.is_aux("BDF"):
            bdf_files += [step.path]
        elif step.is_aux('BOARD'):
            if board_config == None and args.board is None:
                board_config = toml.load(step.path)
                print('info: loaded board file:', step.path)
            # match filename with the filename provided on command-line
            elif os.path.splitext(os.path.basename(step.path))[0] == args.board:
                board_config = toml.load(step.path)
                print('info: loaded board file:', step.path)
            pass
        pass

    # verify we got a matching board file if specified from the command-line
    if board_config is None and args.board is not None:
        print("error: board file "+Env.quote_str(args.board)+" is not found in blueprint")
        exit(101)

    if board_config is not None:
        FAMILY = board_config["part"]["FAMILY"]
        DEVICE = board_config["part"]["DEVICE"]

    top_unit = Env.read("ORBIT_TOP_NAME", missing_ok=False)

    if FAMILY == None:
        print("error: FPGA \"FAMILY\" must be specified in .board file's `[part]` table")
        exit(101)
    if DEVICE == None:
        print("error: FPGA \"DEVICE\" must be specified in .board file's `[part]` table")
        exit(101)
    # verify the board has pin assignments
    if board_config is None or (board_config is not None and 'pins' not in board_config.keys()):
        print("warning: no pin assignments found due to missing `[pins]` table in board file")

    # --- Process data -------------------------------------------------------------

    # Define initial project settings
    PROJECT_SETTINGS = """\
# Quartus project TCL script automatically generated by Orbit. DO NOT EDIT.
load_package flow

#### General project settings ####

# Create the project and overwrite any settings or files that exist
project_new """ + Env.quote_str(PROJECT) + """ -revision """ + Env.quote_str(PROJECT) + """ -overwrite
# Set default configurations and device
set_global_assignment -name NUM_PARALLEL_PROCESSORS """ + Env.quote_str("ALL") + """
set_global_assignment -name VHDL_INPUT_VERSION VHDL_1993
set_global_assignment -name VERILOG_INPUT_VERSION SYSTEMVERILOG_2005
set_global_assignment -name EDA_SIMULATION_TOOL "ModelSim-Altera (VHDL)"
set_global_assignment -name EDA_OUTPUT_DATA_FORMAT "VHDL" -section_id EDA_SIMULATION
set_global_assignment -name EDA_GENERATE_FUNCTIONAL_NETLIST OFF -section_id EDA_SIMULATION
set_global_assignment -name FAMILY """ + Env.quote_str(FAMILY) + """
set_global_assignment -name DEVICE """ + Env.quote_str(DEVICE) + """
# Use single uncompressed image with memory initialization file
set_global_assignment -name EXTERNAL_FLASH_FALLBACK_ADDRESS 00000000
set_global_assignment -name USE_CONFIGURATION_DEVICE OFF
set_global_assignment -name INTERNAL_FLASH_UPDATE_MODE "SINGLE IMAGE WITH ERAM" 
# Configure tri-state for unused pins     
set_global_assignment -name RESERVE_ALL_UNUSED_PINS_WEAK_PULLUP "AS INPUT TRI-STATED"
"""

    # 1. write TCL file for quartus project

    tcl = Tcl('orbit.tcl')

    tcl.push(PROJECT_SETTINGS, raw=True)

    tcl.push('#### Application-specific settings ####', end='\n\n', raw=True)

    tcl.push('# Add source code files to the project', raw=True)

    # generate the required tcl text for adding source files (vhdl, verilog, sv, bdf)
    src: Step
    for src in src_files:
        if src.is_vhdl():
            tcl.push("set_global_assignment -name VHDL_FILE "+Env.quote_str(src.path)+" -library "+Env.quote_str(src.lib), raw=True)
        elif src.is_vlog():
            tcl.push("set_global_assignment -name VERILOG_FILE "+Env.quote_str(src.path)+" -library "+Env.quote_str(src.lib), raw=True)
        elif src.is_sysv():
            tcl.push("set_global_assignement -name SYSTEMVERILOG_FILE "+Env.quote_str(src.path)+" -library "+Env.quote_str(src.lib), raw=True)
        pass

    for bdf in bdf_files:
        tcl.push("set_global_assignment -name BDF_FILE "+Env.quote_str(bdf), raw=True)

    # set the top level entity
    tcl.push('# Set the top level entity', raw=True)
    tcl.push("set_global_assignment -name TOP_LEVEL_ENTITY "+Env.quote_str(top_unit), raw=True)

    # set generics for top level entity
    if len(generics) > 0:
        tcl.push('# Set generics for top level entity', raw=True)
        generic: Generic
        for generic in generics:
            tcl.push("set_parameter -name "+Env.quote_str(generic.key)+" "+Env.quote_str(str(generic.val)), raw=True)
        pass

    # set the pin assignments
    if board_config is not None and 'pins' in board_config.keys():
        tcl.push('# Set the pin assignments', raw=True)
        for (pin, port) in board_config['pins'].items():
            tcl.push("set_location_assignment "+Env.quote_str(pin)+" -to "+Env.quote_str(port), raw=True)
        pass

    # run a preset workflow
    if flow is not None:
        tcl.push('execute_flow '+flow, raw=True)
        pass

    # close the newly created project
    tcl.push('project_close', raw=True)

    # finish writing the TCL script and save it to disk
    tcl.save()

    # 2. run quartus with TCL script

    # execute quartus using the generated tcl script
    Command("quartus_sh").args(['-t', tcl.get_path()]).spawn().unwrap()

    # 3. perform a specified toolflow

    # synthesize design
    if synth == True:
        Command("quartus_map").arg(PROJECT).spawn().unwrap()
    # route design to board
    if impl == True:
        Command("quartus_fit").arg(PROJECT).spawn().unwrap()
    # perform static timing analysis
    if sta == True:
        Command("quartus_sta").arg(PROJECT).spawn().unwrap()
    # generate bitstream
    if asm == True:
        Command("quartus_asm").arg(PROJECT).spawn().unwrap()
    # generate necessary files for timing simulation
    if eda_netlist == True:
        Command("quartus_eda").args([PROJECT, '--simulation']).spawn().unwrap()

    # 4. program the FPGA board

    # auto-detect the FPGA programming cable
    if pgm_temporary == True or pgm_permanent == True:
        out, status = Command("quartus_pgm").arg('-a').output()
        status.unwrap()
        if out.startswith('Error ') == True:
            print(out, end='')
            exit(101)
        tokens = out.split()
        # grab the second token (cable name)
        CABLE = tokens[1]
        pass

    prog_args = ['-c', CABLE, '-m', 'jtag', '-o']
    # program the FPGA board with temporary SRAM file
    if pgm_temporary == True:
        if os.path.exists(PROJECT+'.sof') == True:
            Command('quartus_pgm').args(prog_args).args(['p'+';'+PROJECT+'.sof']).spawn().unwrap()
        else:
            exit('error: bitstream .sof file not found')
        pass
    # program the FPGA board with permanent program file
    elif pgm_permanent == True:
        if os.path.exists(PROJECT+'.pof') == True:
            Command('quartus_pgm').args(prog_args).args(['bpv'+';'+PROJECT+'.pof']).spawn().unwrap()
        else:
            exit('error: bitstream .pof file not found')
        pass

    # 5. open the quartus project

    # open the project using quartus GUI
    if open_project == True:
        Command('quartus').arg(PROJECT+'.qpf').spawn().unwrap()
        pass
    pass
    
if __name__ == '__main__':
    main()
