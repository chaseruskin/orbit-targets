# Provides the glue logic between a filelist and the Xilinx Vivado EDA tool.
# This script generates a tcl script and executes it using Vivado in a 
# subprocess.
#
# Dependencies:
#   Vivado (tested: 2019.2)
#
# Reference:
#   https://grittyengineer.com/vivado-non-project-mode-releasing-vivados-true-potential/

from mod import Env, Command, Generic, Blueprint, Tcl, Esc
import argparse
from enum import Enum
import os

class Step(Enum):
    Synth = 0
    Impl = 1
    Route = 2
    Bit = 3
    Pgm = 4
    
    @staticmethod
    def from_str(s: str):
        s = str(s).lower()
        if s == 'synth':
            return Step.Synth
        if s == 'impl':
            return Step.Impl
        if s == 'route':
            return Step.Route
        if s == 'bit':
            return Step.Bit
        if s == 'pgm':
            return Step.Pgm
        pass
    pass


def synthesize(tcl: Tcl, top: str, part: str, generics=[]):
    '''
    Performs synthesis.
    '''
    tcl.push(['synth_design', '-top', top, '-part', str(part)] + generics)
    tcl.push(['write_checkpoint', '-force', 'post_synth.dcp'])
    tcl.push(['report_timing_summary', '-file', 'post_synth_timing_summary.rpt'])
    tcl.push(['report_utilization', '-file', 'post_synth_util.rpt'])
    pass


def implement(tcl: Tcl):
    '''
    Performs implementation.
    '''
    tcl.push(['opt_design'])
    tcl.push(['place_design'])
    tcl.push(['report_clock_utilization', '-file', 'clock_util.rpt'])
    # get timing violations and run optimizations if needed
    tcl.push('if {[get_property SLACK [get_timing_paths -max_paths 1 -nworst 1 -setup]] < 0} {', raw=True)
    tcl.indent()
    tcl.push(['puts', 'info: found setup timing violations: running physical optimization ...'])
    tcl.push(['phys_opt_design'])
    tcl.dedent()
    tcl.push('}', raw=True)
    tcl.push(['write_checkpoint', '-force', 'post_place.dcp'])
    tcl.push(['report_utilization', '-file', 'post_place_util.rpt'])
    tcl.push(['report_timing_summary', '-file', 'post_place_timing_summary.rpt'])
    pass


def route(tcl: Tcl):
    '''
    Performs routing.
    '''
    tcl.push(['route_design', '-directive', 'Explore'])
    tcl.push(['write_checkpoint', '-force', 'post_route.dcp'])
    tcl.push(['report_route_status', '-file', 'post_route_status.rpt'])
    tcl.push(['report_timing_summary', '-file', 'post_route_timing_summary.rpt'])
    tcl.push(['report_power', '-file', 'post_route_power.rpt'])
    tcl.push(['report_drc', '-file', 'post_impl_drc.rpt'])
    pass


def bitstream(tcl: Tcl, top: str, bit_file: str):
    '''
    Peforms bitstream generation.
    '''
    tcl.push(['write_verilog', '-force', 'cpu_impl_netlist_'+top+'.v', '-mode', 'timesim', '-sdf_anno', 'true'])
    tcl.push(['write_bitstream', '-force', bit_file])
    pass
    

def program_device(tcl: Tcl, bit_file: str):
    '''
    Programs the generated bitstream to the connected FPGA.
    '''
    # connect to the digilent cable on localhost
    tcl.push(['open_hw_manager'])
    tcl.push(['connect_hw_server', '-allow_non_jtag'])
    tcl.push(['open_hw_target'])
    # find the Xilinx FPGA device connected to the local machine
    tcl.push('set device [lindex [get_hw_devices "xc*"] 0]', raw=True)
    tcl.push(['puts', 'info: detected device $device ...'])
    tcl.push(['current_hw_device', '$device'])
    tcl.push(['refresh_hw_device', '-update_hw_probes', 'false', '$device'])
    tcl.push(['set_property', 'PROBES.FILE', Esc('{}'), '$device'])
    tcl.push(['set_property', 'FULL_PROBES.FILE', Esc('{}'), '$device'])
    tcl.push(['set_property', 'PROGRAM.FILE', bit_file, '$device'])
    # program and refresh the fpga device
    tcl.push(['program_hw_devices', '$device'])
    tcl.push(['refresh_hw_device', '$device'])
    pass


def main():
    # collect command-line arguments
    parser = argparse.ArgumentParser(prog='voodoo', allow_abbrev=False)

    parser.add_argument('--generic', '-g', action='append', type=Generic.from_arg, default=[], metavar='KEY=VALUE', help='override top-level VHDL generics')
    parser.add_argument('--part', required=True, help='specify the FPGA part number')
    parser.add_argument('--run', '-r', required=True, choices=['synth', 'impl', 'route', 'bit', 'pgm'], help='select the step to perform')
    parser.add_argument('--no-bat', action='store_true', help='do not use .bat extension to call vivado')

    args = parser.parse_args()

    # convert argument values to script variables
    fpga_part = str(args.part)
    no_bat = bool(args.no_bat)
    eda_step = Step.from_str(args.run)
    tcl_generics = []
    for g in args.generic:
        tcl_generics += ['-generic', str(g)]
        pass

    # convert environment variables to script constants
    TOP: str = str(Env.read('ORBIT_TOP_NAME', missing_ok=False))
    BIT_FILE: str = str(TOP)+'.bit'

    VIVADO_CMD = 'vivado.bat' if no_bat == False and os.name == 'nt' else 'vivado'

    tcl = Tcl('orbit.tcl')

    # try to disable webtalk
    tcl.push(['config_webtalk', '-user', 'off'])

    steps = Blueprint().parse()
    for step in steps:
        if step.is_vhdl():
            tcl.push(['read_vhdl', '-library', step.lib, step.path])
        if step.is_vlog():
            tcl.push(['read_verilog', '-library', step.lib, step.path])
        if step.is_sysv():
            tcl.push(['read_verilog', '-sv', '-library', step.lib, step.path])
        if step.is_aux('XDCF'):
            tcl.push(['read_xdc', step.path])
            pass
        pass

    # select which toolflows to perform with vivado
    if eda_step.value >= Step.Synth.value:
        synthesize(tcl, TOP, fpga_part, tcl_generics)
    if eda_step.value >= Step.Impl.value:
        implement(tcl)
    if eda_step.value >= Step.Route.value:
        route(tcl)
    if eda_step.value >= Step.Bit.value:
        bitstream(tcl, TOP, BIT_FILE)
    if eda_step.value >= Step.Pgm.value:
        program_device(tcl, BIT_FILE)

    tcl.save()
    Command(VIVADO_CMD) \
        .args(['-mode', 'batch', '-nojournal', '-nolog', '-source', tcl.get_path()]) \
        .spawn()
    exit(0)


if __name__ == '__main__':
    main()
