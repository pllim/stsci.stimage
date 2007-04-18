from distutils.core import setup, Extension
from distutils import sysconfig
from distutils.command.install_data import install_data
import sys, os.path

numpyStatus = False
numarrayStatus = False

if not hasattr(sys, 'version_info') or sys.version_info < (2,3,0,'alpha',0):
    raise SystemExit, "Python 2.3 or later required to build imagestats."

try:
    import numpy
    import numpy.numarray as nn
except:
    raise ImportError("NUMPY was not found. It may not be installed or it may not be on your PYTHONPATH")

print "Building C extensions using NUMPY."
pythoninc = sysconfig.get_python_inc()

numpyinc = numpy.get_include()
numpynumarrayinc = nn.get_numarray_include_dirs()

if sys.platform != 'win32':
    imagestats_libraries = ['m']
else:
    imagestats_libraries = ['']

args = sys.argv[:]
for a in args:
    if a.startswith('--local='):
        dir = os.path.abspath(a.split("=")[1])
        sys.argv.extend([
                "--install-lib="+dir,
                ])
        #remove --local from both sys.argv and args
        args.remove(a)
        sys.argv.remove(a)

class smart_install_data(install_data):
    def run(self):
        #need to change self.install_dir to the library dir
        install_cmd = self.get_finalized_command('install')
        self.install_dir = getattr(install_cmd, 'install_lib')
        return install_data.run(self)


def getExtensions_numpy(args):
    ext = [Extension('imagestats.buildHistogram',['src/buildHistogram.c'],
                             define_macros=[('NUMPY', '1')],
                             include_dirs = [pythoninc,numpyinc]+numpynumarrayinc,
                             libraries = imagestats_libraries),
           Extension('imagestats.computeMean', ['src/computeMean.c'],
                             define_macros=[('NUMPY', '1')],
                             include_dirs = [pythoninc,numpyinc]+numpynumarrayinc,
                             libraries = imagestats_libraries)]

    return ext
"""
def getExtensions_numarray(args):
    numarrayIncludeDir = './'
    for a in args:
        if a.startswith('--home='):
            numarrayIncludeDir = os.path.abspath(os.path.join(a.split('=')[1], 'include', 'python', 'numarray'))
        elif a.startswith('--prefix='):
            numarrayIncludeDir = os.path.abspath(os.path.join(a.split('=')[1], 'include','python2.3', 'numarray'))
        elif a.startswith('--local='):
            numarrayIncludeDir = os.path.abspath(a.split('=')[1])

    ext = [NumarrayExtension('imagestats/buildHistogram',['src/buildHistogram.c'],
                             include_dirs = [numarrayIncludeDir],
                             libraries = ['m']),
           NumarrayExtension('imagestats/computeMean', ['src/computeMean.c'],
                             include_dirs = [numarrayIncludeDir],
                             libraries = ['m'])]
                             
    return ext
"""

def dosetup(ext):
    r = setup(name = "imagestats",
              version = "1.1.0",
              description = "Compute desired statistics values for array objects",
              author = "Warren Hack, Christopher Hanley",
              author_email = "help@stsci.edu",
              license = "http://www.stsci.edu/resources/software_hardware/pyraf/LICENSE",
              platforms = ["Linux","Solaris","Mac OS X", "Windows"],
              packages=['imagestats'],
              package_dir={'imagestats':'lib'},
              cmdclass = {'install_data':smart_install_data},
              data_files = [('imagestats',['lib/LICENSE.txt'])],
              ext_modules=ext)
    return r


if __name__ == "__main__":
    ext = getExtensions_numpy(args)
    dosetup(ext)


