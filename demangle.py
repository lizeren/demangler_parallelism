import subprocess
import re

def demangle_with_cxxfilt(mangled_symbol):
    """
    Invoke c++filt from the command line to demangle a C++ symbol.

    Args:
        mangled_symbol (str): The mangled C++ symbol.

    Returns:
        str: The demangled symbol (with surrounding whitespace removed),
             or None if the command fails.
    """
    try:
        result = subprocess.run(
            ['c++filt', '-p', mangled_symbol],
            capture_output=True,  # capture stdout and stderr
            text=True,            # return output as string
            check=True            # raise CalledProcessError on error
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error: c++filt returned non-zero exit code: {e.returncode}")
    except FileNotFoundError:
        print("Error: c++filt command not found. Is it installed and in your PATH?")
    return None

def get_bare_function_name(mangled_symbol):
    """
    Demangle the symbol using c++filt and post-process the output to extract 
    the bare function name, matching the logic in demangle_json.sh.

    Processing steps:
    1. Get part after the last :: (removes namespaces)
    2. Remove parameter list (anything between parentheses)
    3. Remove template parameters (anything between angle brackets)
    4. Remove ABI tags like [abi:cxx11]

    Args:
        mangled_symbol (str): The mangled C++ symbol.

    Returns:
        str: The bare function name, or the original symbol if demangling failed.
    """
    demangled = demangle_with_cxxfilt(mangled_symbol)
    if demangled is None:
        demangled = mangled_symbol


    # Process the demangled name to extract the bare function name
    # Following the same logic as in demangle_json.sh
    
    # Step 1: Get part after the last :: (removes namespaces)
    # This regex finds the last instance of :: followed by any character sequence up to (
    # If found, it extracts what's between :: and (, otherwise it keeps the whole string
    match = re.search(r'.*::([^(]+)', demangled)
    if match:
        bare_name = match.group(1)
    else:
        bare_name = demangled
    
    # Step 2: Remove parameter list (anything between parentheses)
    bare_name = re.sub(r'\(.*\)', '', bare_name)
    
    # Step 3: Remove template parameters (anything between angle brackets)
    bare_name = re.sub(r'<[^>]*>', '', bare_name)
    
    # Step 4: Remove ABI tags like [abi:cxx11]
    bare_name = re.sub(r'\[.*\]', '', bare_name)
    
    # Clean up any extra whitespace
    bare_name = bare_name.strip()
    
    # If we ended up with an empty string, use the original demangled name
    if not bare_name:
        return demangled, demangled
        
    return demangled, bare_name

if __name__ == "__main__":
    # List of sample mangled symbols.
    mangled_symbols = [
        "_Z8multiplyIdET_S0_S0_",
        "_ZN9StaticLib7isPrimeEi",            # Expected demangled: StaticLib::isPrime(int) -> bare: isPrime
        "_Z15calculateSquarei",               # Expected demangled: calculateSquare(int) -> bare: calculateSquare
        "_Z1fv",                              # Expected demangled: f() -> bare: f
        "_ZNSt16allocator_traitsISaINSt7__cxx1112basic_stringIcSt11char_traitsIcESaIcEEEEE9constructIS5_JS5_EEEvRS6_PT_DpOT0_",
        "_ZStlsISt11char_traitsIcEERSt13basic_ostreamIcT_ES5_PKc@GLIBCXX_3.4",
        "_ZNSt8functionIFvRK6ClassCEEaSIZ12analyzeTypesvE3$_0EENSt9enable_ifIXsrNS4_9_CallableIT_NS7_IXntsr7is_sameINSt9remove_cvINSt16remove_referenceIS9_E4typeEE4typeES4_EE5valueESt5decayIS9_EE4type4typeESt15__invoke_resultIRSK_JS2_EEEE5valueERS4_E4typeEOS9_",
        "_ZNSt16allocator_traitsISaIvEE9constructI6ClassBJEEEvRS0_PT_DpOT0_",
        "__cxa_pure_virtual@CXXABI_1.3",
        "_Z11processNodeB5cxx1111Node_cyclic", # Tests ABI tag removal
    ]
    
    for sym in mangled_symbols:
        demangled, bare_name = get_bare_function_name(sym)
        if demangled:
            print(f"\n===============\nMangled: {sym}\n\nDemangled: {demangled}\nBare name: {bare_name}\n===============\n")