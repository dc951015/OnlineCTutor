from __future__ import print_function

import json
import lldb, sys
import logging
import codecs
from CTutorUtils import CTutorFP, CTutorFPEncoder

# "int"/"long"/"long long" are treated the same way
# "float"/"double" are treated the same way
# Pointer with address is ["REF", address]
# "struct" and "class" is mapped to DICT. Field names are used as DICT keys.
#    Only difference with "union" is that for latter memory addresses overlap.
#
# Heap has address as keys. Memory is organized as chunks, each chunk has a type, which will
#   determine how the chunk will be visualized.
#
# Value at an address are fetched by letting LLDB read memory. We query LLDB for field types.
#
# array are treated as LIST.
#
# "malloc/realloc/calloc" allocates multiple data chunks in heap.
#    (It cannot be a LIST as LIST is not recursive.)
#    This way we would allow pointer arithmetic.
#    TODO can we read memory size from instruction rather than instrumentation?
# "free" deletes all data chunks. TODO do we need maintain count of data chunks?
#
# C++ support:
#    Instance method of "class" is treated as a field in DICT.
#    Static method of "class" is treated as globals.
#    TODO: Reference type.
#
# Ban these operations:
#   Free part of allocated memory.
#   Type casting. (By strict-type checking?)
#   step into other library functions such as printf
#

# TODO handle on stack struct variable
# this is difficult as need to track lifetime of the variable

# TODO support multiple level pointer

class Trace(object) :

  MAX_STDOUT = 100

  MAX_NUM_STEP = 100

  kUnknownType = None
  IGNORE_SBVALUE_NAME_LST = [
     "__FRAME_END__",
     "__dso_handle",
  ]
  
  POINTTO_UNKNOWN=0
  POINTTO_HEAP=1
  POINTTO_GLOBAL=2
  POINTTO_STACK=3
  

  def __init__(self, src, binary, trace):
    self.dbg = lldb.SBDebugger.Create()
    self.dbg.SetAsync(False)
    lldb.debugger = self.dbg

    self.ci = self.dbg.GetCommandInterpreter()
    self.pytutor_trace = {}
    self.trace = []
    self.heap = {}
    self.heap_allocations = {} # dict of address -> (type, #byte)
    self.stdout = ''
    self.src_fn = src
    self.bin_fn = binary
    self.trace_fn = trace
  
    self.error = lldb.SBError()
    self._NDEBUG=False

    #double direction dict between global varname and its addr
    self._global_addr_name_dmap={} 


    #double direction dict between stack varname and its addr
    self._stack_addr={}

  def run(self):

    self.pytutor_trace['code'] = open(self.src_fn).read()

    self.exec_command('file ' + self.bin_fn)
    self.exec_command('b _start')
    self.exec_command('b main')
    self.exec_command('r')

    self.target = self.dbg.GetSelectedTarget()
    self.process = self.target.GetProcess()
    self.thread = self.process.GetSelectedThread()

    # walk around for the aliyun platform
    start_frame = self.thread.GetSelectedFrame()
    pc_addr = start_frame.GetPC()
    new_pc_addr = pc_addr + 2
    start_frame.SetPC(new_pc_addr)
    logging.debug("run: set the PC from %s to %s to a new value to walk around the aliyun bug"%(pc_addr, new_pc_addr))
    self.exec_command('c')

    succeeded = True
    num_step = 0
    # The main loop to check each step, and generate the trace information
    # for such step
    while succeeded:
      cur_line_num = self.get_line_number()
      logging.debug("#####Dump trace at %s Line %d "%(self.get_file_path(), cur_line_num))
      self.dump_status(self.target)
      logging.debug("#####Dump trace at %s Line %d Done. Current Step %d "%(self.get_file_path(), cur_line_num, num_step))
      succeeded = self.exec_command('s').Succeeded()
      num_step += 1
      if num_step >= Trace.MAX_NUM_STEP:
        logging.debug("Break the trace record, step exceeds the MAX_NUM_STEP %d"%(Trace.MAX_NUM_STEP))
        break
      if self.get_file_path() != self.src_fn:
        succeeded = self.exec_command('finish').Succeeded()
        logging.debug("Not in the source code file anymore, might be a printf function call"
                      ", finish current frame, so that the control could return back to the"
                      " original source code file")
      line_number = self.get_line_number()
      if line_number == 0:
        logging.debug("Current Line number:%d, break"%line_number)
        break
    self.process.Destroy()
    logging.debug('before exit')
    self.exec_command('exit')
    self.pytutor_trace['trace'] = self.trace
    
    if self._NDEBUG:
      pytutor_trace_str = json.dumps(self.pytutor_trace)
    else:
      pytutor_trace_str = json.dumps(self.pytutor_trace, sort_keys=True, indent=2, separators=(',',':'), 
                                     cls = CTutorFPEncoder)

    logging.debug(pytutor_trace_str)
    codecs.open(self.trace_fn,'w','utf-8').write(" var demoTrace = " + pytutor_trace_str + ";")

  def is_string_type(self, type_):
    assert False

  def read_memory(self, addr, type_size):
    return self.process.ReadMemory(addr, type_size, self.error)
  
  def read_string(self, addr):
    str = ''
    i = 0
    while True:
      c = self.read_memory(addr + i, 1)
      i += 1
      if c == '\x00':break
      str += c
    return str


  def parse_sb_value(self, sb_value):
    logging.debug("parse_sb_value: %s -> %s"%( sb_value.GetName(), str(self.variable_view(sb_value))))
    return (sb_value.GetName(), self.variable_view(sb_value))

  def get_frame_description(self, frame, index):
    locals_ = {}
    sb_value_list = frame.GetVariables(1,1,0,0)
    for i in xrange(sb_value_list.GetSize()):
      sb_value = sb_value_list.GetValueAtIndex(i)
      if self.show_sb_value(sb_value) and sb_value.is_in_scope:
        (name, value) = self.parse_sb_value(sb_value)
        locals_[name] = value

    func_name = self.get_function_name(frame)

    desc = {}
    desc['frame_id'] = index + 1
    desc['encoded_locals'] = locals_
    desc['func_name'] = func_name
    desc['unique_hash'] = func_name + str(index)
    desc['ordered_varnames'] = locals_.keys()

    # ignore these ields
    desc['parent_frame_id_list'] = [] 
    desc['is_zombie'] = False 
    desc['is_parent'] = False
 
    return desc

  def get_stack_to_render(self):
    frames = []
    num_frames = self.thread.GetNumFrames()
    for i in xrange(num_frames):
      frame = self.thread.GetFrameAtIndex(i)
      desc = self.get_frame_description(frame,i)
      desc['is_highlighted'] = (i == 0)
      frames += [desc]
      if desc['func_name'] == 'main':break
    return frames

  def get_globals(self, target):
    module = target.module_iter().next()
    globals_ = {}
    import pdb
    for sym in module:
      sb_value_list = target.FindGlobalVariables(sym.name,1)
      try:
        sb_value = sb_value_list.GetValueAtIndex(0)
        if self.show_sb_value(sb_value) and sb_value.is_in_scope:
          # pdb.set_trace()
          (name, value) = self.parse_sb_value(sb_value)
          globals_[name] = value
          addr_sb_value = sb_value.AddressOf()
          addr_value = self.variable_view(addr_sb_value, get_pointer_addr=True)
          self._global_addr_name_dmap[name] = addr_value
          self._global_addr_name_dmap[addr_value] = name
          logging.debug("Get global: %s->%s, addr:%d"%(name, value, addr_value))
      except:
        logging.error(("Unexpected error:", sys.exc_info()[0]))
    return globals_

  def show_sb_value(self, sb_value):
    sb_name = sb_value.GetName()
    if sb_name == None:
       return False
   
    # For C, there are some other symbols which is not
    # related to the current program, we should ignore to
    # show such symbol to our client.
    if sb_name in self.IGNORE_SBVALUE_NAME_LST:
       return False

    return True   


  def get_function_name(self, frame):
    func_name = frame.GetFunctionName()
    if func_name == None:
      return ''
    else:
      return func_name

  def get_line_number(self):
    return self.thread.GetSelectedFrame().GetLineEntry().GetLine()

  def get_file_path(self):
    return self.thread.GetSelectedFrame().GetLineEntry().GetFileSpec().__get_fullpath__()

  def to_heap_key(self, value):
    if type(value) == type(1) or type(value) == type(long(1)):
      logging.debug("to_heap_key: type %s ,value %s"%(type(value), value))
      return (value)
    elif type(value) == type("hello"):
      logging.debug("to_heap_key: type %s ,value %s"%(type(value), value))
      return (int(value, 0))
    else:
      logging.error("Unhandled value:%s with type:%s"%(str(value), str(type(value))))
      return (int(value, 0))

  def to_global_key(self, value):
    global_name = self._global_addr_name_dmap[value]
    return global_name
    

  def point_to(self, sb_value, pointer_val):
    #return pointer_val != 0

    # For argv pased to main function, this is just a pointer
    if sb_value.GetName() == "argv":
       return True

    # TODO, support pointer to frame variables
    found = False
    logging.debug("check pointer_val %d"%pointer_val)

    # Check Heap
    for addr in self.heap_allocations:
      #import pdb
      #pdb.set_trace()
      (typ, num_bytes) = self.heap_allocations[addr]
      if addr <= pointer_val <= addr + num_bytes:
        found = True
        break

    logging.debug("is_valid_pointer: check whether it is a valid point to heap: %s"%(str(found)))
    if found:
      return self.POINTTO_HEAP

    # Check Global
    for addr in self._global_addr_name_dmap:
      if type(addr) is str:
        # the dmap have mixed type of key, we only need to check
        # if the key is long int
        continue
      name = self._global_addr_name_dmap[addr]
      if addr == pointer_val and len(name)>0 :
        logging.debug("Check global_addr for pointer %d <--> %s"%(addr, name))
        found = True
        break

    logging.debug("is_valid_pointer: check whether it is a valid point to global vars: %s"%(str(found)))
    if found:
      return self.POINTTO_GLOBAL



    # Check Stack
  
    logging.debug("is_valid_pointer: check whether it is a valid point to stack vars: %s"%(str(found)))
    return self.POINTTO_UNKNOWN

  def process_stdout(self, stdout):
    ALLOC_TAG = 'Alloc = '
    FREE_TAG = 'free' 
    logging.debug("Process stdout: %s"% stdout)
    if stdout.startswith(ALLOC_TAG):
      fields = stdout.split()
      self.heap_allocations[int(self.to_heap_key(fields[2]))] = (self.kUnknownType, int(fields[4]))
      logging.debug("heap_allocations alloc: %s -> %s"%(self.to_heap_key(fields[2]), str((self.kUnknownType, int(fields[4])))))
      new_stdout = "\r\n".join(stdout.split('\r\n')[1:])
      return new_stdout
    elif stdout.startswith(FREE_TAG):
      fields = stdout.split()
      logging.debug("Heap_allocations free: %s "% self.to_heap_key(fields[1]))
      del self.heap_allocations[int(self.to_heap_key(fields[1]))]
      new_stdout = "\r\n".join(stdout.split('\r\n')[1:])
      return new_stdout
    else:
      return stdout

  def size_of_type(self, typ): #typ is SBType
    if typ == self.kUnknownType:
      return 1
    else:
      #      print('size_of_type', typ)
      return typ.size

  def put_in_heap(self, sb_value):
    # Propogate type information to heap_allocations
    heap_allocations = dict(self.heap_allocations)
    for addr in self.heap_allocations:
      (typ, num_bytes) = self.heap_allocations[addr]
      if typ != self.kUnknownType:
        continue
      chunk_size = self.size_of_type(typ)
      num_chunks = num_bytes / chunk_size
      for i in xrange(num_chunks):
        chunk_addr = addr + i * chunk_size
        if chunk_addr == sb_value.GetValueAsUnsigned(self.error):
          # Update type
          heap_allocations[self.to_heap_key(addr)] = (sb_value.GetType().GetPointeeType(), heap_allocations[self.to_heap_key(addr)][1])
          break
    self.heap_allocations = heap_allocations
    
    key = self.to_heap_key(sb_value.GetValueAsUnsigned(self.error))
    if not key in self.heap:
      value = self.object_view(sb_value)
      self.heap[key] = value
      logging.debug("Put in heap: %s -> %s"%(key, value))
    else:
      logging.debug("Do not put in heap for key: %s, since it is not in self.heap"%key)

  def variable_view(self, sb_value, get_pointer_addr=False):
    value = None
    type_ = sb_value.GetType()
    logging.debug("get_pointer_addr=%s"%str(get_pointer_addr))
    if type_.IsPointerType() and type_.GetPointeeType() == type_.GetBasicType(lldb.eBasicTypeChar):
      # handle string
      value = self.read_string(sb_value.GetValueAsUnsigned(self.error))
      logging.debug("variable_view for string %s : %s"%(sb_value.GetName(), value))
    elif type_.IsPointerType() and get_pointer_addr:
      value = sb_value.GetValueAsUnsigned(self.error)
      logging.debug("variable_view for pointer %s, since get_pointer_addr is set, just return the pointer value:%d"%(sb_value.GetName(), value))
    elif type_.IsPointerType():
      # handle Pointer type
      value = sb_value.GetValueAsUnsigned(self.error)
      logging.debug("variable_view for pointer %s, the unsigned value is %d "%(sb_value.GetName(), value))
      pointto = self.point_to(sb_value, value)
      if pointto == self.POINTTO_HEAP:
        value = ["REF", self.to_heap_key(value), "REF_HEAP"]
        self.put_in_heap(sb_value)
      elif pointto == self.POINTTO_GLOBAL:
        value = ["REF", self.to_global_key(value), "REF_GLOBAL"]
      #TODO: add support for point to stack
      else:
        value = "Invalid"
    elif type_ == type_.GetBasicType(lldb.eBasicTypeInt):
      value = sb_value.GetValueAsSigned(self.error)
      logging.debug("variable_view for int %s: %d."%(sb_value.GetName(), value))
    elif type_ == type_.GetBasicType(lldb.eBasicTypeFloat) or type_ == type_.GetBasicType(lldb.eBasicTypeDouble) :
      value = CTutorFP(sb_value.GetValue())
      logging.debug("variable_view for %s %s: %s, planning to round to %s"%(type_.GetName(), sb_value.GetName(), str(value.raw_val()), str(value)))
    elif type_ == type_.GetBasicType(lldb.eBasicTypeChar):
      value = sb_value.GetValue()
      logging.debug("variable_view for type %s %s: %s."%(type_.GetName(), sb_value.GetName(), str(value)))
    elif type_.GetTypeClass() == 1: #The type is array
      # TODO supports array and on-stack struct variable here.
      value=["LIST"]
      arr_sz = sb_value.GetNumChildren()
      for i in range(0, arr_sz):
        value.append(sb_value.GetChildAtIndex(i).GetValue())

      logging.debug("variable_view for array type %s, size %d: %s"%(type_.GetName(), arr_sz, " ".join(value)))
      
    else:
      #import pdb
      #pdb.set_trace()
      logging.warn("Unknown type for sbvalue %s: %s "%(sb_value.GetName(), type_.GetName()))
    return value

  def object_view(self, sb_value):
    value = None
    logging.debug("Object_view for %s"%(sb_value.GetName()))
    
    type_ = sb_value.GetType().GetPointeeType()
    if type_.GetNumberOfFields() > 0: # a struct/union/class type
      value = ["DICT"]
      for i in xrange(type_.GetNumberOfFields()):
        field_value = self.variable_view(sb_value.GetChildAtIndex(i))
        value += [[type_.GetFieldAtIndex(i).GetName(), field_value]]
    else:
      value = self.variable_view(sb_value.Dereference())
    if type(value) != type([]):
      value = ["LIST", value]

    logging.debug("Object_view for %s:%s"%(sb_value.GetName(), value))
    return value

  def dump_status(self, target):
    self.heap = {}
    self._global_addr_name_dmap={}
    self._stack_addr={}

    globals_ = self.get_globals(target)
    self.stdout += self.process_stdout(self.process.GetSTDOUT(Trace.MAX_STDOUT))
    frame = self.thread.GetSelectedFrame()
    stack_to_render = self.get_stack_to_render()
    ordered_globals = globals_.keys()
    line = self.get_line_number()
    event = self.thread.GetStopDescription(Trace.MAX_STDOUT)
    trace = {
      'ordered_globals' : ordered_globals, 
      'stdout' : self.stdout, 
      'func_name' : self.get_function_name(frame), 
      'stack_to_render' : stack_to_render, 
      'globals' : globals_,
      'heap' : dict(self.heap), 
      'line' : line,
      'event' : event, 
    };
    self.trace = self.trace + [trace]

  def exec_command(self, cmd):
    res = lldb.SBCommandReturnObject()
    self.ci.HandleCommand(cmd, res)
    if res.Succeeded():
      logging.debug('#' + res.GetOutput().strip() + '#')
    else:
      logging.debug(res.GetError().strip())
    return res

def main(argv):
  if argv[3] !=  '-o':
    print("Incorrect option")
    return 

  src, binary, trace = argv[1], argv[2], argv[4]

  trace = Trace(src, binary, trace)
  trace.run()

if __name__ == "__main__":
    main(sys.argv)
