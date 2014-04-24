CTutor
======

The CTutor is a variant of python tutor

License
====
   BSD licensed.

How to Run
------

`CTutor/` is the source code running in the server, which will generate an js file. 
This js file contains the trace information which will be used by the frontend js
engine to render.

To run it:

`$ cd  CTutor`

`$ ./c_tutor.py < hello.c > index.js`

put `index.js` to the python tutor `js/` directory, so that the front end could render it.


During `c_tutor.py` running, all the temporary files will be stored in `/tmp/` directory. 
And in the local dir, there will be a log file named `CTutor.log` generated to give 
log information during `c_tutor.py` running.

Prerequest
------

llvm, clang, lldb, and all the py-binding.

To run the FE, your running env should also statisfy the requirements of python-tutor.
  

Files 
------

In case for CJK (Chinese, Japanese, Korean) characters, all the intermediate and src file should be encoded as UTF-8 file.
CTutor currently contain the following files.

- `c_tutor.py` : The main entry to run the CTutor.
- `Trace.py`: The class used to call lldb to generate the trace, and put it in a js file.
- `Trace_test.py`: Unit test for trace generator, currently still under development.
- `Makefile_buildlib`: Makefile used to generate the library used for heap memory management. We need to get information about the `malloc`, `alloca` and `free` function call. It is used to generate libsample.so by running `$make -f Makefile_buildlib`
- `sample.c`: The source code for a self-defined `malloc/alloc/free` function.
- `hello.c`: An example code used to generate js.
  
TODO
------

- `DONE`: More unit tests to make the whole CTutor work during the more development
- more testcase from the Mengma C language class test.
  - `DONE`: CJK Chars support
- How to display pointers
- Support for stdin input operation, such as scanf
- `DONE`: Support for floating point numbers
- Support for array
  - `DONE`: Array in stack frame
- Array in global scope
- Support for large strings
- `DONE`: Adjust the tempoary file path layout according to the discussion with Danny. 
  - source code and output js all stored in files, do not use `stdin/stdout` anymore
  - source code in a subdir of  `/tmp`
  - generated code in another subdir of `/tmp`
- Display the variable based on the live scope, not display it all the time.

- BUG: CTutor sometimes crashes
  - When running the small testcase, sometimes CTutor does not generate full trace, but only part of the trace. we need to findout why. 

- FE adjustment:
  - test/0006: For complex array display, The render frame still have display problem, the array displayed is out of the box range.
   
Unexpected behaviors
---_--

- printf string without `\n`: newline charactor will be used to flush the stdout to the terminal, therefore if the printf string does not end with `\n`, the string will not be immediately output to the console. See testcase No. `0000`.
- When deploy on Aliyun Cloud, LLDB will suffer an run fail issue in _start function after loading the binary and start to run it  
