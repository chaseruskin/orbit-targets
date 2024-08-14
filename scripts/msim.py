# Profile: Hyperspace Labs
# Target: msim
# Reference: https://www.microsemi.com/document-portal/doc_view/131617-modelsim-reference-manual
# 
# Runs ModelSim in batch mode to perform HDL simulations.

from mod import Env, Generic, Command, Blueprint, Step
from typing import List
import os
import argparse

def main():
    # append modelsim installation path to PATH env variable
    Env.add_path(Env.read("ORBIT_ENV_MODELSIM_PATH", missing_ok=True))

    # handle command-line arguments
    parser = argparse.ArgumentParser(prog='msim', allow_abbrev=False)

    parser.add_argument('--lint', action='store_true', default=False, help='run static code analysis and exit')
    parser.add_argument('--stop-at-sim', action='store', help='stop after setting up the simulation')
    parser.add_argument('--gui', action='store_true', default=False, help='open the gui')
    parser.add_argument('--generic', '-g', action='append', type=Generic.from_arg, default=[], metavar='KEY=VALUE', help='override top-level VHDL generics')
    parser.add_argument('--top-config', default=None, help='define the top-level configuration unit')

    args = parser.parse_args()

    # set up environment and constants
    TB_NAME = Env.read("ORBIT_TB_NAME", missing_ok=True)

    DO_FILE = 'orbit.do'
    WAVEFORM_FILE = 'vsim.wlf'

    # testbench's VHDL configuration unit
    TOP_LEVEL_CONFIG = args.top_config

    OPEN_GUI = bool(args.gui)
    STOP_AT_SIM = bool(args.stop_at_sim)
    LINT_ONLY = bool(args.lint)

    GENERICS: List[Generic] = args.generic


    tb_do_file: str = None
    compile_order: List[Step] = []

    step: Step

    # process blueprint
    for step in Blueprint().parse():
        if step.is_builtin() == True:
            compile_order += [step]
        if step.is_aux('DO'):
            tb_do_file = step.path
            pass
        pass

    print("info: compiling HDL source code ...")
    libraries = []
    work_lib = 'work'
    # compile hdl source code
    for step in compile_order:
        print('  ->', Env.quote_str(step.path))
        # create new libraries and their mappings
        if step.lib not in libraries:
            Command('vlib').arg(step.lib).spawn().unwrap()
            Command('vmap').arg(step.lib).arg(step.lib).spawn().unwrap()
            libraries.append(step.lib)
        # compile source code
        if step.is_vhdl():
            Command('vcom').arg('-work').arg(step.lib).arg(step.path).spawn().unwrap()
        elif step.is_vlog():
            Command('vlog').arg('-work').arg(step.lib).arg(step.path).spawn().unwrap()
        elif step.is_sysv():
            Command('vlog').arg('-sv').arg('-work').arg(step.lib).arg(step.path).spawn().unwrap()
        # the last file to write the library is the working library
        work_lib = step.lib
        pass

    if LINT_ONLY == True:
        print("info: static analysis complete")
        exit(0)

    # prepare the simulation
    if TB_NAME is None:
        print('error: cannot proceed any further without a testbench\n\nhint: stop here using \"--lint\" to exit safely or set a testbench to run a simulation')
        exit(101)

    # create a .do file to automate modelsim actions
    print("info: generating .do file ...")
    with open(DO_FILE, 'w') as file:
        # prepend .do file data
        if OPEN_GUI == True:
            # add custom waveform/vsim commands
            if tb_do_file != None and os.path.exists(tb_do_file) == True:
                print("info: importing commands from .do file:", tb_do_file)
                with open(tb_do_file, 'r') as do:
                    for line in do.readlines():
                        # add all non-blank lines
                        if len(line.strip()) > 0:
                            file.write(line)
                    pass
            # write default to include all signals into waveform
            else:
                file.write('add wave *\n')
                pass
        if STOP_AT_SIM == False:
            file.write('run -all\n')
        if OPEN_GUI == False:
            file.write('quit\n')
        pass

    # determine to run as script or as gui
    mode = "-batch" if OPEN_GUI == False else "-gui"

    # override bench with top-level config
    TB_NAME = str(TOP_LEVEL_CONFIG) if TOP_LEVEL_CONFIG != None else str(TB_NAME)

    # reference: https://stackoverflow.com/questions/57392389/what-is-vsim-command-line
    print("info: starting simulation for testbench", Env.quote_str(TB_NAME), "...")
    Command('vsim') \
        .arg(mode) \
        .arg('-onfinish').arg('stop') \
        .arg('-do').arg(DO_FILE) \
        .arg('-wlf').arg(WAVEFORM_FILE) \
        .arg('-work').arg(work_lib) \
        .arg('+nowarn3116') \
        .arg(TB_NAME) \
        .args(['-g' + item.to_str() for item in GENERICS]) \
        .spawn() \
        .unwrap()
    pass


if __name__ == '__main__':
    main()
