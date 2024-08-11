# Orbit Profile

A collection of settings for [Orbit](https://github.com/cdotrus/orbit), an agile package manager and extensible build tool for hardware description languages (HDLs).
  
## Installing

To access the configurations and get the most out of these settings, you should at least have `git` and `python` installed and found on your system's PATH.

1. Download the profile from its remote repository using `git`:

```
git clone https://github.com/hyperspace-labs/orbit-profile.git "$(orbit env ORBIT_HOME)/profiles/hyperspace-labs"
```

2. Install the required Python packages using `pip`:
```
pip install -r "$(orbit env ORBIT_HOME)/profiles/hyperspace-labs/requirements.txt"
```

1. Include the profile's configuration in Orbit's global config file using `orbit`:

```
orbit config "$(orbit env ORBIT_HOME)/config.toml" --push include="profiles/hyperspace-labs/config.toml"
```

## Updating

To receive the latest changes:

```
git -C "$(orbit env ORBIT_HOME)/profiles/hyperspace-labs" pull
```