import lldb
import os
import shlex
import optparse
import json


FILE_NAME = os.path.basename(__file__)[:-3]
type_metadata_info = list()


def is_numeric_string(s: str):
    try:
        int(s)
        return True
    except ValueError:
        return False


def evaluate_type_metadata(debugger: lldb.SBDebugger, thread: lldb.SBThread):
    interpreter = debugger.GetCommandInterpreter()
    return_address = thread.GetFrameAtIndex(1).GetPC()

    res = lldb.SBCommandReturnObject()
    expression = f'expression -lobjc -O -- $arg1'
    interpreter.HandleCommand(expression, res)
    if res.HasResult():
        type_metadata = res.GetOutput().replace('\n', '')
        if not is_numeric_string(type_metadata):
            return return_address, type_metadata
    else:
        return None, None


def break_on_swift_allocObject(frame: lldb.SBFrame, bp_loc: lldb.SBAddress, dict: dict):
    return_address, output = evaluate_type_metadata(frame.GetThread().GetProcess().GetTarget().GetDebugger(), frame.GetThread())
    type_metadata_info.append((return_address, output))
    return False


def break_on_swift_initStackObject(frame: lldb.SBFrame, bp_loc: lldb.SBAddress, dict: dict):
    return_address, output = evaluate_type_metadata(frame.GetThread().GetProcess().GetTarget().GetDebugger(), frame.GetThread())
    type_metadata_info.append((return_address, output))
    return False


def __lldb_init_module(debugger: lldb.SBDebugger, internal_dict: dict):
    debugger.HandleCommand(f'command script add -f {FILE_NAME}.set_bps dyn_types_trace -h "Set breakpoints on swift_allocObject and swift_initStackObject"')
    debugger.HandleCommand(f'command script add -f {FILE_NAME}.save_trace_data save_trace_data -h "Save the collected trace data to a file"')


def save_trace_data(debugger: lldb.SBDebugger, command: str, exe_ctx: lldb.SBExecutionContext, result: lldb.SBCommandReturnObject, internal_dict: dict):
    with open("/tmp/type_metadata_trace.json", "w") as f:
        json.dump(type_metadata_info, f)


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
    # bp = target.BreakpointCreateByName("swift_allocObject")
    # bp.SetScriptCallbackFunction(f"{FILE_NAME}.break_on_swift_allocObject")
    bp = target.BreakpointCreateByName("swift_initStackObject")
    bp.SetScriptCallbackFunction(f"{FILE_NAME}.break_on_swift_initStackObject")
    print("Breakpoints are set. Please continue execution.")


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
    