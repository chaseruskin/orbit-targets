# Plugin: orbit-xsim.py
# About: 
#   A quick and simple plugin to orchestrate the building process for the Vivado 
#   simulator (xsim) as a backend for Orbit.
# Note:
#   Assumes Vivado's command-line tools are available via your PATH environment
#   variable.
#
# Filesets:
#   XSIM-TCL  = *.tcl
#   XSIM-WCFG = *.wcfg
#
# Simulation Modes:
#   'cl'- Run completely in console. This will run the simulation until it finishes with
#   no interaction or gui.
#
#   'gui'- Interactively load the simulation and open it in the gui. This will not run
#   the simulation, but will load it into the gui to run and restart.
#
#   'review'- View the waveform. This will only open the waveform in the gui for inspection.
#
import os,sys, getopt
from typing import List

# --- constants ----------------------------------------------------------------

# define python path
PYTHON_PATH = os.path.basename(sys.executable)

VIVADO_PATH = os.environ.get("ORBIT_ENV_VIVADO_PATH")
# temporarily appends vivado installation path to PATH env variable
if(VIVADO_PATH != None and os.path.exists(VIVADO_PATH) and VIVADO_PATH not in os.getenv('PATH')):
    os.environ['PATH'] = os.getenv('PATH') + ';' + VIVADO_PATH

XSIM_DIR = 'xsim'

# --- classes and functions ----------------------------------------------------

class Generic:
    def __init__(self, key: str, val: str):
        self.key = key
        self.val = val
        pass
    pass


    @classmethod
    def from_str(self, s: str):
        # split on equal sign
        words = s.split('=', 1)
        if len(words) != 2:
            return None
        return Generic(words[0], words[1])


    def to_str(self) -> str:
        return self.key+'='+self.val
    pass


def quote_str(s: str) -> str:
    '''Wraps the string `s` around double quotes `\"` characters.'''
    return '\"' + s + '\"'


def invoke(command: str, args: List[str], verbose: bool=False, exit_on_err: bool=True):
    '''
    Runs a subprocess calling `command` with a series of `args`.

    Prints the command if `verbose` is `True`.
    '''
    code_line = command + ' '
    for c in args:
        code_line = code_line + quote_str(c) + ' '
    rc = os.system(code_line)
    if verbose == True:
        print(code_line)
    # immediately stop script upon a bad return code
    if(rc != 0 and exit_on_err == True):
        exit('ERROR: plugin exited with error code: '+str(rc))


# --- Handle command-line arguments --------------------------------------------

try: 
    opts, args = getopt.getopt(sys.argv[1:], "g:ces:", ["flow=", "generic=", "compile", "elaborate", "simulate=", "script"], )
except getopt.GetoptError:
    print("error: getopt threw error trying to parse command-line arguments\n")
    exit(2)

CL  = 0
GUI = 1
REVIEW = 2

generics = []

comp = False
elab = False
sim  = False
script_only = False

sim_mode = CL

for opt, arg in opts:
    if opt in ('--simulate'):
        sim = True
        if arg == 'cl':
            sim_mode = CL
        elif arg == 'gui':
            sim_mode = GUI
        elif arg == 'review':
            sim_mode = REVIEW
        else:
            print('option \''+str(opt)+"\' has value '"+str(arg)+"' but must have value 'cl' or 'gui'")
            exit(2)
    elif opt in ('--script'):
            script_only = True
    elif opt in ('--compile', '-c'):
        comp = True
    elif opt in ('--elaborate', '-e'):
        elab = True
    elif opt in ('--generic', '-g'):
        generics += [Generic.from_str(arg)]
    else:
        print('unknown option \''+str(opt)+'\'')
        exit(2)

# verify there are zero uncaught arguments
for arg in args:
    print('error: unknown argument \''+str(arg)+'\'')
    exit(2)

# verify a toolflow was selected
if(comp or elab or sim) == False:
    print('info: no toolflow performed\n')
    print("hint: include options '--compile', '--elaborate', or '--simulate <mode>' to use xsim")
    exit()

# --- process blueprint --------------------------------------------------------

# begin build process
os.chdir(os.environ.get("ORBIT_BUILD_DIR"))
# collect data
vhdl_sources = []
tcl_config = None
wf_config = None
py_model = None

TOP = os.environ.get("ORBIT_TOP")
BENCH = os.environ.get("ORBIT_BENCH")

with open(os.getenv("ORBIT_BLUEPRINT"), 'r') as blueprint:
    for rule in blueprint.readlines():
        fileset, identifier, path = rule.split('\t')
        # remove trailing newline
        path = path.strip()
        
        if fileset == 'VHDL-RTL' or fileset == 'VHDL-SIM':
            vhdl_sources += [(identifier, path)]
        # tcl files (currently does nothing)
        elif fileset == 'XSIM-TCL':
            tcl_config = path
        elif fileset == 'PY-MODEL':
            py_model = path
        # waveform file must be for the particular top-level
        elif fileset == 'XSIM-WCFG' and BENCH != None and len(BENCH) > 0 and identifier.lower() == BENCH.lower():
            wf_config = path
        pass
    pass

os.makedirs(XSIM_DIR, exist_ok=True)
os.chdir(XSIM_DIR)

# 1. pre-simulation hook: generate test vectors
if py_model != None:
    print("INFO: Running python software model ...")
    # format generics for SW MODEL
    py_generics = []
    for item in generics:
        py_generics += ['-g=' + item.to_str()]
    invoke(PYTHON_PATH, [py_model] + py_generics)
    pass

if script_only == True:
    exit(0)

# compile sources
if comp == True:
    print('info: compiling VHDL source files...')
    for (lib, path) in vhdl_sources:
        invoke('xvhdl', ['--incr', '--work', lib, path], verbose=False)
        pass

if BENCH == None or len(BENCH) == 0:
    exit('error: no testbench specified to perform commands any further for top-level entity \''+str(TOP)+'\'')

LOG_FILE = BENCH+'.log'

snapshot = BENCH

# elaborate the testbench
if elab == True:
    print('info: elaborating design for testbench \''+BENCH+'\'')
    # compile all generics
    gen_args = []
    for g in generics:
        gen_args += ['-generic_top', g.to_str()]
    # print(gen_args)
    invoke('xelab', ['-debug', 'typical', '-top', BENCH, '-snapshot', snapshot] + gen_args)

# verify a tcl file exists to load from
# if sim_mode == GUI and tcl_config == None:
#     exit('error: no tcl file \''+TOP+'_xsim.tcl\' found to load for testbench '+BENCH)

run_args = ['-R']
if(tcl_config != None and sim_mode == GUI and False): # disable tcl files for now
    run_args = ['--tclbatch', tcl_config]
elif(sim_mode == REVIEW):
    run_args = []

if(sim_mode == CL):
    log_wave_tcl_cmd = "log_wave -recursive *" if(wf_config == None) else "open_wave_config "+wf_config
    simple_tcl = log_wave_tcl_cmd+'\nrun all\nexit\n'
    with open('batch.tcl', 'w') as cl_tcl:
        cl_tcl.write(simple_tcl)
    run_args = ['--tclbatch', 'batch.tcl']

gui_args = ['--gui'] if(sim_mode == GUI or sim_mode == REVIEW) else []

# use an existing waveform config file if found for the current testbench and in gui mode
wave_args = ['--view '+wf_config] if(wf_config != None and (sim_mode == GUI or sim_mode == REVIEW)) else []

log_args = ['--log', LOG_FILE] if(sim_mode == CL) else []

# verify a .wdb file exists for review
if sim_mode == REVIEW and os.path.exists(snapshot+'.wdb') == False:
    exit('error: no waveform database file (.wdb) found for \''+snapshot+'\'')

snapshot_arg = [snapshot] if(sim_mode != REVIEW) else [snapshot+'.wdb']

# run simulation through xilinx xsim (`run_args` must be last)
if sim == True:
    xsim_args = snapshot_arg + gui_args + wave_args + log_args + run_args
    invoke('xsim', xsim_args)

    if sim_mode == CL:
        # open log to verify simulation passed
        errors = 0
        failures = 0
        with open(LOG_FILE, 'r') as log:
            for line in log.readlines():
                # skip comments
                if line.startswith('#'):
                    continue
                # count errors and failures
                line = line.lower()
                if line.startswith('error: '):
                    errors += 1
                elif line.startswith('failure: '):
                    failures += 1
            pass

        # verify the simulation passed with no problems
        if(errors > 0 or failures > 0):
            exit('error: simulation reported '+str(errors)+' errors and '+str(failures)+' failures')