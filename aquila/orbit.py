"""
Functions and classes mapped to interfacing with Orbit.
"""

from aquila.process import Command
import json
from aquila import env
import toml
from typing import List as _List
from aquila import log


def get_unit_json(name: str) -> dict:
    """
    Returns the JSON dictionary for the desired unit, None if not found.
    """
    data = ''
    if name is not None:
        data: str = Command([env.read('ORBIT'), 'get', '--json', name]).output()[0]
    if len(data.strip()) == 0:
        log.error('failed to get json data for unit:', name)
    try:
        return json.loads(data)
    except:
        log.error('failed to get json data for unit:', name)


def verify_generics(data: dict, ext_generics: dict) -> bool:
    """
    Verifies all generics have some value, either from the command-line or as a default, where
    `data` is JSON dictionary for the core to check its generic values and `ext_generics` is the list of generics passed
    from the command-line.

    Exits 101 if a generic value is not supplied.
    """
    unit_gens = data['generics']
    missing_gen = False
    def_gen_names = []
    # check if all generics have a value
    for gen in unit_gens:
        def_gen_names += [gen['name']]
        if gen['default'] is None:
            # check the generic has a value from an external source
            if gen['name'] not in ext_generics or ext_generics[gen['name']] is None:
                log.error('missing value for generic "'+gen['name']+'"', exit_on_err=False)
                missing_gen = True
    
    invalid_gen = False
    # check if an invalid generic was supplied
    for gen in ext_generics.keys():
        if gen not in def_gen_names:
            log.error('generic "'+gen+'" does not exist for unit '+data['name'], exit_on_err=False)
            invalid_gen = True

    if missing_gen == True or invalid_gen == True:
        exit(101)


class Manifest:
    """
    Module for interfacing with an Orbit project's manifest file.
    """

    def __init__(self, path: str=None):
        self.path = path if path is not None else env.read('ORBIT_MANIFEST_FILE', missing_ok=False)
        self.data = dict()
        with open(self.path, 'r') as fd:
            self.data = toml.loads(fd.read())

    def get(self, table: str):
        """
        Attempts to fetch data from `table` with the internal TOML dictionary.

        Returns None if missing a key along with way.
        """
        parts = table.split('.')
        subtable = self.data
        for p in parts:
            try:
                subtable = subtable[p]
            except:
                return None
        return subtable
    

class Entry:
    """
    A single source item within a blueprint.
    """

    def __init__(self, fset: str, lib: str, path: str, deps: list=[]):
        self.fset = str(fset).upper().replace(' ', '-').replace('_', '-')
        self.lib = lib
        self.path = path
        self.deps = deps

    def is_builtin(self) -> bool:
        """
        Checks if the entry belongs to a builtin fileset (VHDL, VLOG, SYSV).
        """
        return self.fset == 'VHDL' or self.fset == 'VLOG' or self.fset == 'SYSV'
    
    def is_set(self, fset) -> bool:
        """
        Checks if the given entry belongs to this fileset `fset`.
        """
        return self.fset == str(fset).upper().replace(' ', '-').replace('_', '-')
    
    def is_aux(self, fset: str) -> bool:
        return self.fset == str(fset).upper().replace(' ', '-').replace('_', '-')

    def is_vhdl(self) -> bool:
        """
        Checks if the given entry belongs to the builtin VHDL filset.
        """
        return self.fset == 'VHDL'
    
    def is_vlog(self) -> bool:
        """
        Checks if the given entry belongs to the builtin VLOG filset.
        """
        return self.fset == 'VLOG'
    
    def is_sysv(self) -> bool:
        """
        Checks if the given entry belongs to the builtin SYSV filset.
        """
        return self.fset == 'SYSV'
    
    def get_deps(self) -> list:
        """
        Returns the list of file dependencies for the given entry.
        """
        return self.deps


class Blueprint:
    """
    A data structure that contains the topologically sorted list of all source entries.
    """

    def __init__(self, path: str=None, plan: str=None):
        """
        Loads entries from a blueprint.

        If no path and/or plan is provided, then it reads from the Orbit set environment variables.
        """
        import json
        self._file = path if path is not None else env.read("ORBIT_BLUEPRINT", missing_ok=False)
        self._plan = plan if plan is not None else env.read("ORBIT_BLUEPRINT_PLAN", missing_ok=False)

        self._entries = []
        # extract the list of entries from the file according to its plan
        with open(self._file, 'r') as bp:
            if self.get_plan() == 'tsv':
                for line in bp.readlines():
                    fset, lib, path = line.strip().split('\t')
                    self._entries += [Entry(fset, lib, path)]
            elif self.get_plan() == 'json':
                data = json.load(bp)
                for d in data:
                    self._entries += [Entry(d['fileset'], d['library'], d['filepath'], d['dependencies'])]
    
    def get_entries(self) -> _List[Entry]:
        """
        Returns the topologically sorted list of entries from the current
        blueprint.
        """
        return self._entries
    
    def get_plan(self) -> str:
        """
        Returns which plan was used for the current blueprint.
        """
        return self._plan

    def get_file(self) -> str:
        """
        Return the name of the file used to load the current list of entries.
        """
        return self._file