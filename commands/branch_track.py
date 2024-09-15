import lldb
import os
import shlex
import optparse
import json
import subprocess
from dataclasses import dataclass, asdict
from typing import Dict, List


FILE_NAME = os.path.basename(__file__)[:-3]
branch_data = []


def __lldb_init_module(debugger: lldb.SBDebugger, internal_dict: dict):
    debugger.HandleCommand(f'command script add -f {FILE_NAME}.set_bps set_bps -h "track branches"')
    debugger.HandleCommand(f'command script add -f {FILE_NAME}.save_branch save_branch -h "save tracked branches"')


def get_all_modules(debugger: lldb.SBDebugger) -> List[dict]:
    target: lldb.SBTarget = debugger.GetSelectedTarget()
    all_modules = []
    for i in range(target.GetNumModules()):
        module: lldb.SBModule = target.GetModuleAtIndex(i)
        addr = hex(module.GetObjectFileHeaderAddress().GetLoadAddress(target))
        name = module.GetFileSpec().GetFilename()
        all_modules.append({"name": name, "addr": addr})
    return all_modules


def save_branch(debugger: lldb.SBDebugger, command: str, exe_ctx: lldb.SBExecutionContext, result: lldb.SBCommandReturnObject, internal_dict: dict):
    global branch_data
    file_name = "/tmp/branch_data.json"
    result = {
        "modules": get_all_modules(debugger),
        "branches": branch_data
    }
    with open(file_name, 'w') as f:
        json.dump(result, f, indent=2)
    print(f"Branch data saved to {file_name}")
    branch_data = []
    print("Saved data is cleared")


def set_bps(debugger: lldb.SBDebugger, command: str, exe_ctx: lldb.SBExecutionContext, result: lldb.SBCommandReturnObject, internal_dict: dict):
    '''
    NOTE: Only Intel Mac, only main module
    '''

    command_args = shlex.split(command, posix=False)
    parser = generate_option_parser()
    try:
        (options, args) = parser.parse_args(command_args)
    except:
        result.SetError(parser.usage)
        return

    target = debugger.GetSelectedTarget()
    main_module: lldb.SBModule = target.GetModuleAtIndex(0)
    image_base = main_module.GetObjectFileHeaderAddress().GetLoadAddress(target)
    branch_instruction_addresses = get_all_branch_instructions(debugger, image_base)

    for address in branch_instruction_addresses.splitlines():
        bp = target.BreakpointCreateByAddress(int(address, 16))
        bp.SetScriptCallbackFunction(f"{FILE_NAME}.break_on_indirect_branch")
    
    print(f"Breakpoints set in main module: {main_module.GetFileSpec().GetFilename()}")
    print(f"Please continue program execution, then save branch data using the \"save_branch\" command")


def generate_option_parser():
    # TODO: implement module option
    usage = "usage: %prog [options] TODO Description Here :]"
    parser = optparse.OptionParser(usage=usage, prog=FILE_NAME)
    parser.add_option("-m", "--module",
                      action="store",
                      default=None,
                      dest="module",
                      help="This is a placeholder option to show you how to use options with strings")
    return parser
    

def get_target_executable(debugger):
    file_spec = debugger.GetSelectedTarget().GetExecutable()
    directory = file_spec.GetDirectory()
    filename = file_spec.GetFilename()
    full_path = os.path.join(directory, filename)
    return full_path


def get_all_branch_instructions(debugger, image_base):
    r2_script_path = "/tmp/disas.r2"
    target_section_names = [
        "__TEXT.__text",
    ]
    with open(r2_script_path, "w") as fout:
        fout.write("e asm.lines = false\n")
        fout.write("aaaa\n")
        fout.write("pD 0 > /tmp/disas.asm\n")
        for target_section_name in target_section_names:
            fout.write(f"s $(iS~{target_section_name}~[3])\n")
            fout.write("pD $SS >> /tmp/disas.asm\n")
    os.system(f"r2 -e bin.relocs.apply=true -i {r2_script_path} -B {hex(image_base)} -q {get_target_executable(debugger)}")
    grep_process = subprocess.Popen(["grep", "-E", "(call|jmp).*(\\[|r\\Sx|e\\Sx)", "/tmp/disas.asm"], stdout=subprocess.PIPE)
    awk_process = subprocess.Popen(["awk", "{print $1}"], stdin=grep_process.stdout, stdout=subprocess.PIPE, text=True)
    branch_instruction_addresses = awk_process.communicate()[0]
    return branch_instruction_addresses


@dataclass
class BranchData:
    module: str
    func: str
    registers: Dict[str, str]


class CollectIndirectBranchInfo:
    def __init__(self, thread_plan, dict):
        self.thread_plan = thread_plan
        self.thread = self.thread_plan.GetThread()
        self.branch_data_before = self.get_branch_data()
        self.branch_data_after = None

    def get_branch_data(self) -> BranchData:
        return BranchData(module=self.get_current_module(), func=self.get_current_func(), registers=self.get_register_values())

    def get_current_func(self):
        return self.thread.GetFrameAtIndex(0).GetFunctionName()

    def get_current_module(self):
        return self.thread.GetFrameAtIndex(0).GetModule().GetFileSpec().GetFilename()

    def get_register_values(self):
        frame = self.thread.GetFrameAtIndex(0)
        registers = frame.GetRegisters()
        general_purpose_registers = registers.GetFirstValueByName("General Purpose Registers")
        
        register_values = {}
        for register in general_purpose_registers:
            if register.GetByteSize() == 8:
                register_values[register.GetName()] = register.GetValue()
        return register_values

    def save(self):
        global branch_data
        branch_data.append({
            "before": asdict(self.branch_data_before),
            "after": asdict(self.branch_data_after)
        })

    def is_stale(self):
        return False

    def explains_stop(self, event):
        if self.thread_plan.GetThread().GetStopReason() == lldb.eStopReasonTrace:
            return True
        else:
            return False

    def should_stop(self, event):
        self.branch_data_after = self.get_branch_data()
        self.save()
        self.thread_plan.SetPlanComplete(True)
        return False

    def should_step(self):
        return True

    def stop_description(self, stream):
        stream.Print("CollectIndirectBranch completed")


def break_on_indirect_branch(frame: lldb.SBFrame, bp_loc: lldb.SBAddress, dict: dict):
    thread = frame.GetThread()
    process = thread.GetProcess()
    process.GetTarget().GetDebugger().SetAsync(False)
    thread.StepUsingScriptedThreadPlan(f"{FILE_NAME}.CollectIndirectBranchInfo", False)
    return False
