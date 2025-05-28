import lldb
import hashlib
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
    debugger.HandleCommand(f'command script add -f {FILE_NAME}.set_bps brt_set_bps -h "Set breakpoints to record destination addresses of indirect branches"')
    debugger.HandleCommand(f'command script add -f {FILE_NAME}.save brt_save -h "Save trace data to /tmp/branches.json"')


def get_all_modules(debugger: lldb.SBDebugger) -> List[dict]:
    target: lldb.SBTarget = debugger.GetSelectedTarget()
    all_modules = []
    for i in range(target.GetNumModules()):
        module: lldb.SBModule = target.GetModuleAtIndex(i)
        addr = hex(module.GetObjectFileHeaderAddress().GetLoadAddress(target))
        name = module.GetFileSpec().GetFilename()
        all_modules.append({"name": name, "addr": addr})
    return all_modules


def save(debugger: lldb.SBDebugger, command: str, exe_ctx: lldb.SBExecutionContext, result: lldb.SBCommandReturnObject, internal_dict: dict):
    global branch_data
    file_name = "/tmp/branches.json"
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
    NOTE: x86_64 only, only main module is supported
    '''

    target: lldb.SBTarget = debugger.GetSelectedTarget()
    arch = target.GetTriple().split('-')[0]
    if arch != 'x86_64':
        print(f"Warning: This command only supports x86_64 architecture. Current architecture is {arch}")
        return

    command_args = shlex.split(command, posix=False)
    parser = generate_option_parser()
    try:
        (options, args) = parser.parse_args(command_args)
    except:
        result.SetError(parser.usage)
        return

    main_module: lldb.SBModule = target.GetModuleAtIndex(0)
    image_base = main_module.GetObjectFileHeaderAddress().GetLoadAddress(target)
    branch_instruction_addresses = get_all_branch_instructions(debugger, image_base)

    for address in branch_instruction_addresses:
        bp = target.BreakpointCreateByAddress(address)
        bp.SetScriptCallbackFunction(f"{FILE_NAME}.break_on_indirect_branch")
    
    print(f"Breakpoints set in main module: {main_module.GetFileSpec().GetFilename()}")
    print(f"Please continue program execution, then save branch data using the \"brt_save\" command")


def generate_option_parser():
    # TODO: implement module option (not implemented yet)
    usage = "usage: %prog [options]"
    parser = optparse.OptionParser(usage=usage, prog=FILE_NAME)
    parser.add_option("-m", "--module",
                      action="store",
                      default=None,
                      dest="module",
                      help="Module name to set breakpoints")
    return parser
    

def get_target_executable(debugger):
    file_spec = debugger.GetSelectedTarget().GetExecutable()
    directory = file_spec.GetDirectory()
    filename = file_spec.GetFilename()
    full_path = os.path.join(directory, filename)
    return full_path


def disassemble(target_path, image_base, disas_file_name):
    r2_script_path = "/tmp/disas.r2"
    target_section_names = [
        "__TEXT.__text",
    ]
    with open(r2_script_path, "w") as fout:
        fout.write("e asm.lines = false\n")
        fout.write("aaaa\n")
        fout.write(f"pD 0 > {disas_file_name}\n")
        for target_section_name in target_section_names:
            fout.write(f"s $(iS~{target_section_name}~[3])\n")
            fout.write(f"pD $SS >> {disas_file_name}\n")
    os.system(f"r2 -e bin.relocs.apply=true -i {r2_script_path} -B {hex(image_base)} -q {target_path}")


def get_all_branch_instructions(debugger, image_base):
    target_executable = get_target_executable(debugger)
    def calculate_sha256(file_path):
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        sha256_hash.update(image_base.to_bytes(8, byteorder="little"))
        return sha256_hash.hexdigest()
    sha256_value = calculate_sha256(target_executable)

    branch_address_cache = f"/tmp/branches_cache_{sha256_value}.json"
    if os.path.exists(branch_address_cache):
        print(f"Branch address cache ({branch_address_cache}) found. Skipping r2 analysis")
        with open(branch_address_cache, "r") as fin:
            return json.loads(fin.read())
    else:
        print(f"Branch address cache ({branch_address_cache}) not found. Start r2 analysis, but it takes a lot of time.")
        disas_file_name = "/tmp/disas.asm"
        disassemble(target_executable, image_base, disas_file_name)
        grep_process = subprocess.Popen(["grep", "-E", "(call|jmp)\\s*\\w*\\s+(\\[|r[a|b|c|d]x|r[s|d]i|r[b|s]p|r\\d|e[a|b|c|d]x|e[s|d]i|e[b|s]p)", disas_file_name], stdout=subprocess.PIPE)
        awk_process = subprocess.Popen(["awk", "{print $1}"], stdin=grep_process.stdout, stdout=subprocess.PIPE, text=True)
        branch_addresses = [int(line.strip(), 16) for line in awk_process.communicate()[0].splitlines()]
        with open(branch_address_cache, "w") as fout:
            fout.write(json.dumps(branch_addresses))
        return branch_addresses


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
