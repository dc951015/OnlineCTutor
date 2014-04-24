from __future__ import print_function
import logging
import json
import threading
import subprocess

LOGGING_FORMAT= "%(asctime)-15s %(name)s:%(levelname)s %(module)s:%(lineno)d:  %(message)s"
logging.basicConfig(filename="CTutor.log", level=logging.DEBUG, format= LOGGING_FORMAT)



class CTutorFP(object):
  def __init__(self, val):
    if type(val) is float:
      self._val = val
    elif type(val) is str:
      self._val = float(val)
    else:
      logging.error("Init CTutorFP type with incorrect val type:%s, value:%s"%(type(val), str(val)))

  def __str__(self):
    return "%.4f"%self._val

  def raw_val(self):
    return self._val

class CTutorFPEncoder(json.JSONEncoder):
  def default(self, obj):
    if isinstance(obj, CTutorFP):
      return str(obj)
    return json.JSONEncoder.default(self, obj)

class CTutorCommand(object):
  def __init__(self, cmd):
    self.cmd = cmd
    self.process = None

  def run(self, timeout):
    def target():
      logging.debug("Thread %s start"%(" ".join(self.cmd)))
      self.process = subprocess.Popen(" ".join(self.cmd),stdout=subprocess.PIPE,stderr=subprocess.PIPE ,shell=True)
      logging.debug("Thread %s finish with output: %s\n %s\n"%(" ".join(self.cmd), self.process.stdout.read(), self.process.stderr.read()))
      self.process.communicate()

    thread = threading.Thread(target=target)
    thread.start()

    thread.join(timeout)
    if thread.is_alive():
      logging.debug("Thread %s terminate"%(" ".join(self.cmd)))
      self.process.terminate()
      thread.join()

    process_ret_code = self.process.returncode
    logging.debug("Thread %s exit with code:%s"%(" ".join(self.cmd), str(process_ret_code)))
    return process_ret_code
