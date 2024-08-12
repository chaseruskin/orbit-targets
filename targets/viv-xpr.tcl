# ------------------------------------------------------------------------------
# Script   : viv-xpr.tcl
# Author   : Chase Ruskin
# Modified : 2022-09-21
# Created  : 2022-09-21
# Details  :
#   Simple toolchain for Vivado in project mode.
#   
#   Referenced from:
#       https://grittyengineer.com/vivado-project-mode-tcl-script/
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

# --- Handle command-line inputs -----------------------------------------------
# ------------------------------------------------------------------------------

# target xilinx device
set PART ""
# flag to remove or keep existing output directory 
set CLEAN $OFF

set prev_arg ""
for {set i 0 } { $i < $argc } { incr i } {
    # set the current argument to handle
    set cur_arg [lindex $argv $i]

    # check for single flags
    switch $cur_arg {
        "--clean" {
            set CLEAN $ON
        }
        default {
            # check for optional values 
            switch $prev_arg {
                "--part" {
                    set PART $cur_arg
                }
            }
        }
    }
    # update previous argument to remember for next state
    set prev_arg $cur_arg
}

# --- Initialize setup ---------------------------------------------------------
# ------------------------------------------------------------------------------

# verify the output directory exists
if { [file exists $env(ORBIT_BUILD_DIR)] == 0 } {
    puts "ERROR: Orbit build directory does not exist"
    exit $ERR_CODE
}
# enter the build directory
cd $env(ORBIT_BUILD_DIR)

# verify the blueprint exists
if { [file exists $env(ORBIT_BLUEPRINT)] == 0 } {
    puts "ERROR: Orbit blueprint file does not exist in current build directory"
    exit $ERR_CODE
}

# create output directory
set OUTPUT_DIR "viv-xpr/$env(ORBIT_IP_NAME)"
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

# check if existing project exists
if { [file exists "$env(ORBIT_IP_NAME).xpr"] != 0 && $CLEAN == $OFF } {
    # open existing project
    open_project "$env(ORBIT_IP_NAME).xpr"
} else {
    # check if part was supplied by user
    if { $PART == "" } {
        puts "WARNING: Using default Xilinx part because --part <num> was not set"
        # create the project
        create_project $env(ORBIT_IP_NAME) "."
    } else {
        # create the project with specified part
        create_project -part $PART $env(ORBIT_IP_NAME) "."
    }
}

# set target language
set_property target_language "VHDL" [current_project]
# set simulation language
set_property simulator_language "VHDL" [current_project]
# set new part if overwritten
if { $PART != "" } {
    set_property part $PART [current_project]
}

# --- Process data in blueprint ------------------------------------------------
# ------------------------------------------------------------------------------

foreach rule [split $blueprint_data "\n"] {
    # break rule into the 3 main components
    lassign [split $rule "\t"] fileset library path
    # branch to action according to rule's fileset
    switch $fileset {
        # synthesizable vhdl files
        "VHDL-RTL" {
            set file_obj [add_files -fileset [current_fileset] $path]
            if { $file_obj != "" } {
                set_property library $library $file_obj
            }
        }
        # simulation vhdl files
        "VHDL-SIM" {
            set file_obj [add_files -fileset sim_1 $path]
            if { $file_obj != "" } {
                set_property library $library $file_obj
            }
        }
        # xilinx design constraints
        "XIL-XDC" {
            add_files -fileset constrs_1 $path
        }
        # python software model
        "PY-MODEL" {
            # run python software model (ignore python environment variables set by Vivado)
            exec "python" "-E" $path
            # take generated files ending in .dat and import them into simulation fileset
            set data_files [glob "*.dat"]
            import_files -fileset sim_1 -force $data_files
        }
    }
}

# set rtl top level
if { $env(ORBIT_TOP) != "" } {
    set_property top $env(ORBIT_TOP) [get_fileset "sources_1"]
}

# set sim top level
if { $env(ORBIT_BENCH) != "" } {
    set_property top $env(ORBIT_BENCH) [get_fileset "sim_1"]
}

update_compile_order -fileset sources_1
update_compile_order -fileset sim_1

# open the gui
start_gui
