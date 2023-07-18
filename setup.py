import sys
from cx_Freeze import setup, Executable

base = None
if (sys.platform == "win32"):
    base = "Win32GUI"    

executables = [Executable("main.pyw", base=base)]

packages = ["idna"]
options = {
    'build_exe': {    
        'packages':packages,
    },    
}

setup(
    name = "tribometer",
    options = options,
    version = "0.1.0",
    description = '',
    executables = executables
)