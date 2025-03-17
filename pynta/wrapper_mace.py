from ase.calculators.calculator import Calculator
from ase.io import write, read
from ase.units import Bohr
import os
import json
import subprocess
import shutil
import numpy as np

class wrapperMACE(Calculator):
    implemented_properties = ['energy', 'forces']

    def __init__(self, **kwargs):
        Calculator.__init__(self, **kwargs)
        self.python_bin = '/lus/eagle/projects/catalysis_aesp/raymundohe/maceFlow/mace_env311/bin/python'
        self.mace = '/lus/eagle/projects/catalysis_aesp/raymundohe/maceFlow/AlCalc/01-ASE/02-Clean-Working-example/soloMace.py'

        if 'host' in kwargs:
            self.host = kwargs['host']
        else:
            self.host = 'localhost'

        if 'storage' in kwargs:
            self.storage = kwargs['storage']
        else:
            self.storage = None

        if 'debug' in kwargs:
            self.debug = kwargs['debug']
        else:
            self.debug = False

    def calculate(self, atoms, properties, system_changes):
        Calculator.calculate(self, atoms, properties, system_changes)

        # Create the input
        atoms.write('input.xyz')

        cwd_path = os.getcwd()

        if self.debug:
            print(" Current directory",cwd_path)
            print(" runing in the host : ",self.host)

        with subprocess.Popen(['ssh','-T', self.host],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        universal_newlines=True) as p:
            output, error = p.communicate(f""" cd {cwd_path}
            echo `pwd`
            echo $HOST
            module use /soft/modulefiles
            module load conda
            module load cudatoolkit-standalone/11.8.0
            conda init
            conda activate /lus/eagle/projects/catalysis_aesp/raymundohe/maceFlow/mace_env311
            python {self.mace} 'input.xyz' {cwd_path}
            """)
            print(output)
            print(error)

        with open("input.json", "r") as file:
            data_json = json.load(file)

        self.results['energy'] = data_json['energy']
        self.results['forces'] = np.array(data_json['forces'])

'''        if self.storage is not None:
            if not os.path.exists(self.storage):
                os.makedirs(self.storage)

            src = os.path.join(cwd_path, "input.json");
            dst = os.path.join(self.storage, "input.json");

            if os.path.exists(dst):
                count = 1
                while True:
                    new_name = f"input_{count:03d}.json"
                    new_path = os.path.join(self.storage, new_name)
                    if not os.path.exists(new_path):
                        dst = new_path
                        break
                    count +=1


            shutil.copy(src, dst)
'''
