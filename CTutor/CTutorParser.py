import clang
import clang.cindex

import logging
LOGGING_FORMAT= "%(name)s:%(levelname)s %(module)s:%(lineno)d:  %(message)s"
logging.basicConfig(filename="CTutor.log", level=logging.DEBUG, format= LOGGING_FORMAT)

# CParser currently only used to analyse the C file and do the 
# followings
#  - Findout whether the file has dangerous file operation function calls
#  - TODO: get the live range of each variable
class CParser(object):
  BLOCK_FUNC_LST = [
    "fopen",
    "fprintf",
    "fwrite",
    "fputs",
    "scanf",
  ]

  def __init__(self, fn):
    index = clang.cindex.Index.create()
    # treat as c++ language
    self._parser = index.parse(fn, args=['-x', 'c++'])
    diagnostics = list(self._parser.diagnostics)
    if len(diagnostics) > 0:
      logging.error( 'There were parse errors, diagnostics:%s'%str(diagnostics))

  
  def check_all_func_call(self):
      cursor = self._parser.cursor
      logging.debug("Start check cursor recursivelly")
      return self.visitor(cursor)

  def visitor(self, cursor):
    logging.debug("visit %s"%str(cursor.kind))
    if cursor.kind == clang.cindex.CursorKind.CALL_EXPR:
      logging.debug("visit found %s [line=%s, col=%s]"%(
        cursor.displayname, cursor.location.line, cursor.location.column))
      if cursor.displayname in self.BLOCK_FUNC_LST:
        return True

    children = list(cursor.get_children())
    logging.debug("visit get %d children"%(len(children)))

    for child in children:
      found = self.visitor(child)
      if found:
        return True

    return False



