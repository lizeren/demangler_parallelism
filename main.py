#!/usr/bin/env python3
"""
Script to process JSON mapping files by demangling function names
with advanced parallel processing.
"""

import json
import os
import sys
import time
import multiprocessing
import concurrent.futures
from tqdm import tqdm
from demangle import demangle_with_cxxfilt, get_bare_function_name

# Determine optimal number of workers based on CPU cores
NUM_PROCESSES = max(1, multiprocessing.cpu_count() - 1)  # Leave one core free for system
NUM_THREADS_PER_PROCESS = 4  # Adjust based on your workload characteristics

def process_entry(function_name):
    """Process a single function name entry."""
    if not function_name:
        return None, None
        
    # Get demangled name
    demangled_name = demangle_with_cxxfilt(function_name)
    if demangled_name is None:
        demangled_name = function_name
    
    # Get bare name
    bare_name = get_bare_function_name(function_name)
    
    return demangled_name, bare_name

def process_batch(batch):
    """Process a batch of entries in parallel."""
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_THREADS_PER_PROCESS) as executor:
        future_to_key = {}
        for key, function_name in batch:
            future = executor.submit(process_entry, function_name)
            future_to_key[future] = key
        
        for future in concurrent.futures.as_completed(future_to_key):
            key = future_to_key[future]
            try:
                results[key] = future.result()
            except Exception as e:
                print(f"Error processing entry {key}: {e}")
                results[key] = (None, None)
    
    return results

def count_processable_entries(filename):
    """
    Count the number of entries in a JSON file that need processing.
    
    Args:
        filename (str): Path to the JSON file
        
    Returns:
        tuple: (total_entries, count_to_process) - Total entries and count of entries to process
    """
    try:
        if not os.path.exists(filename):
            return 0, 0
            
        with open(filename, 'r') as f:
            mapping = json.load(f)
        
        total_entries = len(mapping)
        count_to_process = sum(1 for entry in mapping.values() 
                              if "function_name" in entry and entry["function_name"])
        
        return total_entries, count_to_process
    except Exception as e:
        print(f"Error counting entries in {filename}: {e}")
        return 0, 0

def process_mapping_file(input_filename, output_filename):
    """
    Process a JSON mapping file by demangling function names and writing to a new file.
    
    Args:
        input_filename (str): Path to the input JSON mapping file
        output_filename (str): Path to the output JSON file
        
    Returns:
        tuple: (bool, int) - Success status and number of entries processed
    """
    try:
        # Check if input file exists
        if not os.path.exists(input_filename):
            print(f"Error: Input file {input_filename} not found")
            return False, 0
            
        # Read the JSON file
        with open(input_filename, 'r') as f:
            mapping = json.load(f)
        
        # Prepare entries for processing
        entries_to_process = []
        for key, entry in mapping.items():
            if "function_name" in entry and entry["function_name"]:
                entries_to_process.append((key, entry["function_name"]))
        
        total_entries = len(entries_to_process)
        if total_entries == 0:
            print(f"No entries to process in {input_filename}")
            return True, 0
            
        # Determine optimal batch size
        batch_size = max(10, total_entries // (NUM_PROCESSES * 4))  # Ensure enough batches for parallelism
        batches = [entries_to_process[i:i + batch_size] for i in range(0, len(entries_to_process), batch_size)]
        
        # Process batches in parallel using process pool
        results = {}
        with tqdm(total=total_entries, desc=f"Processing {input_filename}", unit="entries") as pbar:
            with concurrent.futures.ProcessPoolExecutor(max_workers=NUM_PROCESSES) as executor:
                future_to_batch_size = {}
                for batch in batches:
                    future = executor.submit(process_batch, batch)
                    future_to_batch_size[future] = len(batch)
                
                # Collect results as they complete
                for future in concurrent.futures.as_completed(future_to_batch_size):
                    batch_size = future_to_batch_size[future]
                    try:
                        batch_results = future.result()
                        results.update(batch_results)
                        pbar.update(batch_size)
                    except Exception as e:
                        print(f"Error processing batch: {e}")
                        pbar.update(batch_size)  # Update progress even on error
        
        # Update the mapping with results
        entries_processed = 0
        for key, entry in mapping.items():
            if key in results and results[key][0] is not None:
                demangled_name, bare_name = results[key]
                entry["demangled_name"] = demangled_name
                entry["bare_name"] = bare_name
                entries_processed += 1
        
        # Write the processed JSON to the output file
        with open(output_filename, 'w') as f:
            json.dump(mapping, f, indent=4)
            
        return True, entries_processed
        
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON in {input_filename}: {e}")
        return False, 0
    except Exception as e:
        print(f"Error processing {input_filename}: {e}")
        return False, 0

def main():
    # Start timer
    start_time = time.time()
    
    # Define the files to process with their corresponding output files
    mapping_files = [
        # ("dec_mapping_copy_yosys.json", "elf.json"),
        # ("elf_mapping_copy_yosys.json", "dec.json")
        ("dec_mapping_copy_test.json", "elf.json"),
        ("elf_mapping_copy_test.json", "dec.json")
    ]
    
    # Count entries before processing
    print("Counting entries in input files...")
    file_entry_counts = {}
    total_to_process = 0
    
    for input_file, _ in mapping_files:
        total_entries, to_process = count_processable_entries(input_file)
        file_entry_counts[input_file] = (total_entries, to_process)
        total_to_process += to_process
        
        print(f"  {input_file}: {to_process} entries to process out of {total_entries} total entries")
    
    print(f"Total: {total_to_process} entries to process across all files")
    print("\nStarting parallel processing...")
    
    # Process all files in parallel
    total_entries_processed = 0
    results = []
    
    with concurrent.futures.ProcessPoolExecutor(max_workers=len(mapping_files)) as executor:
        # Submit all files for processing
        futures = [
            executor.submit(process_mapping_file, input_file, output_file)
            for input_file, output_file in mapping_files
        ]
        
        # Store the results
        for future, (input_file, output_file) in zip(futures, mapping_files):
            try:
                results.append((input_file, output_file, future.result()))
            except Exception as e:
                print(f"Fatal error processing {input_file}: {e}")
                results.append((input_file, output_file, (False, 0)))
    
    # Process results
    success_count = 0
    for input_file, output_file, (success, entries_processed) in results:
        if success:
            success_count += 1
            total_entries_processed += entries_processed
            expected = file_entry_counts[input_file][1]
            print(f"✓ Completed {input_file} -> {output_file}: {entries_processed}/{expected} entries processed")
        else:
            print(f"✗ Failed processing {input_file} -> {output_file}")
    
    # Calculate total time
    elapsed_time = time.time() - start_time
    minutes, seconds = divmod(elapsed_time, 60)
    
    print(f"\nSystem information:")
    print(f"  - CPU cores: {multiprocessing.cpu_count()}")
    print(f"  - Processes used: {NUM_PROCESSES}")
    print(f"  - Threads per process: {NUM_THREADS_PER_PROCESS}")
    
    print(f"\nCompleted: {success_count}/{len(mapping_files)} files successfully processed.")
    print(f"Total entries processed: {total_entries_processed}/{total_to_process}")
    print(f"Total time: {int(minutes)} minutes and {seconds:.2f} seconds")
    
    if total_entries_processed > 0:
        print(f"Average time per entry: {(elapsed_time / total_entries_processed):.4f} seconds")
    
    return 0 if success_count == len(mapping_files) else 1

if __name__ == "__main__":
    # Ensure proper process spawning on Windows
    multiprocessing.freeze_support()
    sys.exit(main()) 