# Copyright (c) 2023 Kodeco LLC
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# Notwithstanding the foregoing, you may not use, copy, modify, merge, publish,
# distribute, sublicense, create a derivative work, and/or sell copies of the
# Software in any work that is designed, intended, or marketed for pedagogical or
# instructional purposes related to programming, coding, application development,
# or information technology.  Permission for such use, copying, modification,
# merger, publication, distribution, sublicensing, creation of derivative works,
# or sale is expressly withheld.
#
# This project and source code may use libraries or frameworks that are
# released under various Open-Source licenses. Use of those libraries and
# frameworks are governed by their own individual licenses.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import lldb

def __lldb_init_module(debugger, internal_dict):
    debugger.HandleCommand('command script add -f BreakAfterRegex.breakAfterRegex bar')


def breakAfterRegex(debugger, command, result, internal_dict):
    target = debugger.GetSelectedTarget()
    breakpoint = target.BreakpointCreateByRegex(command)

    if not breakpoint.IsValid() or breakpoint.num_locations == 0:
        result.AppendWarning("Breakpoint isn't valid or hasn't found any hits.")
    else:
        result.AppendMessage("{}".format(breakpoint))
    
    breakpoint.SetScriptCallbackFunction("BreakAfterRegex.breakpointHandler")


class FinishPrintAndContinue:
    def __init__(self, thread_plan, dict):
        self.thread_plan = thread_plan
        self.step_out_thread_plan = thread_plan.QueueThreadPlanForStepOut(0, True)
        self.thread = self.thread_plan.GetThread()
        self.debugger = self.thread.GetProcess().GetTarget().GetDebugger()
        self.function_name = self.thread.GetSelectedFrame().GetFunctionName()

    def is_stale(self):
        if self.step_out_thread_plan.IsPlanStale():
            self.evaluate_return_object()
            return True
        else:
            return False

    def explains_stop(self, event):
        return False

    def should_stop(self, event):
        if self.step_out_thread_plan.IsPlanComplete():
            self.evaluate_return_object()
            self.thread_plan.SetPlanComplete(True)
        return False

    def evaluate_return_object(self):
        output = evaluateReturnedObject(self.debugger, self.thread, self.function_name)
        if output is not None:
            print(output)

    def stop_description(self, stream):
        self.step_out_thread_plan.GetDescription(stream)


def breakpointHandler(frame, bp_loc, dict):
    '''The function called when the regular
    expression breakpoint gets triggered
    '''

    thread: lldb.SBThread = frame.GetThread()
    debugger = thread.GetProcess().GetTarget().GetDebugger()
    debugger.SetAsync(False)
    thread.StepUsingScriptedThreadPlan("BreakAfterRegex.FinishPrintAndContinue", False)
    
    return False

def evaluateReturnedObject(debugger, thread, function_name):
    '''Grabs the reference from the return register
    and returns a string from the evaluated value.
    TODO ObjcOnly
    '''
    
    res = lldb.SBCommandReturnObject()

    interpreter = debugger.GetCommandInterpreter()
    target = debugger.GetSelectedTarget()
    frame = thread.GetSelectedFrame()
    parent_function_name = frame.GetFunctionName()

    expression = 'expression -lobjc -O -- $arg1'

    interpreter.HandleCommand(expression, res)

    if res.HasResult():
        output = '{}\nbreakpoint: '\
            '{}\nobject: {}\nstopped:{}'.format(
                '*' * 80,
                function_name,
                res.GetOutput().replace('\n', ''),
                parent_function_name
            )
        return output
    else:
        return None
