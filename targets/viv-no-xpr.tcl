# ------------------------------------------------------------------------------
# Script   : viv-no-xpr.tcl
# Author   : Chase Ruskin
# Modified : 2022-09-05
# Created  : 2022-09-04
# Details  :
#   Complete toolchain for Vivado in non-project mode.
#   
#   Referenced from:
#       https://grittyengineer.com/vivado-non-project-mode-releasing-vivados-true-potential/
#
#
# Provides entire basic toolchain for Xilinx Vivado: synthesis, implementation,
# and generating bitstream. The default process is to only perform synthesis on
# the targeted top-level. Any process chosen will also execute the processes 
# required before it (synth -> impl -> route -> bit).
#
# If '--pgm' is supplied with no toolchain process, it will attempt to only 
# program a connected device with an already existing bitfile named after the
# toplevel $ORBIT_TOP. Otherwise, to generate a fresh bitfile and then program the
# device, also supply the '--bit' option.
#
# If '--synth' or a toolchain process is supplied, then '--part <num>' must be 
# specified as well because there is no set default part number. Top-level 
# generics can be overridden during synthesis by using the '--generic' option.
# Unknown generics are ignored by the synthesis tool.
#
# Assumes Vivado is already added to the PATH environment variable.
#
# Usage:
#     orbit build --plugin viv-no-xpr -- [options]
#
# Options:
#     --part <num>                    specify target xilinx device 
#     --synth                         analyze & synthesize
#     --impl                          implementation & optimization
#     --route                         route design
#     --bit                           generate a bitstream
#     --pgm                           program a connected FPGA device
#     --clean                         clear existing output directory
# -g, --generic <name>=<value>...     override top-level generics/parameters
#
# Dependencies:
#     Vivado (tested: 2019.2)
#
# Examples:
#     orbit build --plugin viv-no-xpr -- --clean --synth --part xc7z010
#     orbit build --plugin viv-no-xpr -- --bit --pgm --part xc7z020
#
# ------------------------------------------------------------------------------

# try to disable webtalk (may have no affect if using WEBPACK license)
config_webtalk -user "off"

# --- Constants ----------------------------------------------------------------
# ------------------------------------------------------------------------------

set DEFAULT_FLOW 0
set SYNTH_FLOW   1
set IMPL_FLOW    2
set ROUTE_FLOW   3
set BIT_FLOW     4

set ON  1
set OFF 0

set ERR_CODE 1
set OK_CODE  0

# --- Procedures ---------------------------------------------------------------
# ------------------------------------------------------------------------------

proc program_device { bit_file } {
    # connect to the digilent cable on localhost
    open_hw_manager
    connect_hw_server -allow_non_jtag
    open_hw_target

    # find the Xilinx FPGA device connected to the local machine
    set device [lindex [get_hw_devices "xc*"] 0]
    puts "info: detected device $device ..."
    current_hw_device $device
    refresh_hw_device -update_hw_probes false $device
    set_property PROBES.FILE {} $device
    set_property FULL_PROBES.FILE {} $device
    set_property PROGRAM.FILE $bit_file $device
    # program and refresh the fpga device
    program_hw_devices $device
    refresh_hw_device $device 
}

# --- Handle command-line inputs -----------------------------------------------
# ------------------------------------------------------------------------------

# target xilinx device
set PART ""
# toolchain stages to perform
set FLOW $DEFAULT_FLOW
# flag to remove or keep existing output directory 
set CLEAN $OFF
# flag to program a connected device with a bitfile
set PROGRAM_BOARD $OFF
# list of top-level generics to override during synthesis
set generics {}

set prev_arg ""
for {set i 0 } { $i < $argc } { incr i } {
    # set the current argument to handle
    set cur_arg [lindex $argv $i]

    # check for single flags
    switch $cur_arg {
        "--synth" {
            if { $FLOW < $SYNTH_FLOW } { set FLOW $SYNTH_FLOW }
        }
        "--impl" {
            if { $FLOW < $IMPL_FLOW } { set FLOW $IMPL_FLOW }
        }
        "--route" {
            if { $FLOW < $ROUTE_FLOW } { set FLOW $ROUTE_FLOW }
        }
        "--bit" {
            if { $FLOW < $BIT_FLOW } { set FLOW $BIT_FLOW }
        }
        "--clean" {
            set CLEAN $ON
        }
        "--pgm" {
            set PROGRAM_BOARD $ON
        }
        default {
            # check for optional values 
            switch $prev_arg {
                "--part" {
                    set PART $cur_arg
                }
                "-g" -
                "--generic" {
                    # take the value assigned after the '=' sign from command-line
                    incr i
                    # verify still within argument array bounds
                    if { $i >= $argc } {
                        puts "ERROR: Expecting <value> for $cur_arg with '$prev_arg' option"
                        exit $ERR_CODE
                    }
                    set value [lindex $argv $i]
                    # add to list of generics to later pass to synthesis stage
                    lappend generics "-generic" "$cur_arg=$value"
                }
            }
        }
    }
    # update previous argument to remember for next state
    set prev_arg $cur_arg
}

# --- Initialize setup ---------------------------------------------------------
# ------------------------------------------------------------------------------

# verify the blueprint exists
if { [file exists $env(ORBIT_BLUEPRINT)] == 0 } {
    puts "ERROR: Orbit blueprint file does not exist in current build directory"
    exit $ERR_CODE
}

# verify a toplevel is set
if { $env(ORBIT_TOP) == "" } {
    puts "ERROR: No toplevel set by Orbit through environment variable ORBIT_TOP"
    exit $ERR_CODE
}
# store the target bitfile filename
set BIT_FILE "$env(ORBIT_TOP).bit"

# create output directory
set OUTPUT_DIR $env(ORBIT_IP_NAME)
file mkdir $OUTPUT_DIR
set files [glob -nocomplain "$OUTPUT_DIR/*"]
if { $CLEAN == $ON && [llength $files] != 0 } {
    # clear folder contents
    puts "INFO: Deleting contents of $OUTPUT_DIR/"
    file delete -force {*}[glob -directory $OUTPUT_DIR *]; 
}

# access the blueprint's data
set blueprint_file $env(ORBIT_BLUEPRINT)
set blueprint_data [read [open $env(ORBIT_BLUEPRINT) r]]

# enter the output directory
cd $OUTPUT_DIR

# just program device if there is a bitstream file and no flow was specified
if { $FLOW == $DEFAULT_FLOW && $PROGRAM_BOARD == $ON } {
    program_device $BIT_FILE
    exit $OK_CODE
}

# --- Process data in blueprint ------------------------------------------------
# ------------------------------------------------------------------------------

foreach rule [split $blueprint_data "\n"] {
    # break rule into the 3 main components
    lassign [split $rule "\t"] fileset library path
    # branch to action according to rule's fileset
    switch $fileset {
        # synthesizable vhdl files
        "VHDL" {
            "read_vhdl" -library $library $path
        }
        # synthesizable verilog files
        "VLOG" {
            read_verilog -library $library $path
        }
        "SYSV" {
            read_verilog -sv -library $library $path
        }
        # Xilinx design constraints
        "XDCF" {
            read_xdc $path
        }
    }
}

# --- Execute toolchain --------------------------------------------------------
# ------------------------------------------------------------------------------

# 1. run synthesis
if { $FLOW >= $DEFAULT_FLOW } {
    synth_design -top $env(ORBIT_TOP) -part $PART {*}$generics
    write_checkpoint -force "post_synth.dcp"
    report_timing_summary -file "post_synth_timing_summary.rpt"
    report_utilization -file "post_synth_util.rpt"
}

# 2. run implementation
if { $FLOW >= $IMPL_FLOW } {
    opt_design
    place_design
    report_clock_utilization -file "clock_util.rpt"
    #get timing violations and run optimizations if needed
    if {[get_property SLACK [get_timing_paths -max_paths 1 -nworst 1 -setup]] < 0} {
        puts "INFO: Found setup timing violations => running physical optimization"
        phys_opt_design
    }
    write_checkpoint -force "post_place.dcp"
    report_utilization -file "post_place_util.rpt"
    report_timing_summary -file "post_place_timing_summary.rpt"
}

# 3. route design
if { $FLOW >= $ROUTE_FLOW } {
    route_design -directive Explore
    write_checkpoint -force "post_route.dcp"
    report_route_status -file "post_route_status.rpt"
    report_timing_summary -file "post_route_timing_summary.rpt"
    report_power -file "post_route_power.rpt"
    report_drc -file "post_imp_drc.rpt"
}

# 4. generate bitstream
if { $FLOW >= $BIT_FLOW } {
    write_verilog -force "cpu_impl_netlist_$env(ORBIT_TOP).v" -mode timesim -sdf_anno true
    write_bitstream -force $BIT_FILE

    # 4a. program to the connected device
    if { $PROGRAM_BOARD == $ON } {
        program_device $BIT_FILE
    }
}

exit 0