import locale
import subprocess
import os
import pathlib
import glob
import logging
import pickle
import math

from model.project import Project
from config import config
from model.defs import *
from observer import observer

logger = logging.getLogger("Helper")

SHC_VERIFY_SLEEP = 0.2


def clean_tmp_files():
    files_to_clean = [
        # compile artefacts in current working dir
        "main-clean.obj",
        "main.obj",
        "mllink$.lnk",
    ]
    for file in files_to_clean:
        pathlib.Path(file).unlink(missing_ok=True)


def clean_files(settings):
    files_to_clean = [
        # temporary files
        settings.project_c_path,
        settings.project_asm_path,
        settings.project_shc_path,
        settings.project_exe_path,
    ]
    for file in files_to_clean:
        pathlib.Path(file).unlink(missing_ok=True)


def run_exe(exefile, dllfunc="", check=True):
    logger.info("-[ Start infected file: {}".format(exefile))

    if exefile.endswith(".dll"):
        if dllfunc == "":
            dllfunc = "dllMain"
            logger.info("      No DLL function specified, using default: {}".format(dllfunc))
            #raise Exception("      No DLL function specified")
        args = [ "rundll32.exe", "{},{}".format(exefile, dllfunc) ]
    elif exefile.endswith(".exe"):
        args = [ exefile ]
    else:
        raise Exception("Unknown file type: {}".format(exefile))

    run_process_checkret(args, check=check)


def run_process_checkret(args, check=True):
    logger.info("    > Run process: {}".format(" ".join(args)))

    ret = subprocess.CompletedProcess("", 666)
    try:
        ret = subprocess.run(args, capture_output=True)
    except KeyboardInterrupt:
        logger.warning("Caught KeyboardInterrupt, exiting gracefully...")
    except subprocess.CalledProcessError as e:
        logger.warning(f"Command '{e.cmd}' returned non-zero exit status {e.returncode}.")
    except Exception as e:
        logger.warning(f"An error occurred executing {e}")
    
    # handle output with proper Windows encoding
    # Use the preferred encoding for console output on Windows
    encoding = locale.getpreferredencoding(False) or 'cp1252'

    # handle output
    stdout_s = ""
    if ret.stdout != None:
        stdout_s = ret.stdout.decode(encoding, errors='replace')
    stderr_s = ""
    if ret.stderr != None:
        stderr_s = ret.stderr.decode(encoding, errors='replace')

    # log it
    observer.add_cmd_output(">>> {}\n".format(" ".join(args)))
    for line in stdout_s.split("\n"):
        observer.add_cmd_output(line)
    for line in stderr_s.split("\n"):
        observer.add_cmd_output(line)

    # check return code (optional)
    if ret.returncode != 0 and check:
        logger.error("----! FAILED Command: {}".format(" ".join(args)))
        logger.warning("----! Stdout:\n {}".format(stdout_s))
        logger.warning("----! Stderr:\n {}".format(stderr_s))
        raise ChildProcessError("Command failed: " + " ".join(args))
    
    # debug: show command output
    if config.ShowCommandOutput:
        logger.info(">>> " + " ".join(args))
        logger.info(stdout_s)
        logger.info(stderr_s)


def try_start_shellcode(shc_file):
    logger.info("    Blindly execute shellcode: {}".format(shc_file))
    subprocess.run([
        config.get("path_runshc"),
        shc_file,
    ])


def file_readall_text(filepath) -> str:
    with open(filepath, "r") as f:
        data = f.read()
    return data


def file_readall_binary(filepath) -> bytes:
    with open(filepath, "rb") as f:
        data = f.read()
    return data


def file_to_lf(filename):
    with open(filename, 'rb') as f:
        data = f.read()
    
    data = data.replace(b'\r\n', b'\n')
    with open(filename, 'wb') as f:
        f.write(data)


def round_up_to_multiple_of_8(x):
    return math.ceil(x / 8) * 8


def ui_string_decode(data):
    res = ""
    try:
        if len(data) > 32:
            res = "Data with len {}".format(len(data))
        elif b"\x00\x00" in data:
            res = "(utf16) " + data.decode("utf-16le")
        else:
            res = "(utf8) " + data.decode("utf-8")
    except Exception as e:
        res = "(bytes) " + data.hex()

    return res


def ascii_to_hex_bytes(ascii_bytes):
    hex_escaped = ''.join(f'\\x{byte:02x}' for byte in ascii_bytes)
    return hex_escaped
