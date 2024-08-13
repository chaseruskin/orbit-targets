# orbit-profile

[Orbit](https://github.com/chaseruskin/orbit) configurations for FPGA development.
  
## Installing

To apply these configurations to Orbit:

1. Download the profile from its remote repository using `git`:

```
git clone https://github.com/hyperspace-labs/orbit-profile.git "$(orbit env ORBIT_HOME)/profiles/hyperspace-labs"
```

2. Install the required Python packages using `pip`:
```
pip install -r "$(orbit env ORBIT_HOME)/profiles/hyperspace-labs/requirements.txt"
```

1. Include the profile's configuration file using `orbit`:

```
orbit config --push include="profiles/hyperspace-labs/config.toml"
```

## Updating

To receive the latest changes:

```
git -C "$(orbit env ORBIT_HOME)/profiles/hyperspace-labs" pull
```