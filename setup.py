#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Note: To use the 'upload' functionality of this file, you must:
#   $ pip install twine

import io
import os
import sys
import re
import shutil
from shutil import rmtree
import textwrap
import shlex
import subprocess

from setuptools import find_packages, setup, Command, Extension
from setuptools.command.build_ext import build_ext
from setuptools.command.sdist import sdist as sdist_orig
from distutils.errors import CompileError, DistutilsError, DistutilsPlatformError, LinkError, DistutilsSetupError, DistutilsExecError
from distutils import log as distutils_logger
from distutils.version import LooseVersion
import traceback

if os.path.isfile('./pre_setup_local.py'):
    import pre_setup_local as pre_setup
else:
    import pre_setup as pre_setup

server_lib = Extension('byteps.server.c_lib', [])
pytorch_lib = Extension('byteps.torch.c_lib', [])

# Package meta-data.
NAME = 'byteps'
DESCRIPTION = 'A high-performance cross-framework Parameter Server for Deep Learning'
URL = 'https://github.com/bytedance/byteps'
EMAIL = 'lab-hr@bytedance.com'
AUTHOR = 'Bytedance Inc.'
REQUIRES_PYTHON = '>=2.7.0'
VERSION = '0.2.5'

# What packages are required for this module to be executed?
REQUIRED = [
    'cloudpickle',
    # 'cffi>=1.4.0',
]

# What packages are optional?
EXTRAS = {
    # 'fancy feature': ['django'],
}

# The rest you shouldn't have to touch too much :)
# ------------------------------------------------
# Except, perhaps the License and Trove Classifiers!
# If you do change the License, remember to change the Trove Classifier for that!
os.environ["CC"] = "gcc"
os.environ["CXX"] = "g++"

here = os.path.abspath(os.path.dirname(__file__))

# Import the README and use it as the long-description.
# Note: this will only work if 'README.md' is present in your MANIFEST.in file!
try:
    with io.open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
        long_description = '\n' + f.read()
except OSError:
    long_description = DESCRIPTION

# Load the package's __version__.py module as a dictionary.
about = {}
if not VERSION:
    with open(os.path.join(here, NAME, '__version__.py')) as f:
        exec(f.read(), about)
else:
    about['__version__'] = VERSION


def is_build_action():
    if len(sys.argv) <= 1:
        return False

    if sys.argv[1].startswith('build'):
        return True

    if sys.argv[1].startswith('bdist'):
        return True

    if sys.argv[1].startswith('install'):
        return True


class UploadCommand(Command):
    """Support setup.py upload."""

    description = 'Build and publish the package.'
    user_options = []

    @staticmethod
    def status(s):
        """Prints things in bold."""
        print('\033[1m{0}\033[0m'.format(s))

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        try:
            self.status('Removing previous builds…')
            rmtree(os.path.join(here, 'dist'))
        except OSError:
            pass

        self.status('Building Source and Wheel (universal) distribution…')
        os.system(
            '{0} setup.py sdist bdist_wheel --universal'.format(sys.executable))

        self.status('Uploading the package to PyPI via Twine…')
        os.system('twine upload dist/*')

        self.status('Pushing git tags…')
        os.system('git tag v{0}'.format(about['__version__']))
        os.system('git push --tags')

        sys.exit()


# Start to build c libs
# ------------------------------------------------
def test_compile(build_ext, name, code, libraries=None, include_dirs=None, library_dirs=None,
                 macros=None, extra_compile_preargs=None, extra_link_preargs=None):
    test_compile_dir = os.path.join(build_ext.build_temp, 'test_compile')
    if not os.path.exists(test_compile_dir):
        os.makedirs(test_compile_dir)

    source_file = os.path.join(test_compile_dir, '%s.cc' % name)
    with open(source_file, 'w') as f:
        f.write(code)

    compiler = build_ext.compiler
    [object_file] = compiler.object_filenames([source_file])
    shared_object_file = compiler.shared_object_filename(
        name, output_dir=test_compile_dir)

    compiler.compile([source_file], extra_preargs=extra_compile_preargs,
                     include_dirs=include_dirs, macros=macros)
    compiler.link_shared_object(
        [object_file], shared_object_file, libraries=libraries, library_dirs=library_dirs,
        extra_preargs=extra_link_preargs)

    return shared_object_file


def get_mpi_flags():
    show_command = os.environ.get('BYTEPS_MPICXX_SHOW', 'mpicxx -show')
    try:
        mpi_show_output = subprocess.check_output(
            shlex.split(show_command), universal_newlines=True).strip()
        mpi_show_args = shlex.split(mpi_show_output)
        if not mpi_show_args[0].startswith('-'):
            # Open MPI and MPICH print compiler name as a first word, skip it
            mpi_show_args = mpi_show_args[1:]
        # strip off compiler call portion and always escape each arg
        return ' '.join(['"' + arg.replace('"', '"\'"\'"') + '"'
                         for arg in mpi_show_args])
    except Exception:
        raise DistutilsPlatformError(
            '%s failed (see error below), is MPI in $PATH?\n'
            'Note: If your version of MPI has a custom command to show compilation flags, '
            'please specify it with the BYTEPS_MPICXX_SHOW environment variable.\n\n'
            '%s' % (show_command, traceback.format_exc()))


def get_cpp_flags(build_ext):
    last_err = None
    default_flags = ['-std=c++17', '-fPIC', '-Ofast', '-frtti', '-Wall', '-shared', '-fopenmp', '-march=native', '-mno-avx512f'
                     ,'-lcudart', '-lnuma']
    flags_to_try = []
    if sys.platform == 'darwin':
        # Darwin most likely will have Clang, which has libc++.
        flags_to_try = [default_flags + ['-stdlib=libc++'],
                        default_flags]
    else:
        flags_to_try = [default_flags ,
                        default_flags + ['-stdlib=libc++']]
    for cpp_flags in flags_to_try:
        try:
            test_compile(build_ext, 'test_cpp_flags', extra_compile_preargs=cpp_flags,
                         code=textwrap.dedent('''\
                    #include <unordered_map>
                    void test() {
                    }
                    '''))

            return cpp_flags
        except (CompileError, LinkError):
            last_err = 'Unable to determine C++ compilation flags (see error above).'
        except Exception:
            last_err = 'Unable to determine C++ compilation flags.  ' \
                       'Last error:\n\n%s' % traceback.format_exc()

    raise DistutilsPlatformError(last_err)


def get_link_flags(build_ext):
    last_err = None
    libtool_flags = ['-Wl,-exported_symbols_list,byteps.exp']
    ld_flags = ['-Wl,--version-script=byteps.lds', '-fopenmp']
    flags_to_try = []
    if sys.platform == 'darwin':
        flags_to_try = [libtool_flags, ld_flags]
    else:
        flags_to_try = [ld_flags, libtool_flags]
    for link_flags in flags_to_try:
        try:
            test_compile(build_ext, 'test_link_flags', extra_link_preargs=link_flags,
                         code=textwrap.dedent('''\
                    void test() {
                    }
                    '''))

            return link_flags
        except (CompileError, LinkError):
            last_err = 'Unable to determine C++ link flags (see error above).'
        except Exception:
            last_err = 'Unable to determine C++ link flags.  ' \
                       'Last error:\n\n%s' % traceback.format_exc()

    raise DistutilsPlatformError(last_err)

def has_rdma_header():
    ret_code = subprocess.call(
        "echo '#include <rdma/rdma_cma.h>' | cpp -H -o /dev/null 2>/dev/null", shell=True)
    if ret_code != 0:
        import warnings
        warnings.warn("\n\n No RDMA header file detected. Will disable RDMA for compilation! \n\n")
    return ret_code==0

def use_ucx():
    byteps_with_ucx = int(os.environ.get('BYTEPS_WITH_UCX', 0))
    return byteps_with_ucx

def with_pre_setup():
    return int(os.environ.get('BYTEPS_WITHOUT_PRESETUP', 0)) == 0

def with_tensorflow():
    return int(os.environ.get('BYTEPS_WITH_TENSORFLOW', 0))

def without_tensorflow():
    return int(os.environ.get('BYTEPS_WITHOUT_TENSORFLOW', 0))

def with_pytorch():
    return int(os.environ.get('BYTEPS_WITH_PYTORCH', 0))

def without_pytorch():
    return int(os.environ.get('BYTEPS_WITHOUT_PYTORCH', 0))

def should_build_ucx():
    has_prebuilt_ucx = os.environ.get('BYTEPS_UCX_HOME', '')
    return use_ucx() and not has_prebuilt_ucx

ucx_default_home = '/usr/local'
def get_ucx_prefix():
    """ specify where to install ucx """
    ucx_prefix = os.getenv('BYTEPS_UCX_PREFIX', ucx_default_home)
    return ucx_prefix

def get_ucx_home():
    """ pre-installed ucx path """
    if should_build_ucx():
        return get_ucx_prefix()
    return os.environ.get('BYTEPS_UCX_HOME', ucx_default_home)

def get_common_options(build_ext):
    cpp_flags = get_cpp_flags(build_ext)
    link_flags = get_link_flags(build_ext)

    MACROS = [('EIGEN_MPL2_ONLY', 1)]
    INCLUDES = ['3rdparty/ps-lite/include']
    SOURCES = ['byteps/common/common.cc',
               'byteps/common/operations.cc',
               'byteps/common/core_loops.cc',
               'byteps/common/global.cc',
               'byteps/common/logging.cc',
               'byteps/common/communicator.cc',
               'byteps/common/scheduled_queue.cc',
               'byteps/common/ready_table.cc',
               'byteps/common/shared_memory.cc',
               'byteps/common/nccl_manager.cc',
               'byteps/common/cpu_reducer.cc'] + [
               'byteps/common/compressor/compressor_registry.cc',
               'byteps/common/compressor/error_feedback.cc',
               'byteps/common/compressor/momentum.cc',
               'byteps/common/compressor/impl/dithering.cc',
               'byteps/common/compressor/impl/onebit.cc',
               'byteps/common/compressor/impl/randomk.cc',
               'byteps/common/compressor/impl/topk.cc',
               'byteps/common/compressor/impl/vanilla_error_feedback.cc',
               'byteps/common/compressor/impl/nesterov_momentum.cc']
    if "BYTEPS_USE_MPI" in os.environ and os.environ["BYTEPS_USE_MPI"] == "1":
        mpi_flags = get_mpi_flags()
        COMPILE_FLAGS = cpp_flags + \
            shlex.split(mpi_flags) + ["-DBYTEPS_USE_MPI"]
        LINK_FLAGS = link_flags + shlex.split(mpi_flags)
    else:
        COMPILE_FLAGS = cpp_flags
        LINK_FLAGS = link_flags

    LIBRARY_DIRS = []
    LIBRARIES = []

    nccl_include_dirs, nccl_lib_dirs, nccl_libs = get_nccl_vals()
    INCLUDES += nccl_include_dirs
    LIBRARY_DIRS += nccl_lib_dirs
    LIBRARIES += nccl_libs

    # RDMA and NUMA libs
    LIBRARIES += ['numa']

    # auto-detect rdma
    if has_rdma_header():
        LIBRARIES += ['rdmacm', 'ibverbs', 'rt']
    if use_ucx():
        LIBRARIES += ['ucp', 'uct', 'ucs', 'ucm']
        ucx_home = get_ucx_home()
        if ucx_home:
            INCLUDES += [f'{ucx_home}/include']
            LIBRARY_DIRS += [f'{ucx_home}/lib']

    # ps-lite
    EXTRA_OBJECTS = ['3rdparty/ps-lite/build/libps.a',
                     '3rdparty/ps-lite/deps/lib/libzmq.a']

    return dict(MACROS=MACROS,
                INCLUDES=INCLUDES,
                SOURCES=SOURCES,
                COMPILE_FLAGS=COMPILE_FLAGS,
                LINK_FLAGS=LINK_FLAGS,
                LIBRARY_DIRS=LIBRARY_DIRS,
                LIBRARIES=LIBRARIES,
                EXTRA_OBJECTS=EXTRA_OBJECTS)


def build_server(build_ext, options):
    server_lib.define_macros = options['MACROS']
    server_lib.include_dirs = options['INCLUDES']
    server_lib.sources = ['byteps/server/server.cc',
                          'byteps/common/cpu_reducer.cc',
                          'byteps/common/logging.cc',
                          'byteps/common/common.cc'] + [
                          'byteps/common/compressor/compressor_registry.cc',
                          'byteps/common/compressor/error_feedback.cc',
                          'byteps/common/compressor/impl/dithering.cc',
                          'byteps/common/compressor/impl/onebit.cc',
                          'byteps/common/compressor/impl/randomk.cc',
                          'byteps/common/compressor/impl/topk.cc',
                          'byteps/common/compressor/impl/vanilla_error_feedback.cc']
    server_lib.extra_compile_args = options['COMPILE_FLAGS'] + \
        ['-DBYTEPS_BUILDING_SERVER']
    server_lib.extra_link_args = options['LINK_FLAGS']
    server_lib.extra_objects = options['EXTRA_OBJECTS']
    server_lib.library_dirs = options['LIBRARY_DIRS']

    # auto-detect rdma
    if has_rdma_header():
        server_lib.libraries = ['rdmacm', 'ibverbs', 'rt']
    else:
        server_lib.libraries = []
    if use_ucx():
        server_lib.libraries += ['ucp', 'uct', 'ucs', 'ucm']
        ucx_home = get_ucx_home()
        if ucx_home:
            server_lib.include_dirs += [f'{ucx_home}/include']
            server_lib.library_dirs += [f'{ucx_home}/lib']

    build_ext.build_extension(server_lib)

def check_macro(macros, key):
    return any(k == key and v for k, v in macros)


def set_macro(macros, key, new_value):
    if any(k == key for k, _ in macros):
        return [(k, new_value if k == key else v) for k, v in macros]
    else:
        return macros + [(key, new_value)]


def get_cuda_dirs(build_ext, cpp_flags):
    cuda_include_dirs = []
    cuda_lib_dirs = []

    cuda_home = os.environ.get('BYTEPS_CUDA_HOME')
    if cuda_home:
        cuda_include_dirs += ['%s/include' % cuda_home]
        cuda_lib_dirs += ['%s/lib' % cuda_home, '%s/lib64' % cuda_home]

    cuda_include = os.environ.get('BYTEPS_CUDA_INCLUDE')
    if cuda_include:
        cuda_include_dirs += [cuda_include]

    cuda_lib = os.environ.get('BYTEPS_CUDA_LIB')
    if cuda_lib:
        cuda_lib_dirs += [cuda_lib]

    if not cuda_include_dirs and not cuda_lib_dirs:
        # default to /usr/local/cuda
        cuda_include_dirs += ['/usr/local/cuda/include']
        cuda_lib_dirs += ['/usr/local/cuda/lib', '/usr/local/cuda/lib64']

    try:
        test_compile(build_ext, 'test_cuda', libraries=['cudart'], include_dirs=cuda_include_dirs,
                     library_dirs=cuda_lib_dirs, extra_compile_preargs=cpp_flags,
                     code=textwrap.dedent('''\
            #include <cuda_runtime.h>
            void test() {
                cudaSetDevice(0);
            }
            '''))
    except (CompileError, LinkError):
        raise DistutilsPlatformError(
            'CUDA library was not found (see error above).\n'
            'Please specify correct CUDA location with the BYTEPS_CUDA_HOME '
            'environment variable or combination of BYTEPS_CUDA_INCLUDE and '
            'BYTEPS_CUDA_LIB environment variables.\n\n'
            'BYTEPS_CUDA_HOME - path where CUDA include and lib directories can be found\n'
            'BYTEPS_CUDA_INCLUDE - path to CUDA include directory\n'
            'BYTEPS_CUDA_LIB - path to CUDA lib directory')

    return cuda_include_dirs, cuda_lib_dirs


def get_nccl_vals():
    nccl_include_dirs = []
    nccl_lib_dirs = []
    nccl_libs = []

    nccl_home = os.environ.get('BYTEPS_NCCL_HOME', '/usr/local/nccl')
    if nccl_home:
        nccl_include_dirs += ['%s/include' % nccl_home]
        nccl_lib_dirs += ['%s/lib' % nccl_home, '%s/lib64' % nccl_home]

    nccl_link_mode = os.environ.get('BYTEPS_NCCL_LINK', 'SHARED')
    if nccl_link_mode.upper() == 'SHARED':
        nccl_libs += ['nccl']
    else:
        nccl_libs += ['nccl_static']

    return nccl_include_dirs, nccl_lib_dirs, nccl_libs

def dummy_import_torch():
    try:
        import torch
    except:
        pass


def parse_version(version_str):
    if "dev" in version_str:
        return 9999999999
    m = re.match('^(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:\.(\d+))?', version_str)
    if m is None:
        return None

    # turn version string to long integer
    version = int(m.group(1)) * 10 ** 9
    if m.group(2) is not None:
        version += int(m.group(2)) * 10 ** 6
    if m.group(3) is not None:
        version += int(m.group(3)) * 10 ** 3
    if m.group(4) is not None:
        version += int(m.group(4))
    return version


def check_torch_version():
    try:
        import torch
        if torch.__version__ < '1.0.1':
            raise DistutilsPlatformError(
                'Your torch version %s is outdated.  '
                'BytePS requires torch>=1.0.1' % torch.__version__)
    except ImportError:
            print('import torch failed, is it installed?\n\n%s' %
                  traceback.format_exc())

    # parse version
    version = parse_version(torch.__version__)
    if version is None:
        raise DistutilsPlatformError(
            'Unable to determine PyTorch version from the version string \'%s\'' % torch.__version__)
    return version


def is_torch_cuda(build_ext, include_dirs, extra_compile_args):
    try:
        from torch.utils.cpp_extension import include_paths
        test_compile(build_ext, 'test_torch_cuda', include_dirs=include_dirs + include_paths(cuda=True),
                     extra_compile_preargs=extra_compile_args, code=textwrap.dedent('''\
            #include <THC/THC.h>
            void test() {
            }
            '''))
        return True
    except (CompileError, LinkError, EnvironmentError):
        print('INFO: Above error indicates that this PyTorch installation does not support CUDA.')
        return False


def build_torch_extension(build_ext, options, torch_version):
    pytorch_compile_flags = ["-std=c++17" if flag == "-std=c++17"
                             else flag for flag in options['COMPILE_FLAGS']]
    have_cuda = is_torch_cuda(build_ext, include_dirs=options['INCLUDES'],
                              extra_compile_args=pytorch_compile_flags)
    if not have_cuda and check_macro(options['MACROS'], 'HAVE_CUDA'):
        raise DistutilsPlatformError(
            'byteps build with GPU support was requested, but this PyTorch '
            'installation does not support CUDA.')

    # Update HAVE_CUDA to mean that PyTorch supports CUDA.
    updated_macros = set_macro(
        options['MACROS'], 'HAVE_CUDA', str(int(have_cuda)))

    # Export TORCH_VERSION equal to our representation of torch.__version__. Internally it's
    # used for backwards compatibility checks.
    updated_macros = set_macro(
       updated_macros, 'TORCH_VERSION', str(torch_version))

    # Always set _GLIBCXX_USE_CXX11_ABI, since PyTorch can only detect whether it was set to 1.
    import torch
    updated_macros = set_macro(updated_macros, '_GLIBCXX_USE_CXX11_ABI',
                               str(int(torch.compiled_with_cxx11_abi())))

    # PyTorch requires -DTORCH_API_INCLUDE_EXTENSION_H
    updated_macros = set_macro(
        updated_macros, 'TORCH_API_INCLUDE_EXTENSION_H', '1')

    if have_cuda:
        from torch.utils.cpp_extension import CUDAExtension as TorchExtension
    else:
        # CUDAExtension fails with `ld: library not found for -lcudart` if CUDA is not present
        from torch.utils.cpp_extension import CppExtension as TorchExtension

    ext = TorchExtension(pytorch_lib.name,
                         define_macros=updated_macros,
                         include_dirs=options['INCLUDES'],
                         sources=options['SOURCES'] + ['byteps/torch/ops.cc',
                                                       'byteps/torch/ready_event.cc',
                                                       'byteps/torch/cuda_util.cc',
                                                       'byteps/torch/adapter.cc',
                                                       'byteps/torch/handle_manager.cc'],
                         extra_compile_args=pytorch_compile_flags,
                         extra_link_args=options['LINK_FLAGS'],
                         extra_objects=options['EXTRA_OBJECTS'],
                         library_dirs=options['LIBRARY_DIRS'],
                         libraries=options['LIBRARIES'])

    # Patch an existing pytorch_lib extension object.
    for k, v in ext.__dict__.items():
        pytorch_lib.__dict__[k] = v
    build_ext.build_extension(pytorch_lib)

def build_ucx():
    ucx_tarball_path = os.getenv("BYTEPS_UCX_TARBALL_PATH", "")
    if not ucx_tarball_path and with_pre_setup() \
       and hasattr(pre_setup, 'ucx_tarball_path'):
        ucx_tarball_path = pre_setup.ucx_tarball_path.strip()

    if not ucx_tarball_path:
        if os.path.exists("./ucx.tar.gz"):
            ucx_tarball_path = os.path.join(here, './ucx.tar.gz')

    if not ucx_tarball_path:
        cmd = "curl -kL {} -o ucx.tar.gz".format("https://github.com/openucx/ucx/archive/refs/tags/v1.11.0.tar.gz")
        subprocess.run(cmd, shell=True)
        ucx_tarball_path = os.path.join(here, './ucx.tar.gz')

    print("ucx_tarball_path is", ucx_tarball_path)
    ucx_prefix = get_ucx_prefix()
    sudo_str = "" if os.access(ucx_prefix, os.W_OK) else "sudo"
    cmd = "mkdir -p tmp; tar xzf {} -C tmp; ".format(ucx_tarball_path) + \
          "rm -rf ucx-build; mkdir -p ucx-build; mv tmp/ucx-*/* ucx-build/; " + \
          "cd ucx-build; pwd; which libtoolize; " + \
          "./autogen.sh; ./autogen.sh && " + \
          "./contrib/configure-release --enable-mt --prefix={0} && make -j && {1} make install -j".format(ucx_prefix, sudo_str)
    make_process = subprocess.Popen(cmd,
                                    cwd='3rdparty',
                                    stdout=sys.stdout,
                                    stderr=sys.stderr,
                                    shell=True)
    make_process.communicate()
    if make_process.returncode:
        raise DistutilsSetupError('An ERROR occured while running the '
                                  'Makefile for the ucx library. '
                                  'Exit code: {0}'.format(make_process.returncode))

# run the customize_compiler
class custom_build_ext(build_ext):
    def build_extensions(self):
        if with_pre_setup():
            pre_setup.setup()

        ucx_home = get_ucx_home()
        ucx_prefix = get_ucx_prefix()
        make_option = ""
        # To resolve tf-gcc incompatibility
        has_cxx_flag = False
        glibcxx_flag = False

        # To resolve torch-gcc incompatibility
        if not without_pytorch():
            try:
                import torch
                torch_flag = torch.compiled_with_cxx11_abi()
                if has_cxx_flag:
                    if glibcxx_flag != torch_flag:
                        raise DistutilsError(
                            '-D_GLIBCXX_USE_CXX11_ABI is not consistent between TensorFlow and PyTorch, '
                            'consider install them separately.')
                    else:
                        pass
                else:
                    make_option += 'ADD_CFLAGS=-D_GLIBCXX_USE_CXX11_ABI=' + \
                                    str(int(torch_flag)) + ' '
                    has_cxx_flag = True
                    glibcxx_flag = torch_flag
            except:
                pass

        if not os.path.exists("3rdparty/ps-lite/build/libps.a") or \
           not os.path.exists("3rdparty/ps-lite/deps/lib"):
            print("should_build_ucx is", should_build_ucx())
            if should_build_ucx():
                build_ucx()

            if os.environ.get('CI', 'false') == 'false':
                make_option += "-j "
            if has_rdma_header():
                make_option += "USE_RDMA=1 "
            if use_ucx():
                make_option += 'USE_UCX=1 '
                if ucx_home:
                    make_option += f'UCX_PATH={ucx_home} '

            if with_pre_setup():
                make_option += pre_setup.extra_make_option()

            if os.path.exists("./zeromq-4.1.4.tar.gz"):
                zmq_tarball_path = os.path.join(here, './zeromq-4.1.4.tar.gz')
                make_option += " WGET='curl -O '  ZMQ_URL=file://" + zmq_tarball_path + " "

            make_process = subprocess.Popen('make ' + make_option,
                                            cwd='3rdparty/ps-lite',
                                            stdout=sys.stdout,
                                            stderr=sys.stderr,
                                            shell=True)
            make_process.communicate()
            if make_process.returncode:
                raise DistutilsSetupError('An ERROR occured while running the '
                                          'Makefile for the ps-lite library. '
                                          'Exit code: {0}'.format(make_process.returncode))

        options = get_common_options(self)
        if has_cxx_flag:
            options['COMPILE_FLAGS'] += ['-D_GLIBCXX_USE_CXX11_ABI=' + str(int(glibcxx_flag))]

        built_plugins = []
        try:
            build_server(self, options)
        except:
            raise DistutilsSetupError('An ERROR occured while building the server module.\n\n'
                                      '%s' % traceback.format_exc())

        # If PyTorch is installed, it must be imported before others, otherwise
        # we may get an error: dlopen: cannot load any more object with static TLS
        if not without_pytorch():
            dummy_import_torch()

        if not without_pytorch():
            try:
                torch_version = check_torch_version()
                build_torch_extension(self, options, torch_version)
                built_plugins.append(True)
                print('INFO: PyTorch extension is built successfully.')
            except:
                if not with_pytorch():
                    print('INFO: Unable to build PyTorch plugin, will skip it.\n\n'
                          '%s' % traceback.format_exc())
                    built_plugins.append(False)
                else:
                    raise

        if not built_plugins:
            print('INFO: Only server module is built.')
            return

# Where the magic happens:
if not os.path.exists('3rdparty/ps-lite/src'):
    msg = "Missing ./3rdparty/ps-lite, ps-lite is required to build BytePS."
    raise ValueError(msg)

if os.path.exists('launcher/launch.py'):
    if not os.path.exists('bin'):
        os.mkdir('bin')
    shutil.copyfile('launcher/launch.py', 'bin/bpslaunch')

extensions_to_build = [server_lib, pytorch_lib]

if without_pytorch():
    extensions_to_build.remove(pytorch_lib)

class sdist(sdist_orig):
    def run(self):
        try:
            if not os.path.isfile("./ucx.tar.gz"):
                self.spawn(['curl', '-kL', 'https://github.com/openucx/ucx/archive/refs/tags/v1.11.0.tar.gz', '-o', 'ucx.tar.gz'])
            if not os.path.isfile("./zeromq-4.1.4.tar.gz"):
                self.spawn(['curl', '-kL', '-O', 'https://github.com/zeromq/zeromq4-1/releases/download/v4.1.4/zeromq-4.1.4.tar.gz'])
        except DistutilsExecError:
            self.warn('failed to download required tarballs')
        super().run()

setup(
    name=NAME,
    version=about['__version__'],
    description=DESCRIPTION,
    long_description=long_description,
    long_description_content_type='text/markdown',
    author=AUTHOR,
    author_email=EMAIL,
    python_requires=REQUIRES_PYTHON,
    url=URL,
    packages=find_packages(exclude=('tests',)),
    install_requires=REQUIRED,
    extras_require=EXTRAS,
    include_package_data=True,
    license='Apache',
    classifiers=[
        # Trove classifiers
        # Full list: https://pypi.python.org/pypi?%3Aaction=list_classifiers
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Operating System :: POSIX :: Linux'
    ],
    ext_modules=extensions_to_build,
    # $ setup.py publish support.
    cmdclass={
        'upload': UploadCommand,
        'build_ext': custom_build_ext,
        'sdist': sdist
    },
    # cffi is required for PyTorch
    # If cffi is specified in setup_requires, it will need libffi to be installed on the machine,
    # which is undesirable.  Luckily, `install` action will install cffi before executing build,
    # so it's only necessary for `build*` or `bdist*` actions.
    setup_requires=[],
    scripts=['bin/bpslaunch']
)
