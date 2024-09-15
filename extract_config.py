import os
import sys
import subprocess


def get_target_executable(debugger):
    file_spec = debugger.GetSelectedTarget().GetExecutable()
    directory = file_spec.GetDirectory()
    filename = file_spec.GetFilename()
    full_path = os.path.join(directory, filename)
    return full_path


def get_bss_segment_info(debugger):
    output = subprocess.run(["/usr/bin/size", "-arch", "x86_64", "-ml", get_target_executable(debugger)], capture_output=True, text=True).stdout
    print(output)
    for l in output.split("\n"):
        if "__bss" in l:
            bss_size = int(l.strip().split(":")[-1].split(" ")[1])
            bss_addr = int(l.strip().split(":")[-1].split(" ")[3], 16)
            return bss_size, bss_addr
    return None, None


def extract(debugger, command, result, internal_dict):
    bss_size, bss_addr = get_bss_segment_info(debugger)
    filename = "/tmp/bss_segment_dump.bin"
    debugger.HandleCommand(f"memory read --force --binary -c {hex(bss_size)} {hex(bss_addr)} --outfile {filename}")
    debugger.HandleCommand("c")
    os.system(f"strings {filename} > /tmp/config.txt")


def __lldb_init_module(debugger, internal_dict):
    target = debugger.GetSelectedTarget()
    print(target.GetExecutable())
    debugger.HandleCommand("setting set target.max-string-summary-length 10000")
    debugger.HandleCommand("command script add -f extract_config.extract cmd_extract_config")
    debugger.HandleCommand("breakpoint set -n exit -C \"cmd_extract_config\"")
