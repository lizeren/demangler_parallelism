#!/usr/bin/env python3
"""
Script to process JSON mapping files by demangling function names.
"""

import json
import os
import sys
import time
from tqdm import tqdm
from demangle import demangle_with_cxxfilt, get_bare_function_name

def process_mapping_file(input_filename, output_filename):
    """
    Process a JSON mapping file by demangling function names and writing to a new file.
    
    Args:
        input_filename (str): Path to the input JSON mapping file
        output_filename (str): Path to the output JSON file
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Check if input file exists
        if not os.path.exists(input_filename):
            print(f"Error: Input file {input_filename} not found")
            return False
            
        # Read the JSON file
        with open(input_filename, 'r') as f:
            mapping = json.load(f)
            
        # Process each entry with progress bar
        entries_processed = 0
        total_entries = sum(1 for entry in mapping.values() if "function_name" in entry and entry["function_name"])
        
        with tqdm(total=total_entries, desc=f"Processing {input_filename}", unit="entries") as pbar:
            for key, entry in mapping.items():
                if "function_name" in entry:
                    function_name = entry["function_name"]
                    # Only process if function_name is not empty
                    if function_name:
                        # Get demangled name
                        demangled_name = demangle_with_cxxfilt(function_name)
                        if demangled_name is None:
                            demangled_name = function_name
                        
                        # Get bare name
                        bare_name = get_bare_function_name(function_name)
                        
                        # Update the entry
                        entry["demangled_name"] = demangled_name
                        entry["bare_name"] = bare_name
                        entries_processed += 1
                        pbar.update(1)
        
        # Write the processed JSON to the output file
        with open(output_filename, 'w') as f:
            json.dump(mapping, f, indent=4)
            
        print(f"Processed {entries_processed} entries from {input_filename}")
        print(f"Output written to {output_filename}")
        return True
        
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON in {input_filename}: {e}")
        return False
    except Exception as e:
        print(f"Error processing {input_filename}: {e}")
        return False

def main():
    # Start timer
    start_time = time.time()
    
    # Define the files to process with their corresponding output files
    mapping_files = [
        ("elf_mapping.json", "elf.json"),
        ("dec_mapping.json", "dec.json")
    ]
    
    success_count = 0
    for input_file, output_file in mapping_files:
        print(f"Processing {input_file} -> {output_file}...")
        if process_mapping_file(input_file, output_file):
            success_count += 1
    
    # Calculate total time
    elapsed_time = time.time() - start_time
    minutes, seconds = divmod(elapsed_time, 60)
    
    print(f"\nCompleted: {success_count}/{len(mapping_files)} files successfully processed.")
    print(f"Total time: {int(minutes)} minutes and {seconds:.2f} seconds")
    
    return 0 if success_count == len(mapping_files) else 1

if __name__ == "__main__":
    sys.exit(main()) 