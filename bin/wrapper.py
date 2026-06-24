#!/usr/bin/env python3
import sys
import os
import yaml
import subprocess
from datetime import datetime

def write_to_event_log(code, message):
    print(f"[EVENT - {code}] {message}")

def write_to_error_log(code, message):
    print(f"[ERROR - {code}] {message}", file=sys.stderr)

def main():
    # 1. Accept initial args (matching the Cylc pre-script call)
    # Expected Cylc format: YYYYMMDD (or YYYYMMDDHH)
    raw_date = sys.argv[1].replace("T", "").replace("Z", "") 
    task_name = sys.argv[2]
    config_path = sys.argv[3]
    
    # Extract year and month for dynamic paths
    yyyy = raw_date[0:4]
    mm = raw_date[4:6]
    
    # 2. Access config file
    with open(config_path, 'r') as file:
        config = yaml.safe_load(file)
        
    task_config = config['tasks'][task_name]
    script_path = task_config['script_path']
    script_name = task_config['script_name']
    raw_arguments = task_config['args_to_pass']
    
    # Environment configs
    linux_path = config['environment']['linux']['path']
    
    write_to_event_log("INIT", f"Configs loaded for {task_name} on {raw_date}")

    # 3. Handle Pre-Run Directory Creation (Replaces Perl's token_resolve & mkdir hack)
    if 'pre_run_mkdir' in task_config:
        dir_to_make = task_config['pre_run_mkdir'].format(YYYY=yyyy, MM=mm)
        try:
            os.makedirs(dir_to_make, exist_ok=True)
            write_to_event_log("ENV", f"Created output directory: {dir_to_make}")
        except OSError as e:
            write_to_error_log("ENV", f"Failed to create directory {dir_to_make}: {e}")
            sys.exit(1)

    # 4. Process Arguments (Substitute {DATE}, {YYYY}, {MM})
    arguments = []
    for arg in raw_arguments:
        formatted_arg = arg.format(DATE=raw_date[0:8], YYYY=yyyy, MM=mm)
        arguments.append(formatted_arg)

    # 5. Construct and Execute Command via a discrete script
    g5_modules_path = os.path.join(linux_path, "g5_modules")
    geos_lib_path = linux_path.replace('bin_ops', 'lib')
    
    # We write a physical script to disk to guarantee a pure csh environment
    runner_script = f"run_{task_name}.csh"
    
    with open(runner_script, "w") as f:
        f.write("#!/bin/csh -f\n")
        f.write("unlimit\n")
        f.write("setenv OMP_NUM_THREADS 1\n")   # <--- Add this! Forces 1 thread to prevent array bounds crashes
        f.write("setenv OMP_STACKSIZE 2048m\n")
        f.write("source /usr/share/modules/init/csh\n")
        f.write("module purge\n")
        f.write(f"source {g5_modules_path}\n")
        f.write(f"setenv LD_LIBRARY_PATH {geos_lib_path}:${{BASEDIR}}/Linux/lib:${{LD_LIBRARY_PATH}}\n")
        f.write(f"cd {script_path}\n")
        f.write(f"./{script_name} {' '.join(arguments)}\n") 


    # Make the script executable
    os.chmod(runner_script, 0o755)

    try:
        write_to_event_log("EXEC", f"Running discrete script: {runner_script}")
        
        # Execute the physical script we just created
        result = subprocess.run([f"./{runner_script}"], check=True)
        
        write_to_event_log("SUCCESS", f"{task_name} on {raw_date} successfully executed.")
        
    except subprocess.CalledProcessError as e:
        error_log_location = os.environ.get('CYLC_TASK_LOG_DIR', 'UNKNOWN_DIR')
        write_to_error_log("FAIL", f"{task_name} FAILED. Exit Code: {e.returncode}")
        write_to_error_log("FAIL", f"Check logs at: {error_log_location}")
        sys.exit(1)
if __name__ == "__main__":
    main()
