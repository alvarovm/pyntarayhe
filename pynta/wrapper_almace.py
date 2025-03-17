from ase.calculators.calculator import Calculator, all_changes
from ase.io import write, read
from ase.units import Bohr
from pynta.utils import name_to_ase_software
import os
import json
import subprocess
import shutil
import numpy as np
import yaml

class wrapperALMACE(Calculator):
    implemented_properties = ['energy', 'forces']
    discard_results_on_any_change = True

    def __init__(self, **kwargs):
        Calculator.__init__(self, **kwargs)
        self.python_bin = '/lus/eagle/projects/catalysis_aesp/raymundohe/maceFlow/mace_env311/bin/python'
        self.almace = '/lus/eagle/projects/catalysis_aesp/raymundohe/pynta/pynta/almace.py'
        self.force_threshold = 0.25
        self.relative = 0.25

        if 'force_threshold' in kwargs:
            self.force_threshold = kwargs['force_threshold']
        if 'rel_force_threshold' in kwargs:
            self.relative = kwargs['rel_force_threshold']

        if 'host' in kwargs:
            self.host = kwargs['host']
            self.conect = True
        else:
            self.host = 'localhost'

        if 'opt_method' in kwargs:
            class_opt_method = kwargs['opt_method']
            parts = str(class_opt_method).split("'")
            self.opt_method = parts[1].split('.')[-1]
        else:
            self.opt_method = None

        if 'sub_software' in kwargs:
            self.sub_software = kwargs['sub_software']
        else:
            self.sub_software = 'Espresso'

        if 'sub_software_kwargs' in kwargs:
            self.sub_software_kwargs = kwargs['sub_software_kwargs']
        else:
            print(" You need a DFT software for ALMACE")

        self.abc = None

        if 'storage' in kwargs:
            self.storage = kwargs['storage']
        else:
            self.storage = None

        if 'debug' in kwargs:
            self.debug = kwargs['debug']
        else:
            self.debug = False




    def writeConfig(self):
        print(" force threshold : ",self.force_threshold)
        print(" force relative  : ",self.relative)
        dataConfig = {
            'origin': '/lus/eagle/projects/catalysis_aesp/raymundohe/testPyntaMultiNode/',
            'args_foundational': 'args-foundational.yaml',
            'device': 'cuda',
            'force_threshold': self.force_threshold,
            'rel_force_threshold': self.relative,
        }

        with open('config.yaml', 'w') as file:
            yaml.dump(dataConfig, file)



    def calculate(self, atoms, properties, system_changes):
        Calculator.calculate(self, atoms, properties, system_changes)

        # Create the input
        cwd_path = os.getcwd()
        atoms.write(os.path.join(cwd_path, 'input.xyz'))

        if self.sub_software_kwargs is not None:
            file_yaml = os.path.join(cwd_path,'sub_software.yaml')

            with open(file_yaml, 'w') as file:
                yaml.dump(self.sub_software_kwargs, file)

        print(" Opt Method: ",self.opt_method)

        if self.opt_method == 'MDMin':
            self.Training = False
        else:
            self.Training = True

        if self.debug:
            print(" Current directory",cwd_path)
            print(" runing in the host : ",self.host)

        if self.Training == True:
            if self.conect == True:
                print(" Using ALMACE")

                self.writeConfig()
                import subprocess
                with subprocess.Popen(['ssh','-T', self.host],
                                stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                universal_newlines=True) as p:
                    output, error = p.communicate(f""" cd {cwd_path}
                    echo `pwd`
                    module use /soft/modulefiles
                    module load conda
                    module load PrgEnv-nvhpc nvhpc cudatoolkit-standalone/11.8.0
                    module load cray-hdf5
                    module list
                    conda activate /lus/eagle/projects/catalysis_aesp/raymundohe/maceFlow/mace_env311
                    export MPICH_GPU_SUPPORT_ENABLED=0

                    {self.python_bin} {self.almace} {os.path.join(cwd_path, 'input.xyz')} {cwd_path} {self.storage}  {self.sub_software} sub_software.yaml  config.yaml
                    """)
                    print(output)
                    print(error)
                    print("\033[34m{0}\033[0m".format(os.path.join(cwd_path,"input.json")))

                    try:
                        with open(os.path.join(cwd_path,"input.json"), "r") as file:
                            data_json = json.load(file)
                    except FileNotFoundError:
                        print("The file was not found!")
                    self.results['energy'] = data_json['energy']
                    self.results['forces'] = np.array(data_json['forces'])
                    atoms.info['energy'] = data_json['energy']
                    atoms.arrays['forces'] = np.array(data_json['forces'])


            else:
                import subprocess
                self.writeConfig()
                print("\nBranch else of conect\n")
                command = f'{self.python_bin} {self.almace} input.xyz {cwd_path} {self.storage} {self.sub_software} sub_software.yaml'
                subprocess.run(command, shell=True)
            try:
                with open(os.path.join(cwd_path,"input.json"), "r") as file:
                    data_json = json.load(file)
            except FileNotFoundError:
                print("The file was not found!")
            self.results['energy'] = data_json['energy']
            self.results['forces'] = np.array(data_json['forces'])
            atoms.info['energy'] = data_json['energy']
            atoms.arrays['forces'] = np.array(data_json['forces'])

            print("      In the OUTPUT ",data_json['energy'])

        else:
            print(" Using DFT")
            atoms.calc = name_to_ase_software(self.sub_software)(**self.sub_software_kwargs)
            atoms.info['energy'] =  atoms.get_potential_energy()
            atoms.arrays['forces'] = atoms.get_forces()
            self.results['energy'] = atoms.info['energy']
            self.results['forces'] = atoms.arrays['forces']

            write('almaceDFT000.xyz', atoms)

            if self.storage is not None:
                if not os.path.exists(self.storage):
                    os.makedirs(self.storage)

                src = os.path.join(os.getcwd(), "almaceDFT000.xyz");
                dst = os.path.join(self.storage, "almaceDFT000.xyz");

                if os.path.exists(dst):
                    count = 1
                    while True:
                        new_name = f"almaceDFT{count:03d}.xyz"
                        new_path = os.path.join(self.storage, new_name)
                        if not os.path.exists(new_path):
                            dst = new_path
                            break
                        count +=1
                shutil.copy(src, dst)

        return atoms

