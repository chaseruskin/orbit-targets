"""
Functionality for powering the process for automated test
identification, test running, and test reporting.
"""

from aquila import env
import hashlib
import time
from termcolor import colored
from aquila import log
from aquila.orbit import Manifest


def base36encode(number, alphabet='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
    """Converts an integer to a base36 string."""
    if not isinstance(number, int):
        raise TypeError('number must be an integer')
 
    base36 = ''
    sign = ''
 
    if number < 0:
        sign = '-'
        number = -number
 
    if 0 <= number < len(alphabet):
        return sign + alphabet[number]
 
    while number != 0:
        number, i = divmod(number, len(alphabet))
        base36 = alphabet[i] + base36
 
    return sign + base36


class Seed:
    """
    An integer value used to set randomness.
    """

    MIN_SEED_VALUE = 0
    MAX_SEED_VALUE = (2**32)-1

    def __init__(self, seed: int=None):
        import random
        self.seed = seed
        if seed is None:
            self.seed = random.randint(Seed.MIN_SEED_VALUE, Seed.MAX_SEED_VALUE)
    
    def get_seed(self) -> int:
        """
        Returns the random seed.
        """
        return self.seed
    
    @staticmethod
    def from_str(s: str):
        if s is not None:
            s = int(s)
        return Seed(s)


class TestModule:

    def __init__(self, dut: str=None, tb: str=None, generics: dict={}, seed: int=None, path: str=None):
        self.dut = dut
        self.tb = tb
        self.path = path
        self.generics = generics
        self.seed = seed
        self._hash = self._compute_hash()
        self.is_tb_dyn = False

    def _compute_hash(self) -> str:
        """
        Returns the unique hash for this test module.
        """
        gens = ''
        for (k, v) in list(self.generics.items()):
            gens += '_'+str(k)+'='+str(v).replace('.', '-').replace('/', '-').replace('\\', '-')
        seed = ''
        if self.seed is not None:
            seed = '_seed=' + str(self.seed)

        full_name = ''
        if self.dut is not None:
            full_name += self.dut
        if self.tb is not None:
            if self.dut is not None:
                full_name += '__'
            full_name += self.tb
        
        if len(seed) > 0 or len(gens) > 0:
            full_name += '_' + gens + seed
        full_hash = hashlib.sha256(bytes(full_name, encoding='utf-8'))
        return full_hash.hexdigest()
    
    def get_short_hash(self, size: int=8):
        return self._hash[:size]
    
    def set_path(self, path: str):
        self.path = path

    def get_path(self) -> str:
        return self.path

    def get_dut(self) -> str:
        return self.dut
    
    def get_tb(self) -> str:
        return self.tb
    
    def get_top(self) -> str:
        return self.dut if self.tb is None else self.tb
    
    def get_generics(self) -> dict:
        return self.generics
    
    def get_seed(self) -> int:
        return self.seed
    
    def set_tb(self, name: str):
        self.tb = name
        self.is_tb_dyn = True
        self._hash = self._compute_hash()

    def is_tb_dynamic(self) -> bool:
        """
        Checks if the TB was added during the build process.
        """
        return self.is_tb_dyn

    def set_seed(self, seed: int):
        self.seed = seed
        self._hash = self._compute_hash()

    def is_valid(self) -> bool:
        return self.dut is not None or self.tb is not None
    
    def __str__(self) -> str:
        result = ''
        if self.tb is not None and self.is_tb_dynamic() == False:
            result += self.tb
        if self.dut is not None:
            if self.tb is not None and self.is_tb_dynamic() == False:
                result += '::'
            result += self.dut
        if len(self.generics) > 0:
            result += ' (' + ' '.join([str(k)+'='+str(v) for (k, v) in self.generics.items()]) + ')'
        if self.seed is not None:
            result += ' #'+str(self.seed)
        return result


class TestRunner:

    def __init__(self, table: dict=None, default: TestModule=None):
        """
        Creates a new instance of the test runner
        """
        self.num_passed = 0
        self.start_time = None

        self.table = table if table is not None else Manifest().get('project.metadata.test')

        if self.table is None:
            self.table = []
    
        self.modules = []
        for entry in self.table:
            dut = entry.get('dut')
            tb = entry.get('tb')
            trials = entry.get('trials', [])
            if len(trials) == 0:
                self.modules += [TestModule(dut, tb, {}, None)]
            for trial in trials:
                generics = trial.get('generics', {})
                seed = trial.get('seed')
                self.modules += [TestModule(dut, tb, generics, seed)]
        if default is not None and default.is_valid():
            self.modules = [default]
        
        self.num_trials = len(self.modules)

    def is_isolated(self) -> bool:
        """
        Returns true if an explicit DUT/TB was provided.
        """
        return env.read('ORBIT_DUT_NAME') is not None or env.read('ORBIT_TB_NAME') is not None
    
    def get_modules(self) -> list:
        """
        Returns the list of modules to run.
        """
        return self.modules
    
    def disp_start(self):
        word = 'test' if self.num_trials == 1 else 'tests'
        stmt = '\nrunning '+str(self.num_trials)+' '+word
        print(stmt)
        # record the start time
        self.start_time = time.perf_counter()
    
    def disp_trial_start(self, trial: TestModule):
        stmt = 'test ' + str(trial)
        print(stmt, end=' ')

    def disp_trial_progress(self):
        stmt = '...'
        print(stmt, end=' ')
    
    def disp_trial_result(self, ok: bool, msg: str=None):
        if ok:
            self.num_passed += 1
            stmt = colored('ok', "green")
        else:
            stmt = colored('failed', 'red')
        if isinstance(msg, list):
            msg = '\n'.join(msg)
        if msg is not None:
            stmt += '\n  '+str(msg).replace('\n', '\n  ')
        print(stmt)

    def disp_result(self) -> bool:
        # record the end time
        self.end_time = time.perf_counter()

        all_ok = self.num_passed == self.num_trials
        self.num_failed = self.num_trials - self.num_passed

        # determine how many seconds elapsed from start to finish
        elapsed = self.end_time - self.start_time
        
        stmt = '\ntest result: '
        if all_ok:
            stmt += colored('ok', "green")
        else:
            stmt += colored('failed', 'red')
        stmt += '. '+str(self.num_passed)+' passed; '+str(self.num_failed)+' failed; '+'finished in '+str(round(elapsed, 2))+'s\n'
        print(stmt)
        return all_ok
    
    def verify_tests_exist(self):
        """
        Checks that a valid test is available to run.
        """
        if self.is_isolated() and len(self.modules) == 0:
            log.error('no tests defined')
        elif self.modules[0].is_valid() == False:
            log.error('no tests defined')
