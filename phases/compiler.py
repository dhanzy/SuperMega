import os
import pprint
import logging
import shutil
import subprocess
from typing import List, Dict

from helper import *
from config import config
from observer import observer
from model import *
from phases.masmshc import masm_shc, Params
from model.injectable import Injectable
from phases.asmtextparser import parse_asm_text_file
from model.settings import Settings

logger = logging.getLogger("Compiler")


def check_compiler_architecture():
    """Check if the Visual C++ compiler is configured for x64 architecture."""
    try:
        # Run cl.exe without arguments to get version info
        result = subprocess.run(
            [config.get("path_cl")],
            capture_output=True,
            text=True,
            timeout=5
        )
        output = result.stderr  # cl.exe outputs version info to stderr
        
        # Check if it's x64 or x86
        if "x64" in output or "AMD64" in output:
            logger.info("    ✓ Compiler architecture: x64 (64-bit)")
            return True
        elif "x86" in output or "80x86" in output:
            logger.error("    ✗ Compiler architecture: x86 (32-bit) - INCORRECT!")
            logger.error("")
            logger.error("=" * 70)
            logger.error("ERROR: You are using a 32-bit compiler, but this tool requires 64-bit!")
            logger.error("=" * 70)
            logger.error("")
            logger.error("To fix this, you need to start the x64 Developer Command Prompt:")
            logger.error("")
            logger.error("Option 1 - Use the Start Menu:")
            logger.error("  1. Open Start Menu")
            logger.error("  2. Search for 'x64 Native Tools Command Prompt'")
            logger.error("  3. Run it and then execute your script from there")
            logger.error("")
            logger.error("Option 2 - Run vcvarsall.bat in your current terminal:")
            logger.error('  "C:\\Program Files\\Microsoft Visual Studio\\2022\\Community\\VC\\Auxiliary\\Build\\vcvarsall.bat" x64')
            logger.error("")
            logger.error("Option 3 - If using VS 2019 or different installation path:")
            logger.error('  "C:\\Program Files (x86)\\Microsoft Visual Studio\\2019\\Community\\VC\\Auxiliary\\Build\\vcvarsall.bat" x64')
            logger.error("")
            logger.error("After running one of these, try again!")
            logger.error("=" * 70)
            return False
        else:
            logger.warning("    ? Could not determine compiler architecture")
            logger.warning("    Compiler output: {}".format(output[:200]))
            return True  # Don't block if we can't determine
            
    except FileNotFoundError:
        logger.error("    ✗ Compiler (cl.exe) not found at: {}".format(config.get("path_cl")))
        logger.error("    Make sure Visual Studio is installed and Developer Command Prompt is active")
        return False
    except Exception as e:
        logger.warning("    ? Could not check compiler architecture: {}".format(e))
        return True  # Don't block on unexpected errors


# NOTE: Mostly copy-pasted from compiler.py::compile()
def compile_dev(
    c_in: FilePath, 
    asm_out: FilePath,
    short_call_patching: bool = False,
):
    logger.info("-( Carrier: Compile C to ASM: {} -> {} ".format(c_in, asm_out))

    # Compile C To Assembly (text)
    run_process_checkret([
            config.get("path_cl"),
            "/c",
            "/FA",
            "/GS-",
            "/favor:AMD64",
            "/Fa{}/".format(os.path.dirname(c_in)),
            c_in,
    ])
    if not os.path.isfile(asm_out):
        raise Exception("Error: Compiling failed")
    
    asm_text: str = file_readall_text(asm_out)
    observer.add_text_file("carrier_asm_orig", asm_text)

    logger.info("      ASM masm_shc: {} ".format(asm_out))
    settings = Settings()
    injectable = Injectable("test.exe")  # ???
    asm_text_lines: List[str] = parse_asm_text_file(injectable, asm_text, settings)
    asm_text = masm_shc(asm_text_lines)
    observer.add_text_file("carrier_asm_cleanup", asm_text)

    with open(asm_out, "w") as f:
        f.write(asm_text)


def compile(
    c_in: FilePath, 
    asm_out: FilePath,
    injectable: Injectable,
    settings: Settings,
):
    logger.info("-[ Carrier: Compile C to ASM".format())
    logger.info("    Carrier: {} -> {} ".format(c_in, asm_out))

    # Check if we're using the correct 64-bit compiler
    if not check_compiler_architecture():
        raise RuntimeError("Incorrect compiler architecture detected. Please use x64 Developer Command Prompt.")

    # Compile C To Assembly (text)
    run_process_checkret([
            config.get("path_cl"),
            "/c",
            "/FA",
            "/GS-",
            "/Fa{}/".format(os.path.dirname(c_in)),
            c_in,
    ])
    if not os.path.isfile(asm_out):
        raise Exception("Error: Compiling failed")
    asm_text = file_readall_text(asm_out)
    observer.add_text_file("carrier_asm_orig", asm_text)

    asm_text_lines = parse_asm_text_file(injectable, asm_text, settings) # Fixup assembly file
    asm_text = masm_shc(asm_text_lines) # Cleanup assembly file
    observer.add_text_file("carrier_asm_final", asm_text)

    # write back. Next step would be compiling this file
    with open(asm_out, "w") as f:
        f.write(asm_text)
