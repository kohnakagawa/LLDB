import lldb
import os
import optparse


def __lldb_init_module(debugger: lldb.SBDebugger, internal_dict: dict):
    debugger.HandleCommand(
    'command script add -o -f swbt.handle_command swbt -h "Resymbolicate stripped Swift backtrace"')


def handle_command(debugger: lldb.SBDebugger, command: str, exe_ctx: lldb.SBExecutionContext, result: lldb.SBCommandReturnObject, internal_dict: dict):
    '''
    Symbolicate Swift backtrace from a stripped binary.
    '''

    command_args = command.split()
    parser = generate_option_parser()
    try:
        (options, args) = parser.parse_args(command_args)
    except:
        result.SetError(parser.usage)
        return

    target: lldb.SBTarget = exe_ctx.target
    thread: lldb.SBThread = exe_ctx.thread
    if thread is None:
        result.SetError("LLDB must be paused to execute this command")
        return

    if options.address:
        frameAddresses = [int(options.address, 16)]
    else:
        frameAddresses = [f.addr.GetLoadAddress(target) for f in thread.frames]

    print(frameAddresses)
    result.AppendMessage(process_stack_trace_string_from_addr(frameAddresses, target))


def process_stack_trace_string_from_addr(frame_addrs: list[int], target: lldb.SBTarget) -> str:
    start_addrs = [target.ResolveLoadAddress(f).symbol.addr.GetLoadAddress(target) for f in frame_addrs]

    # start_addrs を含むモジュールの一覧を取得
    # モジュールの一覧について Swift のメタデータを取得
    # メタデータの値をキャッシュ
    # 関数のアドレスをキーとし、値を class 名と method 名にする辞書を作成

    return ""


def generate_option_parser():
    usage = "usage: %prog [options] path/to/item"
    parser = optparse.OptionParser(usage=usage, prog="swbt")
    parser.add_option("-a", "--address",
                      action="store",
                      default=None,
                      dest="address",
                      help="Only try to resymbolicate this address")
    return parser


