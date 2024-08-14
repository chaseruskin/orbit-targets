# orbit-targets

[Orbit](https://github.com/chaseruskin/orbit) targets for FPGA development.

## Available Tools

The following tools have targets implementations:

### Simulators
- GHDL
- ModelSim

### FPGA Toolchains
- Xilinx Vivado (project mode and non-project mode)
- Intel Quartus Prime

## Installing

To apply these configurations to Orbit:

1. Clone this repository using `git`:

```
git clone https://github.com/chaseruskin/orbit-targets.git "$(orbit env ORBIT_HOME)/targets/chaseruskin"
```

2. Install the required Python packages using `pip`:
```
pip install -r "$(orbit env ORBIT_HOME)/targets/chaseruskin/requirements.txt"
```

1. Include the configuration file using `orbit`:

```
orbit config --push include="targets/chaseruskin/config.toml"
```

## Updating

To receive the latest changes:

```
git -C "$(orbit env ORBIT_HOME)/targets/chaseruskin" pull
```