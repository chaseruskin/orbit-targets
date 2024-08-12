# Profile: Hyperspace Labs
# Target: voodoo
#
# Provide the glue logic between a project's files and the Xilinx Vivado tool.
# This script generates a tcl script to be executed by vivado in a subprocess.

from mod import Env, Command, Generic
import argparse
from enum import Enum
import os

class Esc:
    def __init__(self, inner: str):
        self._inner = inner

    def __str__(self):
        return str(self._inner)
    pass


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


class Tcl:
    def __init__(self, path: str):
        self._file: str = path
        self._data: str = ''
        self._indent: int = 0
        pass

    def push(self, code, end='\n', raw=False):
        if raw == True:
            self._data += ('  '*self._indent) + code
        else:
            for c in code:
                self._data += ('  '*self._indent)
                if isinstance(c, Esc) == True:
                    self._data += str(c) + ' '
                else:
                    self._data += "\"" + str(c) + "\"" + ' '
            pass
        self._data += end
        pass

    def save(self):
        with open(self._file, 'w') as f:
            f.write(self._data)
        pass

    def indent(self):
        self._indent += 1

    def dedent(self):
        self._indent -= 1
        if self._indent < 0:
            self._indent = 0
        pass

    def get_path(self) -> str:
        return self._file
    pass


def synthesize(tcl: Tcl, part: str, generics=[]):
    '''
    Performs synthesis.
    '''
    tcl.push(['synth_design', '-top', TOP, '-part', str(part)] + generics)
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


def bitstream(tcl: Tcl, bit_file: str):
    '''
    Peforms bitstream generation.
    '''
    tcl.push(['write_verilog', '-force', 'cpu_impl_netlist_'+TOP+'.v', '-mode', 'timesim', '-sdf_anno', 'true'])
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

# collect command-line arguments
parser = argparse.ArgumentParser(prog='vivo', allow_abbrev=False)

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
TOP: str = str(Env.read('ORBIT_TOP', missing_ok=False))
BLUEPRINT_FILE: str = str(Env.read('ORBIT_BLUEPRINT', missing_ok=False))
BIT_FILE: str = str(TOP)+'.bit'

VIVADO_CMD = 'vivado.bat' if no_bat == False and os.name == 'nt' else 'vivado'

tcl = Tcl('orbit.tcl')

# try to disable webtalk
tcl.push(['config_webtalk', '-user', 'off'])

# read source code files from blueprint
with open(BLUEPRINT_FILE, 'r') as fh:
    steps = fh.read().splitlines()
    for step in steps:
        fileset, lib, path = step.split('\t', maxsplit=3)
        if fileset == 'VHDL':
            tcl.push(['read_vhdl', '-library', lib, path])
        if fileset == 'VLOG':
            tcl.push(['read_verilog', '-library', lib, path])
        if fileset == 'SYSV':
            tcl.push(['read_verilog', '-sv', '-library', lib, path])
        if fileset == 'XDCF':
            tcl.push(['read_xdc', path])
        pass
    pass

# select which toolflows to perform with vivado
if eda_step.value >= Step.Synth.value:
    synthesize(tcl, fpga_part, tcl_generics)
if eda_step.value >= Step.Impl.value:
    implement(tcl)
if eda_step.value >= Step.Route.value:
    route(tcl)
if eda_step.value >= Step.Bit.value:
    bitstream(tcl, BIT_FILE)
if eda_step.value >= Step.Pgm.value:
    program_device(tcl, BIT_FILE)

tcl.save()

child = Command(VIVADO_CMD) \
    .args(['-mode', 'batch', '-nojournal', '-nolog', '-source', tcl.get_path()]) \
    .spawn()

exit(0)
