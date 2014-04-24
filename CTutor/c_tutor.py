#!/usr/bin/env python

from __future__ import print_function
import subprocess
import os
import sys
import logging
import tempfile
import codecs
import clang
from Trace import Trace
from CTutorUtils import CTutorCommand
from CTutorParser import CParser

LOGGING_FORMAT= "%(name)s:%(levelname)s %(module)s:%(lineno)d:  %(message)s"
logging.basicConfig(filename="CTutor.log", level=logging.DEBUG, format= LOGGING_FORMAT)

class CTutorSingle(object):
  COMPILER="clang"
  GCCCOMPILER="gcc"
  PYTHON="python"
  LIBSAMPLE="libsample.so"
  STATIC_LIBSAMPLE="libsample.a"
  TRACE_GENERATOR="trace.py"

  # second count for clang to finish the source code compile process
  MAX_COMPILE_TIME=20 
   
  def __init__(self, user_id, libpath=""):
    self.src_f = tempfile.NamedTemporaryFile(prefix=user_id, suffix=".c",  delete=False)
    self.bin_fn = self.src_f.name + ".exe"
    self.raw_trace_fn = self.src_f.name + ".rawt"
    self.trace_fn = self.src_f.name + ".trace"
    self.js_fn = self.src_f.name + ".js"
    self._libpath=libpath

  def stdin_to_ctmpfile(self):
    for line in sys.stdin:
      self.src_f.write(line)
    self.src_f.close()


  def file_to_ctmpfile(self, fn):
    c_f = open(fn, "r")
    for line in c_f:
      self.src_f.write(line)
    self.src_f.close()

  def build_src(self):
    #build_cmd_lst = [self.COMPILER, "-O0", "-static", "-g", self.src_f.name, self._libpath+self.STATIC_LIBSAMPLE, "-o "+self.bin_fn]
    build_cmd_lst = [self.COMPILER,"-O0", "-g", self.src_f.name, self._libpath+self.LIBSAMPLE, "-o "+self.bin_fn]
    #subprocess.check_output(" ".join(build_cmd_lst), shell=True)
    clang_command = CTutorCommand(build_cmd_lst)
    clang_ret = clang_command.run(timeout = self.MAX_COMPILE_TIME)
    logging.debug("Run cmd %s return %d"%(" ".join(build_cmd_lst), clang_ret))
    if clang_ret != 0:
      logging.error("Clang return with Non-0 code %d"%(clang_ret))
      # exit the process for security
      sys.exit(clang_ret)
    
  def check_blocked_function(self):
    #Check whether the code have dangerous system calls
    logging.debug("Check whether the c code have dangerous system call")
    cparser = CParser(self.src_f.name)
    has_dangerous_call = cparser.check_all_func_call()
    if has_dangerous_call:
      logging.error("The submited code has dangerous systems calls, Stop CTutor, filename:%s"%self.src_f.name)
      sys.exit("CTutor:Find Dangerous system call in the C src, stop render it")
      

  def generate_trace(self):
    trace_obj = Trace(self.src_f.name, self.bin_fn, self.trace_fn)
    trace_obj.run()

  def generate_tmpjs(self):
    js_f = codecs.open(self.js_fn, "w",'utf-8')
    trace_f = open(self.trace_fn, "r")
    for line in trace_f:
      js_f.write(line)

    trace_f.close()
    js_f.write("""$(document).ready(function() {
  // for rounded corners
  $(".activityPane").corner('15px');

  var demoViz = new ExecutionVisualizer('demoViz', demoTrace, {embeddedMode: true,
                                                               editCodeBaseURL: 'visualize.html'});

  // redraw connector arrows on window resize
  $(window).resize(function() {
    demoViz.redrawConnectors();
  });
});\n""")
    js_f.close()


  def tmpjs_to_stdout(self):
    js_f = open(self.js_fn, 'r')
    print(js_f.read())

  def tmpjs_to_js(self, new_js_fn):
    import shutil
    shutil.copyfile(self.js_fn, new_js_fn);
    

def main(argv):
  user_id = os.getenv("USERID", "Ctutor_USER_UNKNOWN_")
  logging.debug("c_tutor.py: call CTutor with parms %s, USERID=%s"%(" ".join(argv), user_id))
  tutor_obj = CTutorSingle(user_id, "/home/lingkun/CTutor/CTutor/")
  if len(argv) == 1:
    tutor_obj.stdin_to_ctmpfile()
  else:
    tutor_obj.file_to_ctmpfile(argv[1])
  tutor_obj.build_src()
  tutor_obj.check_blocked_function()
  tutor_obj.generate_trace()
  tutor_obj.generate_tmpjs()
  tutor_obj.tmpjs_to_stdout()
  if len(argv) == 3:
    tutor_obj.tmpjs_to_js(argv[2])

if __name__ == "__main__":
    main(sys.argv)
