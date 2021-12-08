"""
Some utilities instrumenting ctypes declaration to make them more
"object-oriented friendly", mostly to facilitate testing.
"""
import ctypes


class ComparableCtStructure(ctypes.Structure):
    """ Just a wrapper for ctypes structs, but comparable and printable """

    def __eq__(self, other) -> bool:
        for field in self._fields_:
            if getattr(self, field[0]) != getattr(other, field[0]):
                return False
        return True

    def __ne__(self, other) -> bool:
        return not self.__eq__(other)

    def __repr__(self) -> str:
        fields = ('{}={}'.format(field[0], getattr(self, field[0])) for field in self._fields_)
        return '{}({})'.format(self.__class__.__name__, ', '.join(fields))


def create_comparable_array_type(size: int, element_type: 'ctypes._CData') -> 'ctypes._CData':
    """ Create instrumented ctypes array type to allow comparisons (and prints nicely)

    :param int size: size of the array
    :param ctypes._CData element_type: Ctype of the array elements
    :return: array Ctype
    """

    def repr_method(self) -> str:
        return '{}({})'.format(self.__class__.__name__, ', '.join(str(e) for e in self))

    def eq_method(self, other) -> bool:
        if len(self) != len(other):
            return False
        for a, b in zip(self, other):
            if a != b:
                return False
        return True

    def neq_method(self, other) -> bool:
        return not self.__eq__(other)

    array_type = size * element_type
    array_type.__repr__ = repr_method
    array_type.__eq__ = eq_method
    array_type.__neq__ = neq_method
    return array_type
