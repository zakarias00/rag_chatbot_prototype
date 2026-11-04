# `pathlib` — Object-oriented filesystem paths

Added in version 3.4.

**Source code:** [Lib/pathlib.py](https://github.com/python/cpython/tree/3.12/Lib/pathlib.py)

* * *

This module offers classes representing filesystem paths with semantics appropriate for different operating systems. Path classes are divided between [pure paths](#pure-paths), which provide purely computational operations without I/O, and [concrete paths](#concrete-paths), which inherit from pure paths but also provide I/O operations.

![Inheritance diagram showing the classes available in pathlib. The most basic class is PurePath, which has three direct subclasses: PurePosixPath, PureWindowsPath, and Path. Further to these four classes, there are two classes that use multiple inheritance: PosixPath subclasses PurePosixPath and Path, and WindowsPath subclasses PureWindowsPath and Path.](https://docs.python.org/3.12/_images/pathlib-inheritance.png)

If you’ve never used this module before or just aren’t sure which class is right for your task, [`Path`](#pathlib.Path) is most likely what you need. It instantiates a [concrete path](#concrete-paths) for the platform the code is running on.

Pure paths are useful in some special cases; for example:

1.  If you want to manipulate Windows paths on a Unix machine (or vice versa). You cannot instantiate a [`WindowsPath`](#pathlib.WindowsPath) when running on Unix, but you can instantiate [`PureWindowsPath`](#pathlib.PureWindowsPath).
    
2.  You want to make sure that your code only manipulates paths without actually accessing the OS. In this case, instantiating one of the pure classes may be useful since those simply don’t have any OS-accessing operations.
    

See also

[**PEP 428**](https://peps.python.org/pep-0428/): The pathlib module – object-oriented filesystem paths.

See also

For low-level path manipulation on strings, you can also use the [`os.path`](https://docs.python.org/3.12/library/os.path.html#module-os.path) module.

## Basic use

Importing the main class:

```python
>>> from pathlib import Path
```

Listing subdirectories:

```python
>>> p = Path('.')
>>> [x for x in p.iterdir() if x.is_dir()]
[PosixPath('.hg'), PosixPath('docs'), PosixPath('dist'),
 PosixPath('__pycache__'), PosixPath('build')]
```

Listing Python source files in this directory tree:

```python
>>> list(p.glob('**/*.py'))
[PosixPath('test_pathlib.py'), PosixPath('setup.py'),
 PosixPath('pathlib.py'), PosixPath('docs/conf.py'),
 PosixPath('build/lib/pathlib.py')]
```

Navigating inside a directory tree:

```python
>>> p = Path('/etc')
>>> q = p / 'init.d' / 'reboot'
>>> q
PosixPath('/etc/init.d/reboot')
>>> q.resolve()
PosixPath('/etc/rc.d/init.d/halt')
```

Querying path properties:

```python
>>> q.exists()
True
>>> q.is_dir()
False
```

Opening a file:

```python
>>> with q.open() as f: f.readline()
...
'#!/bin/bash\n'
```

## Pure paths

Pure path objects provide path-handling operations which don’t actually access a filesystem. There are three ways to access these classes, which we also call _flavours_:

_class_ pathlib.PurePath(_\*pathsegments_)

A generic class that represents the system’s path flavour (instantiating it creates either a [`PurePosixPath`](#pathlib.PurePosixPath) or a [`PureWindowsPath`](#pathlib.PureWindowsPath)):

```python
>>> PurePath('setup.py')      # Running on a Unix machine
PurePosixPath('setup.py')
```

Each element of _pathsegments_ can be either a string representing a path segment, or an object implementing the [`os.PathLike`](https://docs.python.org/3.12/library/os.html#os.PathLike) interface where the [`__fspath__()`](https://docs.python.org/3.12/library/os.html#os.PathLike.__fspath__) method returns a string, such as another path object:

```python
>>> PurePath('foo', 'some/path', 'bar')
PurePosixPath('foo/some/path/bar')
>>> PurePath(Path('foo'), Path('bar'))
PurePosixPath('foo/bar')
```

When _pathsegments_ is empty, the current directory is assumed:

```python
>>> PurePath()
PurePosixPath('.')
```

If a segment is an absolute path, all previous segments are ignored (like [`os.path.join()`](https://docs.python.org/3.12/library/os.path.html#os.path.join)):

```python
>>> PurePath('/etc', '/usr', 'lib64')
PurePosixPath('/usr/lib64')
>>> PureWindowsPath('c:/Windows', 'd:bar')
PureWindowsPath('d:bar')
```

On Windows, the drive is not reset when a rooted relative path segment (e.g., `r'\foo'`) is encountered:

```python
>>> PureWindowsPath('c:/Windows', '/Program Files')
PureWindowsPath('c:/Program Files')
```

Spurious slashes and single dots are collapsed, but double dots (`'..'`) and leading double slashes (`'//'`) are not, since this would change the meaning of a path for various reasons (e.g. symbolic links, UNC paths):

```python
>>> PurePath('foo//bar')
PurePosixPath('foo/bar')
>>> PurePath('//foo/bar')
PurePosixPath('//foo/bar')
>>> PurePath('foo/./bar')
PurePosixPath('foo/bar')
>>> PurePath('foo/../bar')
PurePosixPath('foo/../bar')
```

(a naïve approach would make `PurePosixPath('foo/../bar')` equivalent to `PurePosixPath('bar')`, which is wrong if `foo` is a symbolic link to another directory)

Pure path objects implement the [`os.PathLike`](https://docs.python.org/3.12/library/os.html#os.PathLike) interface, allowing them to be used anywhere the interface is accepted.

Changed in version 3.6: Added support for the [`os.PathLike`](https://docs.python.org/3.12/library/os.html#os.PathLike) interface.

_class_ pathlib.PurePosixPath(_\*pathsegments_)

A subclass of [`PurePath`](#pathlib.PurePath), this path flavour represents non-Windows filesystem paths:

```python
>>> PurePosixPath('/etc/hosts')
PurePosixPath('/etc/hosts')
```

_pathsegments_ is specified similarly to [`PurePath`](#pathlib.PurePath).

_class_ pathlib.PureWindowsPath(_\*pathsegments_)

A subclass of [`PurePath`](#pathlib.PurePath), this path flavour represents Windows filesystem paths, including [UNC paths](https://en.wikipedia.org/wiki/Path_(computing)#UNC):

```python
>>> PureWindowsPath('c:/', 'Users', 'Ximénez')
PureWindowsPath('c:/Users/Ximénez')
>>> PureWindowsPath('//server/share/file')
PureWindowsPath('//server/share/file')
```

_pathsegments_ is specified similarly to [`PurePath`](#pathlib.PurePath).

Regardless of the system you’re running on, you can instantiate all of these classes, since they don’t provide any operation that does system calls.

### General properties

Paths are immutable and [hashable](https://docs.python.org/3.12/glossary.html#term-hashable). Paths of a same flavour are comparable and orderable. These properties respect the flavour’s case-folding semantics:

```python
>>> PurePosixPath('foo') == PurePosixPath('FOO')
False
>>> PureWindowsPath('foo') == PureWindowsPath('FOO')
True
>>> PureWindowsPath('FOO') in { PureWindowsPath('foo') }
True
>>> PureWindowsPath('C:') < PureWindowsPath('d:')
True
```

Paths of a different flavour compare unequal and cannot be ordered:

```python
>>> PureWindowsPath('foo') == PurePosixPath('foo')
False
>>> PureWindowsPath('foo') < PurePosixPath('foo')
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
TypeError: '<' not supported between instances of 'PureWindowsPath' and 'PurePosixPath'
```

### Operators

The slash operator helps create child paths, like [`os.path.join()`](https://docs.python.org/3.12/library/os.path.html#os.path.join). If the argument is an absolute path, the previous path is ignored. On Windows, the drive is not reset when the argument is a rooted relative path (e.g., `r'\foo'`):

```python
>>> p = PurePath('/etc')
>>> p
PurePosixPath('/etc')
>>> p / 'init.d' / 'apache2'
PurePosixPath('/etc/init.d/apache2')
>>> q = PurePath('bin')
>>> '/usr' / q
PurePosixPath('/usr/bin')
>>> p / '/an_absolute_path'
PurePosixPath('/an_absolute_path')
>>> PureWindowsPath('c:/Windows', '/Program Files')
PureWindowsPath('c:/Program Files')
```

A path object can be used anywhere an object implementing [`os.PathLike`](https://docs.python.org/3.12/library/os.html#os.PathLike) is accepted:

```python
>>> import os
>>> p = PurePath('/etc')
>>> os.fspath(p)
'/etc'
```

The string representation of a path is the raw filesystem path itself (in native form, e.g. with backslashes under Windows), which you can pass to any function taking a file path as a string:

```python
>>> p = PurePath('/etc')
>>> str(p)
'/etc'
>>> p = PureWindowsPath('c:/Program Files')
>>> str(p)
'c:\\Program Files'
```

Similarly, calling [`bytes`](https://docs.python.org/3.12/library/stdtypes.html#bytes) on a path gives the raw filesystem path as a bytes object, as encoded by [`os.fsencode()`](https://docs.python.org/3.12/library/os.html#os.fsencode):

Note

Calling [`bytes`](https://docs.python.org/3.12/library/stdtypes.html#bytes) is only recommended under Unix. Under Windows, the unicode form is the canonical representation of filesystem paths.

### Accessing individual parts

To access the individual “parts” (components) of a path, use the following property:

PurePath.parts

A tuple giving access to the path’s various components:

```python
>>> p = PurePath('/usr/bin/python3')
>>> p.parts
('/', 'usr', 'bin', 'python3')

>>> p = PureWindowsPath('c:/Program Files/PSF')
>>> p.parts
('c:\\', 'Program Files', 'PSF')
```

(note how the drive and local root are regrouped in a single part)

### Methods and properties

Pure paths provide the following methods and properties:

PurePath.drive

A string representing the drive letter or name, if any:

```python
>>> PureWindowsPath('c:/Program Files/').drive
'c:'
>>> PureWindowsPath('/Program Files/').drive
''
>>> PurePosixPath('/etc').drive
''
```

UNC shares are also considered drives:

```python
>>> PureWindowsPath('//host/share/foo.txt').drive
'\\\\host\\share'
```

PurePath.root

A string representing the (local or global) root, if any:

```python
>>> PureWindowsPath('c:/Program Files/').root
'\\'
>>> PureWindowsPath('c:Program Files/').root
''
>>> PurePosixPath('/etc').root
'/'
```

UNC shares always have a root:

```python
>>> PureWindowsPath('//host/share').root
'\\'
```

If the path starts with more than two successive slashes, [`PurePosixPath`](#pathlib.PurePosixPath) collapses them:

```python
>>> PurePosixPath('//etc').root
'//'
>>> PurePosixPath('///etc').root
'/'
>>> PurePosixPath('////etc').root
'/'
```

Note

This behavior conforms to _The Open Group Base Specifications Issue 6_, paragraph [4.11 Pathname Resolution](https://pubs.opengroup.org/onlinepubs/009695399/basedefs/xbd_chap04.html#tag_04_11):

_“A pathname that begins with two successive slashes may be interpreted in an implementation-defined manner, although more than two leading slashes shall be treated as a single slash.”_

PurePath.anchor

The concatenation of the drive and root:

```python
>>> PureWindowsPath('c:/Program Files/').anchor
'c:\\'
>>> PureWindowsPath('c:Program Files/').anchor
'c:'
>>> PurePosixPath('/etc').anchor
'/'
>>> PureWindowsPath('//host/share').anchor
'\\\\host\\share\\'
```

PurePath.parents

An immutable sequence providing access to the logical ancestors of the path:

```python
>>> p = PureWindowsPath('c:/foo/bar/setup.py')
>>> p.parents[0]
PureWindowsPath('c:/foo/bar')
>>> p.parents[1]
PureWindowsPath('c:/foo')
>>> p.parents[2]
PureWindowsPath('c:/')
```

Changed in version 3.10: The parents sequence now supports [slices](https://docs.python.org/3.12/glossary.html#term-slice) and negative index values.

PurePath.parent

The logical parent of the path:

```python
>>> p = PurePosixPath('/a/b/c/d')
>>> p.parent
PurePosixPath('/a/b/c')
```

You cannot go past an anchor, or empty path:

```python
>>> p = PurePosixPath('/')
>>> p.parent
PurePosixPath('/')
>>> p = PurePosixPath('.')
>>> p.parent
PurePosixPath('.')
```

Note

This is a purely lexical operation, hence the following behaviour:

```python
>>> p = PurePosixPath('foo/..')
>>> p.parent
PurePosixPath('foo')
```

If you want to walk an arbitrary filesystem path upwards, it is recommended to first call [`Path.resolve()`](#pathlib.Path.resolve) so as to resolve symlinks and eliminate `".."` components.

PurePath.name

A string representing the final path component, excluding the drive and root, if any:

```python
>>> PurePosixPath('my/library/setup.py').name
'setup.py'
```

UNC drive names are not considered:

```python
>>> PureWindowsPath('//some/share/setup.py').name
'setup.py'
>>> PureWindowsPath('//some/share').name
''
```

PurePath.suffix

The file extension of the final component, if any:

```python
>>> PurePosixPath('my/library/setup.py').suffix
'.py'
>>> PurePosixPath('my/library.tar.gz').suffix
'.gz'
>>> PurePosixPath('my/library').suffix
''
```

PurePath.suffixes

A list of the path’s file extensions:

```python
>>> PurePosixPath('my/library.tar.gar').suffixes
['.tar', '.gar']
>>> PurePosixPath('my/library.tar.gz').suffixes
['.tar', '.gz']
>>> PurePosixPath('my/library').suffixes
[]
```

PurePath.stem

The final path component, without its suffix:

```python
>>> PurePosixPath('my/library.tar.gz').stem
'library.tar'
>>> PurePosixPath('my/library.tar').stem
'library'
>>> PurePosixPath('my/library').stem
'library'
```

PurePath.as\_posix()

Return a string representation of the path with forward slashes (`/`):

```python
>>> p = PureWindowsPath('c:\\windows')
>>> str(p)
'c:\\windows'
>>> p.as_posix()
'c:/windows'
```

PurePath.as\_uri()

Represent the path as a `file` URI. [`ValueError`](https://docs.python.org/3.12/library/exceptions.html#ValueError) is raised if the path isn’t absolute.

```
>>> p = PurePosixPath('/etc/passwd')
>>> p.as_uri()
'file:///etc/passwd'
>>> p = PureWindowsPath('c:/Windows')
>>> p.as_uri()
'file:///c:/Windows'
```

PurePath.is\_absolute()

Return whether the path is absolute or not. A path is considered absolute if it has both a root and (if the flavour allows) a drive:

```python
>>> PurePosixPath('/a/b').is_absolute()
True
>>> PurePosixPath('a/b').is_absolute()
False

>>> PureWindowsPath('c:/a/b').is_absolute()
True
>>> PureWindowsPath('/a/b').is_absolute()
False
>>> PureWindowsPath('c:').is_absolute()
False
>>> PureWindowsPath('//some/share').is_absolute()
True
```

PurePath.is\_relative\_to(_other_)

Return whether or not this path is relative to the _other_ path.

```
>>> p = PurePath('/etc/passwd')
>>> p.is_relative_to('/etc')
True
>>> p.is_relative_to('/usr')
False
```

This method is string-based; it neither accesses the filesystem nor treats “`..`” segments specially. The following code is equivalent:

```
>>> u = PurePath('/usr')
>>> u == p or u in p.parents
False
```

Added in version 3.9.

Deprecated since version 3.12, will be removed in version 3.14: Passing additional arguments is deprecated; if supplied, they are joined with _other_.

PurePath.is\_reserved()

With [`PureWindowsPath`](#pathlib.PureWindowsPath), return `True` if the path is considered reserved under Windows, `False` otherwise. With [`PurePosixPath`](#pathlib.PurePosixPath), `False` is always returned.

```
>>> PureWindowsPath('nul').is_reserved()
True
>>> PurePosixPath('nul').is_reserved()
False
```

File system calls on reserved paths can fail mysteriously or have unintended effects.

PurePath.joinpath(_\*pathsegments_)

Calling this method is equivalent to combining the path with each of the given _pathsegments_ in turn:

```python
>>> PurePosixPath('/etc').joinpath('passwd')
PurePosixPath('/etc/passwd')
>>> PurePosixPath('/etc').joinpath(PurePosixPath('passwd'))
PurePosixPath('/etc/passwd')
>>> PurePosixPath('/etc').joinpath('init.d', 'apache2')
PurePosixPath('/etc/init.d/apache2')
>>> PureWindowsPath('c:').joinpath('/Program Files')
PureWindowsPath('c:/Program Files')
```

PurePath.match(_pattern_, _\*_, _case\_sensitive\=None_)

Match this path against the provided glob-style pattern. Return `True` if matching is successful, `False` otherwise.

If _pattern_ is relative, the path can be either relative or absolute, and matching is done from the right:

```python
>>> PurePath('a/b.py').match('*.py')
True
>>> PurePath('/a/b/c.py').match('b/*.py')
True
>>> PurePath('/a/b/c.py').match('a/*.py')
False
```

If _pattern_ is absolute, the path must be absolute, and the whole path must match:

```python
>>> PurePath('/a.py').match('/*.py')
True
>>> PurePath('a/b.py').match('/*.py')
False
```

The _pattern_ may be another path object; this speeds up matching the same pattern against multiple files:

```python
>>> pattern = PurePath('*.py')
>>> PurePath('a/b.py').match(pattern)
True
```

Note

The recursive wildcard “`**`” isn’t supported by this method (it acts like non-recursive “`*`”.)

Changed in version 3.12: Accepts an object implementing the [`os.PathLike`](https://docs.python.org/3.12/library/os.html#os.PathLike) interface.

As with other methods, case-sensitivity follows platform defaults:

```python
>>> PurePosixPath('b.py').match('*.PY')
False
>>> PureWindowsPath('b.py').match('*.PY')
True
```

Set _case\_sensitive_ to `True` or `False` to override this behaviour.

Changed in version 3.12: The _case\_sensitive_ parameter was added.

PurePath.relative\_to(_other_, _walk\_up\=False_)

Compute a version of this path relative to the path represented by _other_. If it’s impossible, [`ValueError`](https://docs.python.org/3.12/library/exceptions.html#ValueError) is raised:

```python
>>> p = PurePosixPath('/etc/passwd')
>>> p.relative_to('/')
PurePosixPath('etc/passwd')
>>> p.relative_to('/etc')
PurePosixPath('passwd')
>>> p.relative_to('/usr')
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
  File "pathlib.py", line 941, in relative_to
    raise ValueError(error_message.format(str(self), str(formatted)))
ValueError: '/etc/passwd' is not in the subpath of '/usr' OR one path is relative and the other is absolute.
```

When _walk\_up_ is false (the default), the path must start with _other_. When the argument is true, `..` entries may be added to form the relative path. In all other cases, such as the paths referencing different drives, [`ValueError`](https://docs.python.org/3.12/library/exceptions.html#ValueError) is raised.:

```python
>>> p.relative_to('/usr', walk_up=True)
PurePosixPath('../etc/passwd')
>>> p.relative_to('foo', walk_up=True)
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
  File "pathlib.py", line 941, in relative_to
    raise ValueError(error_message.format(str(self), str(formatted)))
ValueError: '/etc/passwd' is not on the same drive as 'foo' OR one path is relative and the other is absolute.
```

Warning

This function is part of [`PurePath`](#pathlib.PurePath) and works with strings. It does not check or access the underlying file structure. This can impact the _walk\_up_ option as it assumes that no symlinks are present in the path; call [`resolve()`](#pathlib.Path.resolve) first if necessary to resolve symlinks.

Changed in version 3.12: The _walk\_up_ parameter was added (old behavior is the same as `walk_up=False`).

Deprecated since version 3.12, will be removed in version 3.14: Passing additional positional arguments is deprecated; if supplied, they are joined with _other_.

PurePath.with\_name(_name_)

Return a new path with the [`name`](#pathlib.PurePath.name) changed. If the original path doesn’t have a name, ValueError is raised:

```python
>>> p = PureWindowsPath('c:/Downloads/pathlib.tar.gz')
>>> p.with_name('setup.py')
PureWindowsPath('c:/Downloads/setup.py')
>>> p = PureWindowsPath('c:/')
>>> p.with_name('setup.py')
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
  File "/home/antoine/cpython/default/Lib/pathlib.py", line 751, in with_name
    raise ValueError("%r has an empty name" % (self,))
ValueError: PureWindowsPath('c:/') has an empty name
```

PurePath.with\_stem(_stem_)

Return a new path with the [`stem`](#pathlib.PurePath.stem) changed. If the original path doesn’t have a name, ValueError is raised:

```python
>>> p = PureWindowsPath('c:/Downloads/draft.txt')
>>> p.with_stem('final')
PureWindowsPath('c:/Downloads/final.txt')
>>> p = PureWindowsPath('c:/Downloads/pathlib.tar.gz')
>>> p.with_stem('lib')
PureWindowsPath('c:/Downloads/lib.gz')
>>> p = PureWindowsPath('c:/')
>>> p.with_stem('')
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
  File "/home/antoine/cpython/default/Lib/pathlib.py", line 861, in with_stem
    return self.with_name(stem + self.suffix)
  File "/home/antoine/cpython/default/Lib/pathlib.py", line 851, in with_name
    raise ValueError("%r has an empty name" % (self,))
ValueError: PureWindowsPath('c:/') has an empty name
```

Added in version 3.9.

PurePath.with\_suffix(_suffix_)

Return a new path with the [`suffix`](#pathlib.PurePath.suffix) changed. If the original path doesn’t have a suffix, the new _suffix_ is appended instead. If the _suffix_ is an empty string, the original suffix is removed:

```python
>>> p = PureWindowsPath('c:/Downloads/pathlib.tar.gz')
>>> p.with_suffix('.bz2')
PureWindowsPath('c:/Downloads/pathlib.tar.bz2')
>>> p = PureWindowsPath('README')
>>> p.with_suffix('.txt')
PureWindowsPath('README.txt')
>>> p = PureWindowsPath('README.txt')
>>> p.with_suffix('')
PureWindowsPath('README')
```

PurePath.with\_segments(_\*pathsegments_)

Create a new path object of the same type by combining the given _pathsegments_. This method is called whenever a derivative path is created, such as from [`parent`](#pathlib.PurePath.parent) and [`relative_to()`](#pathlib.PurePath.relative_to). Subclasses may override this method to pass information to derivative paths, for example:

```python
from pathlib import PurePosixPath

class MyPath(PurePosixPath):
    def __init__(self, *pathsegments, session_id):
        super().__init__(*pathsegments)
        self.session_id = session_id

    def with_segments(self, *pathsegments):
        return type(self)(*pathsegments, session_id=self.session_id)

etc = MyPath('/etc', session_id=42)
hosts = etc / 'hosts'
print(hosts.session_id)  # 42
```

Added in version 3.12.

## Concrete paths

Concrete paths are subclasses of the pure path classes. In addition to operations provided by the latter, they also provide methods to do system calls on path objects. There are three ways to instantiate concrete paths:

_class_ pathlib.Path(_\*pathsegments_)

A subclass of [`PurePath`](#pathlib.PurePath), this class represents concrete paths of the system’s path flavour (instantiating it creates either a [`PosixPath`](#pathlib.PosixPath) or a [`WindowsPath`](#pathlib.WindowsPath)):

```python
>>> Path('setup.py')
PosixPath('setup.py')
```

_pathsegments_ is specified similarly to [`PurePath`](#pathlib.PurePath).

_class_ pathlib.PosixPath(_\*pathsegments_)

A subclass of [`Path`](#pathlib.Path) and [`PurePosixPath`](#pathlib.PurePosixPath), this class represents concrete non-Windows filesystem paths:

```python
>>> PosixPath('/etc/hosts')
PosixPath('/etc/hosts')
```

_pathsegments_ is specified similarly to [`PurePath`](#pathlib.PurePath).

_class_ pathlib.WindowsPath(_\*pathsegments_)

A subclass of [`Path`](#pathlib.Path) and [`PureWindowsPath`](#pathlib.PureWindowsPath), this class represents concrete Windows filesystem paths:

```python
>>> WindowsPath('c:/', 'Users', 'Ximénez')
WindowsPath('c:/Users/Ximénez')
```

_pathsegments_ is specified similarly to [`PurePath`](#pathlib.PurePath).

You can only instantiate the class flavour that corresponds to your system (allowing system calls on non-compatible path flavours could lead to bugs or failures in your application):

```python
>>> import os
>>> os.name
'posix'
>>> Path('setup.py')
PosixPath('setup.py')
>>> PosixPath('setup.py')
PosixPath('setup.py')
>>> WindowsPath('setup.py')
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
  File "pathlib.py", line 798, in __new__
    % (cls.__name__,))
NotImplementedError: cannot instantiate 'WindowsPath' on your system
```

Some concrete path methods can raise an [`OSError`](https://docs.python.org/3.12/library/exceptions.html#OSError) if a system call fails (for example because the path doesn’t exist).

### Expanding and resolving paths

_classmethod_ Path.home()

Return a new path object representing the user’s home directory (as returned by [`os.path.expanduser()`](https://docs.python.org/3.12/library/os.path.html#os.path.expanduser) with `~` construct). If the home directory can’t be resolved, [`RuntimeError`](https://docs.python.org/3.12/library/exceptions.html#RuntimeError) is raised.

```python
>>> Path.home()
PosixPath('/home/antoine')
```

Added in version 3.5.

Path.expanduser()

Return a new path with expanded `~` and `~user` constructs, as returned by [`os.path.expanduser()`](https://docs.python.org/3.12/library/os.path.html#os.path.expanduser). If a home directory can’t be resolved, [`RuntimeError`](https://docs.python.org/3.12/library/exceptions.html#RuntimeError) is raised.

```python
>>> p = PosixPath('~/films/Monty Python')
>>> p.expanduser()
PosixPath('/home/eric/films/Monty Python')
```

Added in version 3.5.

_classmethod_ Path.cwd()

Return a new path object representing the current directory (as returned by [`os.getcwd()`](https://docs.python.org/3.12/library/os.html#os.getcwd)):

```python
>>> Path.cwd()
PosixPath('/home/antoine/pathlib')
```

Path.absolute()

Make the path absolute, without normalization or resolving symlinks. Returns a new path object:

```python
>>> p = Path('tests')
>>> p
PosixPath('tests')
>>> p.absolute()
PosixPath('/home/antoine/pathlib/tests')
```

Path.resolve(_strict\=False_)

Make the path absolute, resolving any symlinks. A new path object is returned:

```python
>>> p = Path()
>>> p
PosixPath('.')
>>> p.resolve()
PosixPath('/home/antoine/pathlib')
```

“`..`” components are also eliminated (this is the only method to do so):

```python
>>> p = Path('docs/../setup.py')
>>> p.resolve()
PosixPath('/home/antoine/pathlib/setup.py')
```

If the path doesn’t exist and _strict_ is `True`, [`FileNotFoundError`](https://docs.python.org/3.12/library/exceptions.html#FileNotFoundError) is raised. If _strict_ is `False`, the path is resolved as far as possible and any remainder is appended without checking whether it exists. If an infinite loop is encountered along the resolution path, [`RuntimeError`](https://docs.python.org/3.12/library/exceptions.html#RuntimeError) is raised.

Changed in version 3.6: The _strict_ parameter was added (pre-3.6 behavior is strict).

Path.readlink()

Return the path to which the symbolic link points (as returned by [`os.readlink()`](https://docs.python.org/3.12/library/os.html#os.readlink)):

```python
>>> p = Path('mylink')
>>> p.symlink_to('setup.py')
>>> p.readlink()
PosixPath('setup.py')
```

Added in version 3.9.

### Querying file type and status

Changed in version 3.8: [`exists()`](#pathlib.Path.exists), [`is_dir()`](#pathlib.Path.is_dir), [`is_file()`](#pathlib.Path.is_file), [`is_mount()`](#pathlib.Path.is_mount), [`is_symlink()`](#pathlib.Path.is_symlink), [`is_block_device()`](#pathlib.Path.is_block_device), [`is_char_device()`](#pathlib.Path.is_char_device), [`is_fifo()`](#pathlib.Path.is_fifo), [`is_socket()`](#pathlib.Path.is_socket) now return `False` instead of raising an exception for paths that contain characters unrepresentable at the OS level.

Path.stat(_\*_, _follow\_symlinks\=True_)

Return an [`os.stat_result`](https://docs.python.org/3.12/library/os.html#os.stat_result) object containing information about this path, like [`os.stat()`](https://docs.python.org/3.12/library/os.html#os.stat). The result is looked up at each call to this method.

This method normally follows symlinks; to stat a symlink add the argument `follow_symlinks=False`, or use [`lstat()`](#pathlib.Path.lstat).

```python
>>> p = Path('setup.py')
>>> p.stat().st_size
956
>>> p.stat().st_mtime
1327883547.852554
```

Changed in version 3.10: The _follow\_symlinks_ parameter was added.

Path.lstat()

Like [`Path.stat()`](#pathlib.Path.stat) but, if the path points to a symbolic link, return the symbolic link’s information rather than its target’s.

Path.exists(_\*_, _follow\_symlinks\=True_)

Return `True` if the path points to an existing file or directory.

This method normally follows symlinks; to check if a symlink exists, add the argument `follow_symlinks=False`.

```python
>>> Path('.').exists()
True
>>> Path('setup.py').exists()
True
>>> Path('/etc').exists()
True
>>> Path('nonexistentfile').exists()
False
```

Changed in version 3.12: The _follow\_symlinks_ parameter was added.

Path.is\_file()

Return `True` if the path points to a regular file (or a symbolic link pointing to a regular file), `False` if it points to another kind of file.

`False` is also returned if the path doesn’t exist or is a broken symlink; other errors (such as permission errors) are propagated.

Path.is\_dir()

Return `True` if the path points to a directory (or a symbolic link pointing to a directory), `False` if it points to another kind of file.

`False` is also returned if the path doesn’t exist or is a broken symlink; other errors (such as permission errors) are propagated.

Path.is\_symlink()

Return `True` if the path points to a symbolic link, `False` otherwise.

`False` is also returned if the path doesn’t exist; other errors (such as permission errors) are propagated.

Path.is\_junction()

Return `True` if the path points to a junction, and `False` for any other type of file. Currently only Windows supports junctions.

Added in version 3.12.

Path.is\_mount()

Return `True` if the path is a _mount point_: a point in a file system where a different file system has been mounted. On POSIX, the function checks whether _path_’s parent, `path/..`, is on a different device than _path_, or whether `path/..` and _path_ point to the same i-node on the same device — this should detect mount points for all Unix and POSIX variants. On Windows, a mount point is considered to be a drive letter root (e.g. `c:\`), a UNC share (e.g. `\\server\share`), or a mounted filesystem directory.

Added in version 3.7.

Changed in version 3.12: Windows support was added.

Path.is\_socket()

Return `True` if the path points to a Unix socket (or a symbolic link pointing to a Unix socket), `False` if it points to another kind of file.

`False` is also returned if the path doesn’t exist or is a broken symlink; other errors (such as permission errors) are propagated.

Path.is\_fifo()

Return `True` if the path points to a FIFO (or a symbolic link pointing to a FIFO), `False` if it points to another kind of file.

`False` is also returned if the path doesn’t exist or is a broken symlink; other errors (such as permission errors) are propagated.

Path.is\_block\_device()

Return `True` if the path points to a block device (or a symbolic link pointing to a block device), `False` if it points to another kind of file.

`False` is also returned if the path doesn’t exist or is a broken symlink; other errors (such as permission errors) are propagated.

Path.is\_char\_device()

Return `True` if the path points to a character device (or a symbolic link pointing to a character device), `False` if it points to another kind of file.

`False` is also returned if the path doesn’t exist or is a broken symlink; other errors (such as permission errors) are propagated.

Path.samefile(_other\_path_)

Return whether this path points to the same file as _other\_path_, which can be either a Path object, or a string. The semantics are similar to [`os.path.samefile()`](https://docs.python.org/3.12/library/os.path.html#os.path.samefile) and [`os.path.samestat()`](https://docs.python.org/3.12/library/os.path.html#os.path.samestat).

An [`OSError`](https://docs.python.org/3.12/library/exceptions.html#OSError) can be raised if either file cannot be accessed for some reason.

```python
>>> p = Path('spam')
>>> q = Path('eggs')
>>> p.samefile(q)
False
>>> p.samefile('spam')
True
```

Added in version 3.5.

### Reading and writing files

Path.open(_mode\='r'_, _buffering\=\-1_, _encoding\=None_, _errors\=None_, _newline\=None_)

Open the file pointed to by the path, like the built-in [`open()`](https://docs.python.org/3.12/library/functions.html#open) function does:

```python
>>> p = Path('setup.py')
>>> with p.open() as f:
...     f.readline()
...
'#!/usr/bin/env python3\n'
```

Path.read\_text(_encoding\=None_, _errors\=None_)

Return the decoded contents of the pointed-to file as a string:

```python
>>> p = Path('my_text_file')
>>> p.write_text('Text file contents')
18
>>> p.read_text()
'Text file contents'
```

The file is opened and then closed. The optional parameters have the same meaning as in [`open()`](https://docs.python.org/3.12/library/functions.html#open).

Added in version 3.5.

Path.read\_bytes()

Return the binary contents of the pointed-to file as a bytes object:

```python
>>> p = Path('my_binary_file')
>>> p.write_bytes(b'Binary file contents')
20
>>> p.read_bytes()
b'Binary file contents'
```

Added in version 3.5.

Path.write\_text(_data_, _encoding\=None_, _errors\=None_, _newline\=None_)

Open the file pointed to in text mode, write _data_ to it, and close the file:

```python
>>> p = Path('my_text_file')
>>> p.write_text('Text file contents')
18
>>> p.read_text()
'Text file contents'
```

An existing file of the same name is overwritten. The optional parameters have the same meaning as in [`open()`](https://docs.python.org/3.12/library/functions.html#open).

Added in version 3.5.

Changed in version 3.10: The _newline_ parameter was added.

Path.write\_bytes(_data_)

Open the file pointed to in bytes mode, write _data_ to it, and close the file:

```python
>>> p = Path('my_binary_file')
>>> p.write_bytes(b'Binary file contents')
20
>>> p.read_bytes()
b'Binary file contents'
```

An existing file of the same name is overwritten.

Added in version 3.5.

### Reading directories

Path.iterdir()

When the path points to a directory, yield path objects of the directory contents:

```python
>>> p = Path('docs')
>>> for child in p.iterdir(): child
...
PosixPath('docs/conf.py')
PosixPath('docs/_templates')
PosixPath('docs/make.bat')
PosixPath('docs/index.rst')
PosixPath('docs/_build')
PosixPath('docs/_static')
PosixPath('docs/Makefile')
```

The children are yielded in arbitrary order, and the special entries `'.'` and `'..'` are not included. If a file is removed from or added to the directory after creating the iterator, it is unspecified whether a path object for that file is included.

If the path is not a directory or otherwise inaccessible, [`OSError`](https://docs.python.org/3.12/library/exceptions.html#OSError) is raised.

Path.glob(_pattern_, _\*_, _case\_sensitive\=None_)

Glob the given relative _pattern_ in the directory represented by this path, yielding all matching files (of any kind):

```python
>>> sorted(Path('.').glob('*.py'))
[PosixPath('pathlib.py'), PosixPath('setup.py'), PosixPath('test_pathlib.py')]
>>> sorted(Path('.').glob('*/*.py'))
[PosixPath('docs/conf.py')]
```

Patterns are the same as for [`fnmatch`](https://docs.python.org/3.12/library/fnmatch.html#module-fnmatch), with the addition of “`**`” which means “this directory and all subdirectories, recursively”. In other words, it enables recursive globbing:

```python
>>> sorted(Path('.').glob('**/*.py'))
[PosixPath('build/lib/pathlib.py'),
 PosixPath('docs/conf.py'),
 PosixPath('pathlib.py'),
 PosixPath('setup.py'),
 PosixPath('test_pathlib.py')]
```

This method calls [`Path.is_dir()`](#pathlib.Path.is_dir) on the top-level directory and propagates any [`OSError`](https://docs.python.org/3.12/library/exceptions.html#OSError) exception that is raised. Subsequent [`OSError`](https://docs.python.org/3.12/library/exceptions.html#OSError) exceptions from scanning directories are suppressed.

By default, or when the _case\_sensitive_ keyword-only argument is set to `None`, this method matches paths using platform-specific casing rules: typically, case-sensitive on POSIX, and case-insensitive on Windows. Set _case\_sensitive_ to `True` or `False` to override this behaviour.

Note

Using the “`**`” pattern in large directory trees may consume an inordinate amount of time.

Raises an [auditing event](https://docs.python.org/3.12/library/sys.html#auditing) `pathlib.Path.glob` with arguments `self`, `pattern`.

Changed in version 3.11: Return only directories if _pattern_ ends with a pathname components separator ([`sep`](https://docs.python.org/3.12/library/os.html#os.sep) or [`altsep`](https://docs.python.org/3.12/library/os.html#os.altsep)).

Changed in version 3.12: The _case\_sensitive_ parameter was added.

Path.rglob(_pattern_, _\*_, _case\_sensitive\=None_)

Glob the given relative _pattern_ recursively. This is like calling [`Path.glob()`](#pathlib.Path.glob) with “`**/`” added in front of the _pattern_, where _patterns_ are the same as for [`fnmatch`](https://docs.python.org/3.12/library/fnmatch.html#module-fnmatch):

```python
>>> sorted(Path().rglob("*.py"))
[PosixPath('build/lib/pathlib.py'),
 PosixPath('docs/conf.py'),
 PosixPath('pathlib.py'),
 PosixPath('setup.py'),
 PosixPath('test_pathlib.py')]
```

By default, or when the _case\_sensitive_ keyword-only argument is set to `None`, this method matches paths using platform-specific casing rules: typically, case-sensitive on POSIX, and case-insensitive on Windows. Set _case\_sensitive_ to `True` or `False` to override this behaviour.

Raises an [auditing event](https://docs.python.org/3.12/library/sys.html#auditing) `pathlib.Path.rglob` with arguments `self`, `pattern`.

Changed in version 3.11: Return only directories if _pattern_ ends with a pathname components separator ([`sep`](https://docs.python.org/3.12/library/os.html#os.sep) or [`altsep`](https://docs.python.org/3.12/library/os.html#os.altsep)).

Changed in version 3.12: The _case\_sensitive_ parameter was added.

Path.walk(_top\_down\=True_, _on\_error\=None_, _follow\_symlinks\=False_)

Generate the file names in a directory tree by walking the tree either top-down or bottom-up.

For each directory in the directory tree rooted at _self_ (including _self_ but excluding ‘.’ and ‘..’), the method yields a 3-tuple of `(dirpath, dirnames, filenames)`.

_dirpath_ is a [`Path`](#pathlib.Path) to the directory currently being walked, _dirnames_ is a list of strings for the names of subdirectories in _dirpath_ (excluding `'.'` and `'..'`), and _filenames_ is a list of strings for the names of the non-directory files in _dirpath_. To get a full path (which begins with _self_) to a file or directory in _dirpath_, do `dirpath / name`. Whether or not the lists are sorted is file system-dependent.

If the optional argument _top\_down_ is true (which is the default), the triple for a directory is generated before the triples for any of its subdirectories (directories are walked top-down). If _top\_down_ is false, the triple for a directory is generated after the triples for all of its subdirectories (directories are walked bottom-up). No matter the value of _top\_down_, the list of subdirectories is retrieved before the triples for the directory and its subdirectories are walked.

When _top\_down_ is true, the caller can modify the _dirnames_ list in-place (for example, using [`del`](https://docs.python.org/3.12/reference/simple_stmts.html#del) or slice assignment), and [`Path.walk()`](#pathlib.Path.walk) will only recurse into the subdirectories whose names remain in _dirnames_. This can be used to prune the search, or to impose a specific order of visiting, or even to inform [`Path.walk()`](#pathlib.Path.walk) about directories the caller creates or renames before it resumes [`Path.walk()`](#pathlib.Path.walk) again. Modifying _dirnames_ when _top\_down_ is false has no effect on the behavior of [`Path.walk()`](#pathlib.Path.walk) since the directories in _dirnames_ have already been generated by the time _dirnames_ is yielded to the caller.

By default, errors from [`os.scandir()`](https://docs.python.org/3.12/library/os.html#os.scandir) are ignored. If the optional argument _on\_error_ is specified, it should be a callable; it will be called with one argument, an [`OSError`](https://docs.python.org/3.12/library/exceptions.html#OSError) instance. The callable can handle the error to continue the walk or re-raise it to stop the walk. Note that the filename is available as the `filename` attribute of the exception object.

By default, [`Path.walk()`](#pathlib.Path.walk) does not follow symbolic links, and instead adds them to the _filenames_ list. Set _follow\_symlinks_ to true to resolve symlinks and place them in _dirnames_ and _filenames_ as appropriate for their targets, and consequently visit directories pointed to by symlinks (where supported).

Note

Be aware that setting _follow\_symlinks_ to true can lead to infinite recursion if a link points to a parent directory of itself. [`Path.walk()`](#pathlib.Path.walk) does not keep track of the directories it has already visited.

Note

[`Path.walk()`](#pathlib.Path.walk) assumes the directories it walks are not modified during execution. For example, if a directory from _dirnames_ has been replaced with a symlink and _follow\_symlinks_ is false, [`Path.walk()`](#pathlib.Path.walk) will still try to descend into it. To prevent such behavior, remove directories from _dirnames_ as appropriate.

Note

Unlike [`os.walk()`](https://docs.python.org/3.12/library/os.html#os.walk), [`Path.walk()`](#pathlib.Path.walk) lists symlinks to directories in _filenames_ if _follow\_symlinks_ is false.

This example displays the number of bytes used by all files in each directory, while ignoring `__pycache__` directories:

```python
from pathlib import Path
for root, dirs, files in Path("cpython/Lib/concurrent").walk(on_error=print):
  print(
      root,
      "consumes",
      sum((root / file).stat().st_size for file in files),
      "bytes in",
      len(files),
      "non-directory files"
  )
  if '__pycache__' in dirs:
        dirs.remove('__pycache__')
```

This next example is a simple implementation of [`shutil.rmtree()`](https://docs.python.org/3.12/library/shutil.html#shutil.rmtree). Walking the tree bottom-up is essential as [`rmdir()`](#pathlib.Path.rmdir) doesn’t allow deleting a directory before it is empty:

```python
# Delete everything reachable from the directory "top".
# CAUTION:  This is dangerous! For example, if top == Path('/'),
# it could delete all of your files.
for root, dirs, files in top.walk(top_down=False):
    for name in files:
        (root / name).unlink()
    for name in dirs:
        (root / name).rmdir()
```

Added in version 3.12.

### Creating files and directories

Path.touch(_mode\=0o666_, _exist\_ok\=True_)

Create a file at this given path. If _mode_ is given, it is combined with the process’s `umask` value to determine the file mode and access flags. If the file already exists, the function succeeds when _exist\_ok_ is true (and its modification time is updated to the current time), otherwise [`FileExistsError`](https://docs.python.org/3.12/library/exceptions.html#FileExistsError) is raised.

See also

The [`open()`](#pathlib.Path.open), [`write_text()`](#pathlib.Path.write_text) and [`write_bytes()`](#pathlib.Path.write_bytes) methods are often used to create files.

Path.mkdir(_mode\=0o777_, _parents\=False_, _exist\_ok\=False_)

Create a new directory at this given path. If _mode_ is given, it is combined with the process’s `umask` value to determine the file mode and access flags. If the path already exists, [`FileExistsError`](https://docs.python.org/3.12/library/exceptions.html#FileExistsError) is raised.

If _parents_ is true, any missing parents of this path are created as needed; they are created with the default permissions without taking _mode_ into account (mimicking the POSIX `mkdir -p` command).

If _parents_ is false (the default), a missing parent raises [`FileNotFoundError`](https://docs.python.org/3.12/library/exceptions.html#FileNotFoundError).

If _exist\_ok_ is false (the default), [`FileExistsError`](https://docs.python.org/3.12/library/exceptions.html#FileExistsError) is raised if the target directory already exists.

If _exist\_ok_ is true, [`FileExistsError`](https://docs.python.org/3.12/library/exceptions.html#FileExistsError) will not be raised unless the given path already exists in the file system and is not a directory (same behavior as the POSIX `mkdir -p` command).

Changed in version 3.5: The _exist\_ok_ parameter was added.

Path.symlink\_to(_target_, _target\_is\_directory\=False_)

Make this path a symbolic link pointing to _target_.

On Windows, a symlink represents either a file or a directory, and does not morph to the target dynamically. If the target is present, the type of the symlink will be created to match. Otherwise, the symlink will be created as a directory if _target\_is\_directory_ is true or a file symlink (the default) otherwise. On non-Windows platforms, _target\_is\_directory_ is ignored.

```python
>>> p = Path('mylink')
>>> p.symlink_to('setup.py')
>>> p.resolve()
PosixPath('/home/antoine/pathlib/setup.py')
>>> p.stat().st_size
956
>>> p.lstat().st_size
8
```

Note

The order of arguments (link, target) is the reverse of [`os.symlink()`](https://docs.python.org/3.12/library/os.html#os.symlink)’s.

Path.hardlink\_to(_target_)

Make this path a hard link to the same file as _target_.

Note

The order of arguments (link, target) is the reverse of [`os.link()`](https://docs.python.org/3.12/library/os.html#os.link)’s.

Added in version 3.10.

### Renaming and deleting

Path.rename(_target_)

Rename this file or directory to the given _target_, and return a new `Path` instance pointing to _target_. On Unix, if _target_ exists and is a file, it will be replaced silently if the user has permission. On Windows, if _target_ exists, [`FileExistsError`](https://docs.python.org/3.12/library/exceptions.html#FileExistsError) will be raised. _target_ can be either a string or another path object:

```python
>>> p = Path('foo')
>>> p.open('w').write('some text')
9
>>> target = Path('bar')
>>> p.rename(target)
PosixPath('bar')
>>> target.open().read()
'some text'
```

The target path may be absolute or relative. Relative paths are interpreted relative to the current working directory, _not_ the directory of the `Path` object.

It is implemented in terms of [`os.rename()`](https://docs.python.org/3.12/library/os.html#os.rename) and gives the same guarantees.

Changed in version 3.8: Added return value, return the new `Path` instance.

Path.replace(_target_)

Rename this file or directory to the given _target_, and return a new `Path` instance pointing to _target_. If _target_ points to an existing file or empty directory, it will be unconditionally replaced.

The target path may be absolute or relative. Relative paths are interpreted relative to the current working directory, _not_ the directory of the `Path` object.

Changed in version 3.8: Added return value, return the new `Path` instance.

Path.unlink(_missing\_ok\=False_)

Remove this file or symbolic link. If the path points to a directory, use [`Path.rmdir()`](#pathlib.Path.rmdir) instead.

If _missing\_ok_ is false (the default), [`FileNotFoundError`](https://docs.python.org/3.12/library/exceptions.html#FileNotFoundError) is raised if the path does not exist.

If _missing\_ok_ is true, [`FileNotFoundError`](https://docs.python.org/3.12/library/exceptions.html#FileNotFoundError) exceptions will be ignored (same behavior as the POSIX `rm -f` command).

Changed in version 3.8: The _missing\_ok_ parameter was added.

Path.rmdir()

Remove this directory. The directory must be empty.

### Permissions and ownership

Path.owner()

Return the name of the user owning the file. [`KeyError`](https://docs.python.org/3.12/library/exceptions.html#KeyError) is raised if the file’s user identifier (UID) isn’t found in the system database.

Path.group()

Return the name of the group owning the file. [`KeyError`](https://docs.python.org/3.12/library/exceptions.html#KeyError) is raised if the file’s group identifier (GID) isn’t found in the system database.

Path.chmod(_mode_, _\*_, _follow\_symlinks\=True_)

Change the file mode and permissions, like [`os.chmod()`](https://docs.python.org/3.12/library/os.html#os.chmod).

This method normally follows symlinks. Some Unix flavours support changing permissions on the symlink itself; on these platforms you may add the argument `follow_symlinks=False`, or use [`lchmod()`](#pathlib.Path.lchmod).

```python
>>> p = Path('setup.py')
>>> p.stat().st_mode
33277
>>> p.chmod(0o444)
>>> p.stat().st_mode
33060
```

Changed in version 3.10: The _follow\_symlinks_ parameter was added.

Path.lchmod(_mode_)

Like [`Path.chmod()`](#pathlib.Path.chmod) but, if the path points to a symbolic link, the symbolic link’s mode is changed rather than its target’s.

## Correspondence to tools in the [`os`](https://docs.python.org/3.12/library/os.html#module-os) module

Below is a table mapping various [`os`](https://docs.python.org/3.12/library/os.html#module-os) functions to their corresponding [`PurePath`](#pathlib.PurePath)/[`Path`](#pathlib.Path) equivalent.