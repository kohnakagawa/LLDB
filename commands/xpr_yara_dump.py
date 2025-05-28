import lldb
import os
import sys
import subprocess
from typing import Optional


FILE_NAME = os.path.basename(__file__)[:-3]
OUTPUT_FD = None


def __lldb_init_module(debugger: lldb.SBDebugger, internal_dict: dict):
    debugger.HandleCommand(
    f'command script add -f {FILE_NAME}.handle_command xpr_yara_dump -h "Dump yara rule strings of XProtectRemediator"')


def get_YaraMatcher_init_addr(target_path: str, image_base: int) -> Optional[int]:
    r2_script_path = "/tmp/get_YaraMatcher_init.r2"
    with open(r2_script_path, "w") as fout:
        fout.write("aa\n")
        fout.write("s $(axt sym.imp.yr_compiler_create~[0])\n")
        fout.write("s")
    
    r2_process = subprocess.Popen(["r2", "-e", "bin.relocs.apply=true", "-i", r2_script_path, "-B", hex(image_base) , "-q", target_path], 
                                  stdout=subprocess.PIPE, 
                                  stderr=subprocess.PIPE, 
                                  text=True)
    output, _ = r2_process.communicate()
    addr = None
    try:
        addr = int(output.strip(), 16)
    except Exception as e:
        print("Cannot get YaraMatcher.init", file=sys.stderr)
        print(f"Are you really debugging XProtectRemediator? (executable is {target_path})", file=sys.stderr)
    return addr


def break_on_YaraMatcher_init(frame: lldb.SBFrame, bp_loc: lldb.SBAddress, dict: dict):
    thread = frame.GetThread()
    process = thread.GetProcess()
    process.GetTarget().GetDebugger().SetAsync(False)
    r13_value = frame.FindRegister("r13").GetValueAsUnsigned()
    print(f"Yara Matcher @ 0x{r13_value:016x}", file=OUTPUT_FD)
    OUTPUT_FD.flush()
    return False


def break_on_yr_compiler_add_string(frame: lldb.SBFrame, bp_loc: lldb.SBAddress, dict: dict):
    string_ptr = frame.FindRegister("rsi").GetValueAsUnsigned()
    error = lldb.SBError()
    yara_rule_string = frame.GetThread().GetProcess().ReadCStringFromMemory(string_ptr, 0xffffffff, error)

    if error.Success():
        print(f"YARA rule:\n{yara_rule_string}", file=OUTPUT_FD)
        OUTPUT_FD.flush()
    else:
        print(f"Error reading YARA rule string: {error.GetCString()}", file=sys.stderr)
    return False


def get_target_executable(debugger):
    file_spec = debugger.GetSelectedTarget().GetExecutable()
    directory = file_spec.GetDirectory()
    filename = file_spec.GetFilename()
    full_path = os.path.join(directory, filename)
    return full_path


def handle_command(debugger: lldb.SBDebugger, command: str, exe_ctx: lldb.SBExecutionContext, result: lldb.SBCommandReturnObject, internal_dict: dict):
    '''
    Dump yara rule strings of XProtectRemediator
    '''
    target_executable = get_target_executable(debugger)
    module_name = os.path.basename(target_executable)
    output_file = f"/tmp/{module_name}_yara_dump.txt"
    global OUTPUT_FD
    OUTPUT_FD = open(output_file, "w")

    target: lldb.SBTarget = debugger.GetSelectedTarget()
    main_module: lldb.SBModule = target.GetModuleAtIndex(0)
    image_base = main_module.GetObjectFileHeaderAddress().GetLoadAddress(target)
    YaraMatcher_init_addr = get_YaraMatcher_init_addr(target_executable, image_base)
    if YaraMatcher_init_addr is None:
        return

    target.BreakpointCreateByAddress(YaraMatcher_init_addr).SetScriptCallbackFunction(f"{FILE_NAME}.break_on_YaraMatcher_init")
    target.BreakpointCreateByName("yr_compiler_add_string").SetScriptCallbackFunction(f"{FILE_NAME}.break_on_yr_compiler_add_string")
    print("Callback functions are set. Please continue the execution.")
    print(f"Dumped result will be saved to {output_file}")