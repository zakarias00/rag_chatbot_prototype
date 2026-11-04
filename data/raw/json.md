# `json` — JSON encoding and decoding

**Source code:** [Lib/json/\_\_init\_\_.py](https://github.com/python/cpython/tree/3.12/Lib/json/__init__.py)

* * *

[JSON (JavaScript Object Notation)](https://json.org/), specified by [**RFC 7159**](https://datatracker.ietf.org/doc/html/rfc7159.html) (which obsoletes [**RFC 4627**](https://datatracker.ietf.org/doc/html/rfc4627.html)) and by [ECMA-404](https://ecma-international.org/publications-and-standards/standards/ecma-404/), is a lightweight data interchange format inspired by [JavaScript](https://en.wikipedia.org/wiki/JavaScript) object literal syntax (although it is not a strict subset of JavaScript [\[1\]](#rfc-errata) ).

Warning

Be cautious when parsing JSON data from untrusted sources. A malicious JSON string may cause the decoder to consume considerable CPU and memory resources. Limiting the size of data to be parsed is recommended.

[`json`](#module-json) exposes an API familiar to users of the standard library [`marshal`](https://docs.python.org/3.12/library/marshal.html#module-marshal) and [`pickle`](https://docs.python.org/3.12/library/pickle.html#module-pickle) modules.

Encoding basic Python object hierarchies:

```python
>>> import json
>>> json.dumps(['foo', {'bar': ('baz', None, 1.0, 2)}])
'["foo", {"bar": ["baz", null, 1.0, 2]}]'
>>> print(json.dumps("\"foo\bar"))
"\"foo\bar"
>>> print(json.dumps('\u1234'))
"\u1234"
>>> print(json.dumps('\\'))
"\\"
>>> print(json.dumps({"c": 0, "b": 0, "a": 0}, sort_keys=True))
{"a": 0, "b": 0, "c": 0}
>>> from io import StringIO
>>> io = StringIO()
>>> json.dump(['streaming API'], io)
>>> io.getvalue()
'["streaming API"]'
```

Compact encoding:

```python
>>> import json
>>> json.dumps([1, 2, 3, {'4': 5, '6': 7}], separators=(',', ':'))
'[1,2,3,{"4":5,"6":7}]'
```

Pretty printing:

```python
>>> import json
>>> print(json.dumps({'4': 5, '6': 7}, sort_keys=True, indent=4))
{
    "4": 5,
    "6": 7
}
```

Decoding JSON:

```python
>>> import json
>>> json.loads('["foo", {"bar":["baz", null, 1.0, 2]}]')
['foo', {'bar': ['baz', None, 1.0, 2]}]
>>> json.loads('"\\"foo\\bar"')
'"foo\x08ar'
>>> from io import StringIO
>>> io = StringIO('["streaming API"]')
>>> json.load(io)
['streaming API']
```

Specializing JSON object decoding:

```python
>>> import json
>>> def as_complex(dct):
...     if '__complex__' in dct:
...         return complex(dct['real'], dct['imag'])
...     return dct
...
>>> json.loads('{"__complex__": true, "real": 1, "imag": 2}',
...     object_hook=as_complex)
(1+2j)
>>> import decimal
>>> json.loads('1.1', parse_float=decimal.Decimal)
Decimal('1.1')
```

Extending [`JSONEncoder`](#json.JSONEncoder):

```python
>>> import json
>>> class ComplexEncoder(json.JSONEncoder):
...     def default(self, obj):
...         if isinstance(obj, complex):
...             return [obj.real, obj.imag]
...         # Let the base class default method raise the TypeError
...         return super().default(obj)
...
>>> json.dumps(2 + 1j, cls=ComplexEncoder)
'[2.0, 1.0]'
>>> ComplexEncoder().encode(2 + 1j)
'[2.0, 1.0]'
>>> list(ComplexEncoder().iterencode(2 + 1j))
['[2.0', ', 1.0', ']']
```

Using [`json.tool`](#module-json.tool) from the shell to validate and pretty-print:

```bash
$ echo '{"json":"obj"}' | python -m json.tool
{
    "json": "obj"
}
$ echo '{1.2:3.4}' | python -m json.tool
Expecting property name enclosed in double quotes: line 1 column 2 (char 1)
```

See [Command Line Interface](#json-commandline) for detailed documentation.

Note

JSON is a subset of [YAML](https://yaml.org/) 1.2. The JSON produced by this module’s default settings (in particular, the default _separators_ value) is also a subset of YAML 1.0 and 1.1. This module can thus also be used as a YAML serializer.

Note

This module’s encoders and decoders preserve input and output order by default. Order is only lost if the underlying containers are unordered.

## Basic Usage

json.dump(_obj_, _fp_, _\*_, _skipkeys\=False_, _ensure\_ascii\=True_, _check\_circular\=True_, _allow\_nan\=True_, _cls\=None_, _indent\=None_, _separators\=None_, _default\=None_, _sort\_keys\=False_, _\*\*kw_)

Serialize _obj_ as a JSON formatted stream to _fp_ (a `.write()`\-supporting [file-like object](https://docs.python.org/3.12/glossary.html#term-file-like-object)) using this [Python-to-JSON conversion table](#py-to-json-table).

Note

Unlike [`pickle`](https://docs.python.org/3.12/library/pickle.html#module-pickle) and [`marshal`](https://docs.python.org/3.12/library/marshal.html#module-marshal), JSON is not a framed protocol, so trying to serialize multiple objects with repeated calls to [`dump()`](#json.dump) using the same _fp_ will result in an invalid JSON file.

Parameters:

-   **obj** ([_object_](https://docs.python.org/3.12/library/functions.html#object)) – The Python object to be serialized.
    
-   **fp** ([file-like object](https://docs.python.org/3.12/glossary.html#term-file-like-object)) – The file-like object _obj_ will be serialized to. The `json` module always produces [`str`](https://docs.python.org/3.12/library/stdtypes.html#str) objects, not [`bytes`](https://docs.python.org/3.12/library/stdtypes.html#bytes) objects, therefore `fp.write()` must support [`str`](https://docs.python.org/3.12/library/stdtypes.html#str) input.
    
-   **skipkeys** ([_bool_](https://docs.python.org/3.12/library/functions.html#bool)) – If `True`, keys that are not of a basic type ([`str`](https://docs.python.org/3.12/library/stdtypes.html#str), [`int`](https://docs.python.org/3.12/library/functions.html#int), [`float`](https://docs.python.org/3.12/library/functions.html#float), [`bool`](https://docs.python.org/3.12/library/functions.html#bool), `None`) will be skipped instead of raising a [`TypeError`](https://docs.python.org/3.12/library/exceptions.html#TypeError). Default `False`.
    
-   **ensure\_ascii** ([_bool_](https://docs.python.org/3.12/library/functions.html#bool)) – If `True` (the default), the output is guaranteed to have all incoming non-ASCII characters escaped. If `False`, these characters will be outputted as-is.
    
-   **check\_circular** ([_bool_](https://docs.python.org/3.12/library/functions.html#bool)) – If `False`, the circular reference check for container types is skipped and a circular reference will result in a [`RecursionError`](https://docs.python.org/3.12/library/exceptions.html#RecursionError) (or worse). Default `True`.
    
-   **allow\_nan** ([_bool_](https://docs.python.org/3.12/library/functions.html#bool)) – If `False`, serialization of out-of-range [`float`](https://docs.python.org/3.12/library/functions.html#float) values (`nan`, `inf`, `-inf`) will result in a [`ValueError`](https://docs.python.org/3.12/library/exceptions.html#ValueError), in strict compliance with the JSON specification. If `True` (the default), their JavaScript equivalents (`NaN`, `Infinity`, `-Infinity`) are used.
    
-   **cls** (a [`JSONEncoder`](#json.JSONEncoder) subclass) – If set, a custom JSON encoder with the [`default()`](#json.JSONEncoder.default) method overridden, for serializing into custom datatypes. If `None` (the default), `JSONEncoder` is used.
    
-   **indent** ([_int_](https://docs.python.org/3.12/library/functions.html#int) _|_ [_str_](https://docs.python.org/3.12/library/stdtypes.html#str) _|_ _None_) – If a positive integer or string, JSON array elements and object members will be pretty-printed with that indent level. A positive integer indents that many spaces per level; a string (such as `"\t"`) is used to indent each level. If zero, negative, or `""` (the empty string), only newlines are inserted. If `None` (the default), the most compact representation is used.
    
-   **separators** ([_tuple_](https://docs.python.org/3.12/library/stdtypes.html#tuple) _|_ _None_) – A two-tuple: `(item_separator, key_separator)`. If `None` (the default), _separators_ defaults to `(', ', ': ')` if _indent_ is `None`, and `(',', ': ')` otherwise. For the most compact JSON, specify `(',', ':')` to eliminate whitespace.
    
-   **default** ([callable](https://docs.python.org/3.12/glossary.html#term-callable) | None) – A function that is called for objects that can’t otherwise be serialized. It should return a JSON encodable version of the object or raise a [`TypeError`](https://docs.python.org/3.12/library/exceptions.html#TypeError). If `None` (the default), `TypeError` is raised.
    
-   **sort\_keys** ([_bool_](https://docs.python.org/3.12/library/functions.html#bool)) – If `True`, dictionaries will be outputted sorted by key. Default `False`.
    

Changed in version 3.2: Allow strings for _indent_ in addition to integers.

Changed in version 3.4: Use `(',', ': ')` as default if _indent_ is not `None`.

Changed in version 3.6: All optional parameters are now [keyword-only](https://docs.python.org/3.12/glossary.html#keyword-only-parameter).

json.dumps(_obj_, _\*_, _skipkeys\=False_, _ensure\_ascii\=True_, _check\_circular\=True_, _allow\_nan\=True_, _cls\=None_, _indent\=None_, _separators\=None_, _default\=None_, _sort\_keys\=False_, _\*\*kw_)

Serialize _obj_ to a JSON formatted [`str`](https://docs.python.org/3.12/library/stdtypes.html#str) using this [conversion table](#py-to-json-table). The arguments have the same meaning as in [`dump()`](#json.dump).

Note

Keys in key/value pairs of JSON are always of the type [`str`](https://docs.python.org/3.12/library/stdtypes.html#str). When a dictionary is converted into JSON, all the keys of the dictionary are coerced to strings. As a result of this, if a dictionary is converted into JSON and then back into a dictionary, the dictionary may not equal the original one. That is, `loads(dumps(x)) != x` if x has non-string keys.

json.load(_fp_, _\*_, _cls\=None_, _object\_hook\=None_, _parse\_float\=None_, _parse\_int\=None_, _parse\_constant\=None_, _object\_pairs\_hook\=None_, _\*\*kw_)

Deserialize _fp_ to a Python object using the [JSON-to-Python conversion table](#json-to-py-table).

Parameters:

-   **fp** ([file-like object](https://docs.python.org/3.12/glossary.html#term-file-like-object)) – A `.read()`\-supporting [text file](https://docs.python.org/3.12/glossary.html#term-text-file) or [binary file](https://docs.python.org/3.12/glossary.html#term-binary-file) containing the JSON document to be deserialized.
    
-   **cls** (a [`JSONDecoder`](#json.JSONDecoder) subclass) – If set, a custom JSON decoder. Additional keyword arguments to `load()` will be passed to the constructor of _cls_. If `None` (the default), `JSONDecoder` is used.
    
-   **object\_hook** ([callable](https://docs.python.org/3.12/glossary.html#term-callable) | None) – If set, a function that is called with the result of any object literal decoded (a [`dict`](https://docs.python.org/3.12/library/stdtypes.html#dict)). The return value of this function will be used instead of the [`dict`](https://docs.python.org/3.12/library/stdtypes.html#dict). This feature can be used to implement custom decoders, for example [JSON-RPC](https://www.jsonrpc.org/) class hinting. Default `None`.
    
-   **object\_pairs\_hook** ([callable](https://docs.python.org/3.12/glossary.html#term-callable) | None) – If set, a function that is called with the result of any object literal decoded with an ordered list of pairs. The return value of this function will be used instead of the [`dict`](https://docs.python.org/3.12/library/stdtypes.html#dict). This feature can be used to implement custom decoders. If _object\_hook_ is also set, _object\_pairs\_hook_ takes priority. Default `None`.
    
-   **parse\_float** ([callable](https://docs.python.org/3.12/glossary.html#term-callable) | None) – If set, a function that is called with the string of every JSON float to be decoded. If `None` (the default), it is equivalent to `float(num_str)`. This can be used to parse JSON floats into custom datatypes, for example [`decimal.Decimal`](https://docs.python.org/3.12/library/decimal.html#decimal.Decimal).
    
-   **parse\_int** ([callable](https://docs.python.org/3.12/glossary.html#term-callable) | None) – If set, a function that is called with the string of every JSON int to be decoded. If `None` (the default), it is equivalent to `int(num_str)`. This can be used to parse JSON integers into custom datatypes, for example [`float`](https://docs.python.org/3.12/library/functions.html#float).
    
-   **parse\_constant** ([callable](https://docs.python.org/3.12/glossary.html#term-callable) | None) – If set, a function that is called with one of the following strings: `'-Infinity'`, `'Infinity'`, or `'NaN'`. This can be used to raise an exception if invalid JSON numbers are encountered. Default `None`.
    

Raises:

-   [**JSONDecodeError**](#json.JSONDecodeError) – When the data being deserialized is not a valid JSON document.
    
-   [**UnicodeDecodeError**](https://docs.python.org/3.12/library/exceptions.html#UnicodeDecodeError) – When the data being deserialized does not contain UTF-8, UTF-16 or UTF-32 encoded data.
    

Changed in version 3.1:

-   Added the optional _object\_pairs\_hook_ parameter.
    
-   _parse\_constant_ doesn’t get called on ‘null’, ‘true’, ‘false’ anymore.
    

Changed in version 3.6:

-   All optional parameters are now [keyword-only](https://docs.python.org/3.12/glossary.html#keyword-only-parameter).
    
-   _fp_ can now be a [binary file](https://docs.python.org/3.12/glossary.html#term-binary-file). The input encoding should be UTF-8, UTF-16 or UTF-32.
    

Changed in version 3.11: The default _parse\_int_ of [`int()`](https://docs.python.org/3.12/library/functions.html#int) now limits the maximum length of the integer string via the interpreter’s [integer string conversion length limitation](https://docs.python.org/3.12/library/stdtypes.html#int-max-str-digits) to help avoid denial of service attacks.

json.loads(_s_, _\*_, _cls\=None_, _object\_hook\=None_, _parse\_float\=None_, _parse\_int\=None_, _parse\_constant\=None_, _object\_pairs\_hook\=None_, _\*\*kw_)

Identical to [`load()`](#json.load), but instead of a file-like object, deserialize _s_ (a [`str`](https://docs.python.org/3.12/library/stdtypes.html#str), [`bytes`](https://docs.python.org/3.12/library/stdtypes.html#bytes) or [`bytearray`](https://docs.python.org/3.12/library/stdtypes.html#bytearray) instance containing a JSON document) to a Python object using this [conversion table](#json-to-py-table).

Changed in version 3.6: _s_ can now be of type [`bytes`](https://docs.python.org/3.12/library/stdtypes.html#bytes) or [`bytearray`](https://docs.python.org/3.12/library/stdtypes.html#bytearray). The input encoding should be UTF-8, UTF-16 or UTF-32.

Changed in version 3.9: The keyword argument _encoding_ has been removed.

## Encoders and Decoders

_class_ json.JSONDecoder(_\*_, _object\_hook\=None_, _parse\_float\=None_, _parse\_int\=None_, _parse\_constant\=None_, _strict\=True_, _object\_pairs\_hook\=None_)

Simple JSON decoder.

Performs the following translations in decoding by default:

| 
JSON

 | 

Python

 |
| --- | --- |
| 

object

 | 

dict

 |
| 

array

 | 

list

 |
| 

string

 | 

str

 |
| 

number (int)

 | 

int

 |
| 

number (real)

 | 

float

 |
| 

true

 | 

True

 |
| 

false

 | 

False

 |
| 

null

 | 

None

 |

It also understands `NaN`, `Infinity`, and `-Infinity` as their corresponding `float` values, which is outside the JSON spec.

_object\_hook_ is an optional function that will be called with the result of every JSON object decoded and its return value will be used in place of the given [`dict`](https://docs.python.org/3.12/library/stdtypes.html#dict). This can be used to provide custom deserializations (e.g. to support [JSON-RPC](https://www.jsonrpc.org/) class hinting).

_object\_pairs\_hook_ is an optional function that will be called with the result of every JSON object decoded with an ordered list of pairs. The return value of _object\_pairs\_hook_ will be used instead of the [`dict`](https://docs.python.org/3.12/library/stdtypes.html#dict). This feature can be used to implement custom decoders. If _object\_hook_ is also defined, the _object\_pairs\_hook_ takes priority.

Changed in version 3.1: Added support for _object\_pairs\_hook_.

_parse\_float_ is an optional function that will be called with the string of every JSON float to be decoded. By default, this is equivalent to `float(num_str)`. This can be used to use another datatype or parser for JSON floats (e.g. [`decimal.Decimal`](https://docs.python.org/3.12/library/decimal.html#decimal.Decimal)).

_parse\_int_ is an optional function that will be called with the string of every JSON int to be decoded. By default, this is equivalent to `int(num_str)`. This can be used to use another datatype or parser for JSON integers (e.g. [`float`](https://docs.python.org/3.12/library/functions.html#float)).

_parse\_constant_ is an optional function that will be called with one of the following strings: `'-Infinity'`, `'Infinity'`, `'NaN'`. This can be used to raise an exception if invalid JSON numbers are encountered.

If _strict_ is false (`True` is the default), then control characters will be allowed inside strings. Control characters in this context are those with character codes in the 0–31 range, including `'\t'` (tab), `'\n'`, `'\r'` and `'\0'`.

If the data being deserialized is not a valid JSON document, a [`JSONDecodeError`](#json.JSONDecodeError) will be raised.

Changed in version 3.6: All parameters are now [keyword-only](https://docs.python.org/3.12/glossary.html#keyword-only-parameter).

decode(_s_)

Return the Python representation of _s_ (a [`str`](https://docs.python.org/3.12/library/stdtypes.html#str) instance containing a JSON document).

[`JSONDecodeError`](#json.JSONDecodeError) will be raised if the given JSON document is not valid.

raw\_decode(_s_)

Decode a JSON document from _s_ (a [`str`](https://docs.python.org/3.12/library/stdtypes.html#str) beginning with a JSON document) and return a 2-tuple of the Python representation and the index in _s_ where the document ended.

This can be used to decode a JSON document from a string that may have extraneous data at the end.

_class_ json.JSONEncoder(_\*_, _skipkeys\=False_, _ensure\_ascii\=True_, _check\_circular\=True_, _allow\_nan\=True_, _sort\_keys\=False_, _indent\=None_, _separators\=None_, _default\=None_)

Extensible JSON encoder for Python data structures.

Supports the following objects and types by default:

| 
Python

 | 

JSON

 |
| --- | --- |
| 

dict

 | 

object

 |
| 

list, tuple

 | 

array

 |
| 

str

 | 

string

 |
| 

int, float, int- & float-derived Enums

 | 

number

 |
| 

True

 | 

true

 |
| 

False

 | 

false

 |
| 

None

 | 

null

 |

Changed in version 3.4: Added support for int- and float-derived Enum classes.

To extend this to recognize other objects, subclass and implement a [`default()`](#json.JSONEncoder.default) method with another method that returns a serializable object for `o` if possible, otherwise it should call the superclass implementation (to raise [`TypeError`](https://docs.python.org/3.12/library/exceptions.html#TypeError)).

If _skipkeys_ is false (the default), a [`TypeError`](https://docs.python.org/3.12/library/exceptions.html#TypeError) will be raised when trying to encode keys that are not [`str`](https://docs.python.org/3.12/library/stdtypes.html#str), [`int`](https://docs.python.org/3.12/library/functions.html#int), [`float`](https://docs.python.org/3.12/library/functions.html#float), [`bool`](https://docs.python.org/3.12/library/functions.html#bool) or `None`. If _skipkeys_ is true, such items are simply skipped.

If _ensure\_ascii_ is true (the default), the output is guaranteed to have all incoming non-ASCII characters escaped. If _ensure\_ascii_ is false, these characters will be output as-is.

If _check\_circular_ is true (the default), then lists, dicts, and custom encoded objects will be checked for circular references during encoding to prevent an infinite recursion (which would cause a [`RecursionError`](https://docs.python.org/3.12/library/exceptions.html#RecursionError)). Otherwise, no such check takes place.

If _allow\_nan_ is true (the default), then `NaN`, `Infinity`, and `-Infinity` will be encoded as such. This behavior is not JSON specification compliant, but is consistent with most JavaScript based encoders and decoders. Otherwise, it will be a [`ValueError`](https://docs.python.org/3.12/library/exceptions.html#ValueError) to encode such floats.

If _sort\_keys_ is true (default: `False`), then the output of dictionaries will be sorted by key; this is useful for regression tests to ensure that JSON serializations can be compared on a day-to-day basis.

If _indent_ is a non-negative integer or string, then JSON array elements and object members will be pretty-printed with that indent level. An indent level of 0, negative, or `""` will only insert newlines. `None` (the default) selects the most compact representation. Using a positive integer indent indents that many spaces per level. If _indent_ is a string (such as `"\t"`), that string is used to indent each level.

Changed in version 3.2: Allow strings for _indent_ in addition to integers.

If specified, _separators_ should be an `(item_separator, key_separator)` tuple. The default is `(', ', ': ')` if _indent_ is `None` and `(',', ': ')` otherwise. To get the most compact JSON representation, you should specify `(',', ':')` to eliminate whitespace.

Changed in version 3.4: Use `(',', ': ')` as default if _indent_ is not `None`.

If specified, _default_ should be a function that gets called for objects that can’t otherwise be serialized. It should return a JSON encodable version of the object or raise a [`TypeError`](https://docs.python.org/3.12/library/exceptions.html#TypeError). If not specified, [`TypeError`](https://docs.python.org/3.12/library/exceptions.html#TypeError) is raised.

Changed in version 3.6: All parameters are now [keyword-only](https://docs.python.org/3.12/glossary.html#keyword-only-parameter).

default(_o_)

Implement this method in a subclass such that it returns a serializable object for _o_, or calls the base implementation (to raise a [`TypeError`](https://docs.python.org/3.12/library/exceptions.html#TypeError)).

For example, to support arbitrary iterators, you could implement [`default()`](#json.JSONEncoder.default) like this:

```python
def default(self, o):
   try:
       iterable = iter(o)
   except TypeError:
       pass
   else:
       return list(iterable)
   # Let the base class default method raise the TypeError
   return super().default(o)
```

encode(_o_)

Return a JSON string representation of a Python data structure, _o_. For example:

```python
>>> json.JSONEncoder().encode({"foo": ["bar", "baz"]})
'{"foo": ["bar", "baz"]}'
```

iterencode(_o_)

Encode the given object, _o_, and yield each string representation as available. For example:

```python
for chunk in json.JSONEncoder().iterencode(bigobject):
    mysocket.write(chunk)
```

## Exceptions

_exception_ json.JSONDecodeError(_msg_, _doc_, _pos_)

Subclass of [`ValueError`](https://docs.python.org/3.12/library/exceptions.html#ValueError) with the following additional attributes:

msg

The unformatted error message.

doc

The JSON document being parsed.

pos

The start index of _doc_ where parsing failed.

lineno

The line corresponding to _pos_.

colno

The column corresponding to _pos_.

Added in version 3.5.

## Standard Compliance and Interoperability

The JSON format is specified by [**RFC 7159**](https://datatracker.ietf.org/doc/html/rfc7159.html) and by [ECMA-404](https://ecma-international.org/publications-and-standards/standards/ecma-404/). This section details this module’s level of compliance with the RFC. For simplicity, [`JSONEncoder`](#json.JSONEncoder) and [`JSONDecoder`](#json.JSONDecoder) subclasses, and parameters other than those explicitly mentioned, are not considered.

This module does not comply with the RFC in a strict fashion, implementing some extensions that are valid JavaScript but not valid JSON. In particular:

-   Infinite and NaN number values are accepted and output;
    
-   Repeated names within an object are accepted, and only the value of the last name-value pair is used.
    

Since the RFC permits RFC-compliant parsers to accept input texts that are not RFC-compliant, this module’s deserializer is technically RFC-compliant under default settings.

### Character Encodings

The RFC requires that JSON be represented using either UTF-8, UTF-16, or UTF-32, with UTF-8 being the recommended default for maximum interoperability.

As permitted, though not required, by the RFC, this module’s serializer sets _ensure\_ascii=True_ by default, thus escaping the output so that the resulting strings only contain ASCII characters.

Other than the _ensure\_ascii_ parameter, this module is defined strictly in terms of conversion between Python objects and [`Unicode strings`](https://docs.python.org/3.12/library/stdtypes.html#str), and thus does not otherwise directly address the issue of character encodings.

The RFC prohibits adding a byte order mark (BOM) to the start of a JSON text, and this module’s serializer does not add a BOM to its output. The RFC permits, but does not require, JSON deserializers to ignore an initial BOM in their input. This module’s deserializer raises a [`ValueError`](https://docs.python.org/3.12/library/exceptions.html#ValueError) when an initial BOM is present.

The RFC does not explicitly forbid JSON strings which contain byte sequences that don’t correspond to valid Unicode characters (e.g. unpaired UTF-16 surrogates), but it does note that they may cause interoperability problems. By default, this module accepts and outputs (when present in the original [`str`](https://docs.python.org/3.12/library/stdtypes.html#str)) code points for such sequences.

### Infinite and NaN Number Values

The RFC does not permit the representation of infinite or NaN number values. Despite that, by default, this module accepts and outputs `Infinity`, `-Infinity`, and `NaN` as if they were valid JSON number literal values:

```python
>>> # Neither of these calls raises an exception, but the results are not valid JSON
>>> json.dumps(float('-inf'))
'-Infinity'
>>> json.dumps(float('nan'))
'NaN'
>>> # Same when deserializing
>>> json.loads('-Infinity')
-inf
>>> json.loads('NaN')
nan
```

In the serializer, the _allow\_nan_ parameter can be used to alter this behavior. In the deserializer, the _parse\_constant_ parameter can be used to alter this behavior.

### Repeated Names Within an Object

The RFC specifies that the names within a JSON object should be unique, but does not mandate how repeated names in JSON objects should be handled. By default, this module does not raise an exception; instead, it ignores all but the last name-value pair for a given name:

```python
>>> weird_json = '{"x": 1, "x": 2, "x": 3}'
>>> json.loads(weird_json)
{'x': 3}
```

The _object\_pairs\_hook_ parameter can be used to alter this behavior.

### Top-level Non-Object, Non-Array Values

The old version of JSON specified by the obsolete [**RFC 4627**](https://datatracker.ietf.org/doc/html/rfc4627.html) required that the top-level value of a JSON text must be either a JSON object or array (Python [`dict`](https://docs.python.org/3.12/library/stdtypes.html#dict) or [`list`](https://docs.python.org/3.12/library/stdtypes.html#list)), and could not be a JSON null, boolean, number, or string value. [**RFC 7159**](https://datatracker.ietf.org/doc/html/rfc7159.html) removed that restriction, and this module does not and has never implemented that restriction in either its serializer or its deserializer.

Regardless, for maximum interoperability, you may wish to voluntarily adhere to the restriction yourself.

### Implementation Limitations

Some JSON deserializer implementations may set limits on:

-   the size of accepted JSON texts
    
-   the maximum level of nesting of JSON objects and arrays
    
-   the range and precision of JSON numbers
    
-   the content and maximum length of JSON strings
    

This module does not impose any such limits beyond those of the relevant Python datatypes themselves or the Python interpreter itself.

When serializing to JSON, beware any such limitations in applications that may consume your JSON. In particular, it is common for JSON numbers to be deserialized into IEEE 754 double precision numbers and thus subject to that representation’s range and precision limitations. This is especially relevant when serializing Python [`int`](https://docs.python.org/3.12/library/functions.html#int) values of extremely large magnitude, or when serializing instances of “exotic” numerical types such as [`decimal.Decimal`](https://docs.python.org/3.12/library/decimal.html#decimal.Decimal).

## Command Line Interface

**Source code:** [Lib/json/tool.py](https://github.com/python/cpython/tree/3.12/Lib/json/tool.py)

* * *

The [`json.tool`](#module-json.tool) module provides a simple command line interface to validate and pretty-print JSON objects.

If the optional `infile` and `outfile` arguments are not specified, [`sys.stdin`](https://docs.python.org/3.12/library/sys.html#sys.stdin) and [`sys.stdout`](https://docs.python.org/3.12/library/sys.html#sys.stdout) will be used respectively:

```bash
$ echo '{"json": "obj"}' | python -m json.tool
{
    "json": "obj"
}
$ echo '{1.2:3.4}' | python -m json.tool
Expecting property name enclosed in double quotes: line 1 column 2 (char 1)
```

Changed in version 3.5: The output is now in the same order as the input. Use the [`--sort-keys`](#cmdoption-json.tool-sort-keys) option to sort the output of dictionaries alphabetically by key.

### Command line options

infile

The JSON file to be validated or pretty-printed:

```bash
$ python -m json.tool mp_films.json
[
    {
        "title": "And Now for Something Completely Different",
        "year": 1971
    },
    {
        "title": "Monty Python and the Holy Grail",
        "year": 1975
    }
]
```

If _infile_ is not specified, read from [`sys.stdin`](https://docs.python.org/3.12/library/sys.html#sys.stdin).

outfile

Write the output of the _infile_ to the given _outfile_. Otherwise, write it to [`sys.stdout`](https://docs.python.org/3.12/library/sys.html#sys.stdout).

\--sort-keys

Sort the output of dictionaries alphabetically by key.

Added in version 3.5.

\--no-ensure-ascii

Disable escaping of non-ascii characters, see [`json.dumps()`](#json.dumps) for more information.

Added in version 3.9.

\--json-lines

Parse every input line as separate JSON object.

Added in version 3.8.

\--indent, \--tab, \--no-indent, \--compact

Mutually exclusive options for whitespace control.

Added in version 3.9.

\-h, \--help

Show the help message.