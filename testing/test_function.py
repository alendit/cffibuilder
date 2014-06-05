import py
import math, os, sys
import ctypes.util
from cffibuilder.backend_ctypes import CTypesBackend
from testing.udir import udir
from testing.utils import build_ffi

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO


class FdWriteCapture(object):
    """xxx limited to capture at most 512 bytes of output, according
    to the Posix manual."""

    def __init__(self, capture_fd):
        self.capture_fd = capture_fd

    def __enter__(self):
        self.read_fd, self.write_fd = os.pipe()
        self.copy_fd = os.dup(self.capture_fd)
        os.dup2(self.write_fd, self.capture_fd)
        return self

    def __exit__(self, *args):
        os.dup2(self.copy_fd, self.capture_fd)
        os.close(self.copy_fd)
        os.close(self.write_fd)
        self._value = os.read(self.read_fd, 512)
        os.close(self.read_fd)

    def getvalue(self):
        return self._value

lib_m = 'm'
if sys.platform == 'win32':
    #there is a small chance this fails on Mingw via environ $CC
    import distutils.ccompiler
    if distutils.ccompiler.get_default_compiler() == 'msvc':
        lib_m = 'msvcrt'

class TestFunction(object):
    Backend = CTypesBackend

    def test_sin(self):
        ffi = build_ffi(self.Backend(), cdef="""
            double sin(double x);
        """)
        m = ffi.dlopen(lib_m)
        x = m.sin(1.23)
        assert x == math.sin(1.23)

    def test_sinf(self):
        if sys.platform == 'win32':
            py.test.skip("no sinf found in the Windows stdlib")
        ffi = build_ffi(self.Backend(), cdef="""
            float sinf(float x);
        """)
        m = ffi.dlopen(lib_m)
        x = m.sinf(1.23)
        assert type(x) is float
        assert x != math.sin(1.23)    # rounding effects
        assert abs(x - math.sin(1.23)) < 1E-6

    def test_sin_no_return_value(self):
        # check that 'void'-returning functions work too
        ffi = build_ffi(self.Backend(), cdef="""
            void sin(double x);
        """)
        m = ffi.dlopen(lib_m)
        x = m.sin(1.23)
        assert x is None

    def test_dlopen_filename(self):
        path = ctypes.util.find_library(lib_m)
        if not path:
            py.test.skip("%s not found" % lib_m)
        ffi = build_ffi(self.Backend(), cdef="""
            double cos(double x);
        """)
        m = ffi.dlopen(path)
        x = m.cos(1.23)
        assert x == math.cos(1.23)

        m = ffi.dlopen(os.path.basename(path))
        x = m.cos(1.23)
        assert x == math.cos(1.23)

    def test_dlopen_flags(self):
        ffi = build_ffi(self.Backend(), cdef="""
            double cos(double x);
        """)
        m = ffi.dlopen(lib_m, ffi.RTLD_LAZY | ffi.RTLD_LOCAL)
        x = m.cos(1.23)
        assert x == math.cos(1.23)

    def test_tlsalloc(self):
        if sys.platform != 'win32':
            py.test.skip("win32 only")
        if self.Backend is CTypesBackend:
            py.test.skip("ctypes complains on wrong calling conv")
        ffi = build_ffi(self.Backend(), cdef="long TlsAlloc(void); int TlsFree(long);")
        lib = ffi.dlopen('KERNEL32.DLL')
        x = lib.TlsAlloc()
        assert x != 0
        y = lib.TlsFree(x)
        assert y != 0

    def test_fputs(self):
        if not sys.platform.startswith('linux'):
            py.test.skip("probably no symbol 'stderr' in the lib")
        ffi = build_ffi(self.Backend(), cdef="""
            int fputs(const char *, void *);
            void *stderr;
        """)
        ffi.C = ffi.dlopen(None)
        ffi.C.fputs   # fetch before capturing, for easier debugging
        with FdWriteCapture(2) as fd:
            ffi.C.fputs(b"hello\n", ffi.C.stderr)
            ffi.C.fputs(b"  world\n", ffi.C.stderr)
        res = fd.getvalue()
        assert res == b'hello\n  world\n'

    def test_fputs_without_const(self):
        if not sys.platform.startswith('linux'):
            py.test.skip("probably no symbol 'stderr' in the lib")
        ffi = build_ffi(self.Backend(), cdef="""
            int fputs(char *, void *);
            void *stderr;
        """)
        ffi.C = ffi.dlopen(None)
        ffi.C.fputs   # fetch before capturing, for easier debugging
        with FdWriteCapture(2) as fd:
            ffi.C.fputs(b"hello\n", ffi.C.stderr)
            ffi.C.fputs(b"  world\n", ffi.C.stderr)
        res = fd.getvalue()
        assert res == b'hello\n  world\n'

    def test_vararg(self):
        if not sys.platform.startswith('linux'):
            py.test.skip("probably no symbol 'stderr' in the lib")
        ffi = build_ffi(self.Backend(), cdef="""
           int fprintf(void *, const char *format, ...);
           void *stderr;
        """)
        ffi.C = ffi.dlopen(None)
        with FdWriteCapture(2) as fd:
            ffi.C.fprintf(ffi.C.stderr, b"hello with no arguments\n")
            ffi.C.fprintf(ffi.C.stderr,
                          b"hello, %s!\n", ffi.new("char[]", b"world"))
            ffi.C.fprintf(ffi.C.stderr,
                          ffi.new("char[]", b"hello, %s!\n"),
                          ffi.new("char[]", b"world2"))
            ffi.C.fprintf(ffi.C.stderr,
                          b"hello int %d long %ld long long %lld\n",
                          ffi.cast("int", 42),
                          ffi.cast("long", 84),
                          ffi.cast("long long", 168))
            ffi.C.fprintf(ffi.C.stderr, b"hello %p\n", ffi.NULL)
        res = fd.getvalue()
        assert res == (b"hello with no arguments\n"
                       b"hello, world!\n"
                       b"hello, world2!\n"
                       b"hello int 42 long 84 long long 168\n"
                       b"hello (nil)\n")

    def test_must_specify_type_of_vararg(self):
        ffi = build_ffi(self.Backend(), cdef="""
           int printf(const char *format, ...);
        """)
        ffi.C = ffi.dlopen(None)
        e = py.test.raises(TypeError, ffi.C.printf, b"hello %d\n", 42)
        assert str(e.value) == ("argument 2 passed in the variadic part "
                                "needs to be a cdata object (got int)")

    def test_function_has_a_c_type(self):
        ffi = build_ffi(self.Backend(), cdef="""
            int puts(const char *);
        """)
        ffi.C = ffi.dlopen(None)
        fptr = ffi.C.puts
        assert ffi.typeof(fptr) == ffi.typeof("int(*)(const char*)")
        if self.Backend is CTypesBackend:
            assert repr(fptr).startswith("<cdata 'int puts(char *)' 0x")

    def test_function_pointer(self):
        ffi = build_ffi(self.Backend(), cdef="""
            int fputs(const char *, void *);
            void *stderr;
        """)
        def cb(charp):
            assert repr(charp).startswith("<cdata 'char *' 0x")
            return 42
        fptr = ffi.callback("int(*)(const char *txt)", cb)
        assert fptr != ffi.callback("int(*)(const char *)", cb)
        assert repr(fptr) == "<cdata 'int(*)(char *)' calling %r>" % (cb,)
        res = fptr(b"Hello")
        assert res == 42
        #
        if not sys.platform.startswith('linux'):
            py.test.skip("probably no symbol 'stderr' in the lib")
        ffi.C = ffi.dlopen(None)
        fptr = ffi.cast("int(*)(const char *txt, void *)", ffi.C.fputs)
        assert fptr == ffi.C.fputs
        assert repr(fptr).startswith("<cdata 'int(*)(char *, void *)' 0x")
        with FdWriteCapture(2) as fd:
            fptr(b"world\n", ffi.C.stderr)
        res = fd.getvalue()
        assert res == b'world\n'

    def test_callback_returning_void(self):
        ffi = build_ffi(self.Backend())
        for returnvalue in [None, 42]:
            def cb():
                return returnvalue
            fptr = ffi.callback("void(*)(void)", cb)
            old_stderr = sys.stderr
            try:
                sys.stderr = StringIO()
                returned = fptr()
                printed = sys.stderr.getvalue()
            finally:
                sys.stderr = old_stderr
            assert returned is None
            if returnvalue is None:
                assert printed == ''
            else:
                assert "None" in printed

    def test_passing_array(self):
        ffi = build_ffi(self.Backend(), cdef="""
            int strlen(char[]);
        """)
        ffi.C = ffi.dlopen(None)
        p = ffi.new("char[]", b"hello")
        res = ffi.C.strlen(p)
        assert res == 5

    def test_write_variable(self):
        if not sys.platform.startswith('linux'):
            py.test.skip("probably no symbol 'stdout' in the lib")
        ffi = build_ffi(self.Backend(), cdef="""
            void *stdout;
        """)
        C = ffi.dlopen(None)
        pout = C.stdout
        C.stdout = ffi.NULL
        assert C.stdout == ffi.NULL
        C.stdout = pout
        assert C.stdout == pout

    def test_strchr(self):
        ffi = build_ffi(self.Backend(), cdef="""
            char *strchr(const char *s, int c);
        """)
        ffi.C = ffi.dlopen(None)
        p = ffi.new("char[]", b"hello world!")
        q = ffi.C.strchr(p, ord('w'))
        assert ffi.string(q) == b"world!"

    def test_function_with_struct_argument(self):
        if sys.platform == 'win32':
            py.test.skip("no 'inet_ntoa'")
        if (self.Backend is CTypesBackend and
            '__pypy__' in sys.builtin_module_names):
            py.test.skip("ctypes limitation on pypy")
        ffi = build_ffi(self.Backend(), cdef="""
            struct in_addr { unsigned int s_addr; };
            char *inet_ntoa(struct in_addr in);
        """)
        ffi.C = ffi.dlopen(None)
        ina = ffi.new("struct in_addr *", [0x04040404])
        a = ffi.C.inet_ntoa(ina[0])
        assert ffi.string(a) == b'4.4.4.4'

    def test_function_typedef(self):
        py.test.skip("using really obscure C syntax")
        ffi = build_ffi(self.Backend(), cdef="""
            typedef double func_t(double);
            func_t sin;
        """)
        m = ffi.dlopen(lib_m)
        x = m.sin(1.23)
        assert x == math.sin(1.23)

    def test_fputs_custom_FILE(self):
        if self.Backend is CTypesBackend:
            py.test.skip("FILE not supported with the ctypes backend")
        filename = str(udir.join('fputs_custom_FILE'))
        ffi = build_ffi(self.Backend(), cdef="int fputs(const char *, FILE *);")
        C = ffi.dlopen(None)
        with open(filename, 'wb') as f:
            f.write(b'[')
            C.fputs(b"hello from custom file", f)
            f.write(b'][')
            C.fputs(b"some more output", f)
            f.write(b']')
        with open(filename, 'rb') as f:
            res = f.read()
        assert res == b'[hello from custom file][some more output]'

    def test_constants_on_lib(self):
        ffi = build_ffi(self.Backend(), cdef="""enum foo_e { AA, BB, CC=5, DD };
                    typedef enum { EE=-5, FF } some_enum_t;""")
        lib = ffi.dlopen(None)
        assert lib.AA == 0
        assert lib.BB == 1
        assert lib.CC == 5
        assert lib.DD == 6
        assert lib.EE == -5
        assert lib.FF == -4

    def test_void_star_accepts_string(self):
        ffi = build_ffi(self.Backend(), cdef="""int strlen(const void *);""")
        lib = ffi.dlopen(None)
        res = lib.strlen(b"hello")
        assert res == 5

    def test_signed_char_star_accepts_string(self):
        if self.Backend is CTypesBackend:
            py.test.skip("not supported by the ctypes backend")
        ffi = build_ffi(self.Backend(), cdef="""int strlen(signed char *);""")
        lib = ffi.dlopen(None)
        res = lib.strlen(b"hello")
        assert res == 5

    def test_unsigned_char_star_accepts_string(self):
        if self.Backend is CTypesBackend:
            py.test.skip("not supported by the ctypes backend")
        ffi = build_ffi(self.Backend(), cdef="""int strlen(unsigned char *);""")
        lib = ffi.dlopen(None)
        res = lib.strlen(b"hello")
        assert res == 5

    def test_missing_function(self):
        ffi = build_ffi(self.Backend(), cdef="""
            int nonexistent();
        """)
        m = ffi.dlopen(lib_m)
        assert not hasattr(m, 'nonexistent')

    def test_wraps_from_stdlib(self):
        import functools
        ffi = build_ffi(self.Backend(), cdef="""
            double sin(double x);
        """)
        def my_decorator(f):
            @functools.wraps(f)
            def wrapper(*args):
                return f(*args) + 100
            return wrapper
        m = ffi.dlopen(lib_m)
        sin100 = my_decorator(m.sin)
        x = sin100(1.23)
        assert x == math.sin(1.23) + 100

    def test_free_callback_cycle(self):
        if self.Backend is CTypesBackend:
            py.test.skip("seems to fail with the ctypes backend on windows")
        import weakref
        def make_callback(data):
            container = [data]
            callback = ffi.callback('int()', lambda: len(container))
            container.append(callback)
            # Ref cycle: callback -> lambda (closure) -> container -> callback
            return callback

        class Data(object):
            pass
        ffi = build_ffi(self.Backend())
        data = Data()
        callback = make_callback(data)
        wr = weakref.ref(data)
        del callback, data
        for i in range(3):
            if wr() is not None:
                import gc; gc.collect()
        assert wr() is None    # 'data' does not leak
