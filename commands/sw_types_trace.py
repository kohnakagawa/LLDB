import lldb
import os
import shlex
import optparse
import json
import sys
from typing import Tuple, Optional


FILE_NAME = os.path.basename(__file__)[:-3]
type_metadata = list()
target_module_addr = tuple()


def is_numeric_string(s: str):
    try:
        int(s)
        return True
    except ValueError:
        return False


def is_in_target_module(addr: int):
    return target_module_addr[0] <= addr < target_module_addr[1]


def evaluate_type_metadata(debugger: lldb.SBDebugger, thread: lldb.SBThread) -> Optional[Tuple[int, int]]:
    interpreter = debugger.GetCommandInterpreter()
    return_address = thread.GetFrameAtIndex(1).GetPC()

    if not is_in_target_module(return_address):
        return None

    res = lldb.SBCommandReturnObject()
    expression = f'expression -lobjc -O -- $arg1'
    interpreter.HandleCommand(expression, res)
    if res.HasResult():
        type_metadata = res.GetOutput().replace('\n', '')
        if type_metadata[-1] == "$":
            type_metadata = type_metadata[:-1]
        if not is_numeric_string(type_metadata):
            return return_address, type_metadata
    return None


def break_on_swift_allocObject(frame: lldb.SBFrame, bp_loc: lldb.SBAddress, dict: dict):
    if (res := evaluate_type_metadata(frame.GetThread().GetProcess().GetTarget().GetDebugger(), frame.GetThread())) is None:
        return False
    type_metadata.append(res)
    return False


def break_on_swift_initStackObject(frame: lldb.SBFrame, bp_loc: lldb.SBAddress, dict: dict):
    if (res := evaluate_type_metadata(frame.GetThread().GetProcess().GetTarget().GetDebugger(), frame.GetThread())) is None:
        return False
    type_metadata.append(res)
    return False


def __lldb_init_module(debugger: lldb.SBDebugger, internal_dict: dict):
    debugger.HandleCommand(f'command script add -f {FILE_NAME}.set_bps swtt_set_bps -h "Set breakpoints on swift_allocObject and swift_initStackObject"')
    debugger.HandleCommand(f'command script add -f {FILE_NAME}.save swtt_save -h "Save the collected trace data to a file"')


def save(debugger: lldb.SBDebugger, command: str, exe_ctx: lldb.SBExecutionContext, result: lldb.SBCommandReturnObject, internal_dict: dict):
    with open("/tmp/type_metadata_trace.json", "w") as f:
        json.dump(type_metadata, f)
    print("Saved to /tmp/type_metadata_trace.json")


def get_text_segment_address_range(module: lldb.SBModule, target: lldb.SBTarget) -> Optional[Tuple[int, int]]:
    for sec in module.sections:
        if sec.GetName() == "__TEXT":
            return (sec.GetFileAddress(), sec.GetFileAddress() + sec.size)
    return None


def set_bps(debugger: lldb.SBDebugger, command: str, exe_ctx: lldb.SBExecutionContext, result: lldb.SBCommandReturnObject, internal_dict: dict):
    '''
    TODO: swift_initStackObject と swift_allocObject の両方にブレークポイントを設定した場合に処理が継続しない問題の調査
    現状では swift_initStackObject のみにブレークポイントを設定するようにしている
    '''

    command_args = shlex.split(command, posix=False)
    parser = generate_option_parser()
    try:
        (options, args) = parser.parse_args(command_args)
    except:
        result.SetError(parser.usage)
        return

    target = debugger.GetSelectedTarget()
    bp = target.BreakpointCreateByName("swift_allocObject")
    bp.SetScriptCallbackFunction(f"{FILE_NAME}.break_on_swift_allocObject")
    bp = target.BreakpointCreateByName("swift_initStackObject")
    bp.SetScriptCallbackFunction(f"{FILE_NAME}.break_on_swift_initStackObject")
    print("Breakpoints are set. Please continue execution.")

    global target_module_addr
    main_module: lldb.SBModule = target.GetModuleAtIndex(0)
    if (main_module_address_range := get_text_segment_address_range(main_module, target)) is None:
        print("Cannot find __TEXT segment?", file=sys.stderr)
    target_module_addr = main_module_address_range


def generate_option_parser():
    # TODO: support module option
    usage = "usage: %prog [options] TODO Description Here :]"
    parser = optparse.OptionParser(usage=usage, prog="get_dyn_types")
    parser.add_option("-m", "--module",
                      action="store",
                      default=None,
                      dest="module",
                      help="This is a placeholder option to show you how to use options with strings")
    return parser
    
