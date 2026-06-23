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

    # 5. Construct and Execute Command
    # We construct a bash command to source g5_modules first, just like the Perl script did.
    g5_modules_path = os.path.join(linux_path, "g5_modules")
    executable = os.path.join(script_path, script_name)
    
    command_str = f"source {g5_modules_path} && {executable} {' '.join(arguments)}"
    
    try:
        write_to_event_log("EXEC", f"Running command: {command_str}")
        
        # Run using bash to evaluate the "source" command properly
        result = subprocess.run(['/bin/bash', '-c', command_str], 
                                check=True, capture_output=True, text=True)
        
        # Log successful standard output
        for line in result.stdout.splitlines():
            print(f"[STDOUT] {line}")
            
        write_to_event_log("SUCCESS", f"{task_name} on {raw_date} successfully executed.")
        
    except subprocess.CalledProcessError as e:
        error_log_location = os.environ.get('CYLC_TASK_LOG_DIR', 'UNKNOWN_DIR')
        
        write_to_error_log("FAIL", f"{task_name} on {raw_date} FAILED to execute.")
        write_to_error_log("FAIL", f"Exit Code: {e.returncode}")
        write_to_error_log("FAIL", f"Standard Error Output:\n{e.stderr}")
        write_to_error_log("FAIL", f"Standard Out Output:\n{e.stdout}")
        write_to_error_log("FAIL", f"Check full logs for {task_name} on {raw_date} at: {error_log_location}")
        sys.exit(1)

if __name__ == "__main__":
    main()
