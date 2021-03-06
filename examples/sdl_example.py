import os

from cffibuilder import Builder


builder = Builder()
builder.cdef("""
    #define SDL_ENABLE ...

    typedef uint8_t Uint8;

    typedef enum {
        SDL_FALSE = 0,
        SDL_TRUE  = 1
    } SDL_bool;

    typedef enum {
        SDL_GL_RED_SIZE,
        SDL_GL_GREEN_SIZE,
        SDL_GL_BLUE_SIZE,
        SDL_GL_ALPHA_SIZE,
        SDL_GL_BUFFER_SIZE,
        SDL_GL_DOUBLEBUFFER,
        SDL_GL_DEPTH_SIZE,
        SDL_GL_STENCIL_SIZE,
        SDL_GL_ACCUM_RED_SIZE,
        SDL_GL_ACCUM_GREEN_SIZE,
        SDL_GL_ACCUM_BLUE_SIZE,
        SDL_GL_ACCUM_ALPHA_SIZE,
        SDL_GL_STEREO,
        SDL_GL_MULTISAMPLEBUFFERS,
        SDL_GL_MULTISAMPLESAMPLES,
        SDL_GL_ACCELERATED_VISUAL,
        SDL_GL_SWAP_CONTROL
    } SDL_GLattr;

    Uint8 _pygame_SDL_BUTTON(Uint8 X);
""")
builder.build(
    "_sdl",  # module name
    srcdir=os.path.abspath(os.path.join(os.path.dirname(__file__), 'generated_pkg/')),
    libraries=['SDL'],
    include_dirs=['/usr/include/SDL', '/usr/local/include/SDL'],
    source="""
    #include <SDL.h>

    Uint8 _pygame_SDL_BUTTON(Uint8 X) {
        return SDL_BUTTON(X);
    }
""")

# Note: builder.build adds generated_pkg to sys.path
# to verify that the extensions compile and import
from generated_pkg._sdl import ffi, lib

print(ffi.new('Uint8 *'))
print(lib._pygame_SDL_BUTTON)
print(lib.SDL_FALSE)
print(lib.SDL_TRUE)
print(lib.SDL_GL_RED_SIZE)
print(dir(lib))

import generated_pkg
# use generated_pkg.get_extensions in setup.py to get extension modules
ext_modules = generated_pkg.get_extensions()
print("\nEXTENSIONS: %s\n" % ', '.join([e.name for e in ext_modules]))
