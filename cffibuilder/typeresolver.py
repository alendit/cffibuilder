import re

from . import error, model
from .commontypes import resolve_common_type, ordered_identifiers


_r_words = re.compile(r"\w+|\S")
# assumes space in type declaration was normalized (1 space separating all words)
_r_array_type = re.compile(r"(.*?) \[ (0?x?[0-9a-f]+u?l?)? ?\]$", re.DOTALL)


class TypeResolver(object):

    def __init__(self, declarations):
        self.declarations = declarations
        self._cache = {}

    def resolve(self, typename):
        # normalize space
        typename = ' '.join(_r_words.findall(typename))
        try:
            return self._cache[typename]
        except KeyError:
            tp = self._get_type(typename)
            self._cache[typename] = tp
        return tp

    def _get_type(self, typename, name=None):
        # pointer type
        if typename.endswith(' *'):
            if typename.startswith('const '):
                tp = self._get_type(typename[6:-2])
                const = True
            else:
                tp = self._get_type(typename[:-2])
                const = False
            return self._get_type_pointer(tp, const)

        # array type
        match = _r_array_type.match(typename)
        if match:
            if match.group(2):
                length = int(match.group(2), 0)
            else:
                length = None
            return model.ArrayType(self._get_type(match.group(1)), length)

        # parsed types
        try:
            for prefix in ('typedef', 'function'):
                try:
                    return self.declarations['%s %s' % (prefix, typename)]
                except KeyError:
                    pass
            return self.declarations[typename]
        except KeyError:
            pass

        # TODO function type

        # assume a primitive type. reduce synonyms
        # to a single chosen combination
        ident = ' '.join(ordered_identifiers(_r_words.findall(typename)))
        if ident == 'void':
            return model.void_type
        try:
            return resolve_common_type(ident)
        except error.FFIError:
            pass

        raise error.FFIError("Bad or unsupported type declaration: %r" % typename)

    def _get_type_pointer(self, type, const=False):
        if isinstance(type, model.RawFunctionType):
            return type.as_function_pointer()
        if const:
            return model.ConstPointerType(type)
        return model.PointerType(type)
