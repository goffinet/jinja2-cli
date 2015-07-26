"""
jinja2-cli
==========

License: BSD, see LICENSE for more details.
"""

from jinja2cli import __version__


class InvalidDataFormat(Exception): pass


class InvalidInputData(Exception): pass


class MalformedJSON(InvalidInputData): pass


class MalformedINI(InvalidInputData): pass


class MalformedYAML(InvalidInputData): pass


class MalformedQuerystring(InvalidInputData): pass


# Global list of available format parsers on your system
# mapped to the callable/Exception to parse a string into a dict
formats = {}

# json - builtin json or simplejson as a fallback
try:
    import json

    formats['json'] = (json.loads, ValueError, MalformedJSON)
except ImportError:
    try:
        import simplejson

        formats['json'] = (simplejson.loads, simplejson.decoder.JSONDecodeError, MalformedJSON)
    except ImportError:
        pass


# ini - Nobody likes you.
try:
    # Python 2
    import ConfigParser
except ImportError:
    # Python 3
    import configparser as ConfigParser


def _parse_ini(data):
    import StringIO

    class MyConfigParser(ConfigParser.ConfigParser):
        def as_dict(self):
            d = dict(self._sections)
            for k in d:
                d[k] = dict(self._defaults, **d[k])
                d[k].pop('__name__', None)
            return d

    p = MyConfigParser()
    p.readfp(StringIO.StringIO(data))
    return p.as_dict()


formats['ini'] = (_parse_ini, ConfigParser.Error, MalformedINI)


# yaml - with PyYAML
try:
    import yaml

    formats['yaml'] = formats['yml'] = (yaml.load, yaml.YAMLError, MalformedYAML)
except ImportError:
    pass


# querystring - querystring parsing
def _parse_qs(data):
    """ Extend urlparse to allow objects in dot syntax.

    >>> _parse_qs('user.first_name=Matt&user.last_name=Robenolt')
    {'user': {'first_name': 'Matt', 'last_name': 'Robenolt'}}
    """
    try:
        import urlparse
    except ImportError:
        import urllib.parse as urlparse
    dict_ = {}
    for k, v in urlparse.parse_qs(data).items():
        v = map(lambda x: x.strip(), v)
        v = v[0] if len(v) == 1 else v
        if '.' in k:
            pieces = k.split('.')
            cur = dict_
            for idx, piece in enumerate(pieces):
                if piece not in cur:
                    cur[piece] = {}
                if idx == len(pieces) - 1:
                    cur[piece] = v
                cur = cur[piece]
        else:
            dict_[k] = v
    return dict_


formats['querystring'] = (_parse_qs, Exception, MalformedQuerystring)

import os
import sys
from optparse import OptionParser

import jinja2
from jinja2 import Environment, FileSystemLoader


def format_data(format_, data):
    return formats[format_][0](data)


def render(template_path, data, extensions):
    env = Environment(
        loader=FileSystemLoader(os.path.dirname(template_path)),
        extensions=extensions,
    )
    output = env.get_template(os.path.basename(template_path)).render(data).encode('utf-8')
    return output


def cli(opts, args):
    format = opts.format
    if args[1] == '-':
        data = sys.stdin.read()
        if format == 'auto':
            # default to yaml first if available since yaml is a superset of json
            if 'yaml' in formats:
                format = 'yaml'
            else:
                format = 'json'
    else:
        path = os.path.join(os.getcwd(), os.path.expanduser(args[1]))
        if format == 'auto':
            ext = os.path.splitext(path)[1][1:]
            if ext in formats:
                format = ext
        data = open(path).read()

    template_path = os.path.abspath(args[0])

    try:
        data = format_data(format, data)
    except formats[format][1]:
        raise formats[format][2](u'%s ...' % data[:60])
        sys.exit(1)

    extensions = []
    for ext in opts.extensions:
        # Allow shorthand and assume if it's not a module
        # path, it's probably trying to use builtin from jinja2
        if '.' not in ext:
            ext = 'jinja2.ext.' + ext
        extensions.append(ext)

    output = render(template_path, data, extensions)

    sys.stdout.write(output)
    sys.exit(0)


def main():
    parser = OptionParser(usage="usage: %prog [options] <input template> <input data>",
                          version="jinja2-cli v%s\n - Jinja2 v%s" % (__version__, jinja2.__version__))
    parser.add_option('--format', help='format of input variables: %s' % ', '.join(sorted(formats.keys() + ['auto'])),
                      dest='format', action='store', default='auto')
    parser.add_option('-e', '--extension', help='extra jinja2 extensions to load',
                      dest='extensions', action='append', default=['do'])
    opts, args = parser.parse_args()

    # Dedupe list
    opts.extensions = set(opts.extensions)

    if len(args) == 0:
        parser.print_help()
        sys.exit(1)

    if args[0] == 'help':
        parser.print_help()
        sys.exit(1)

    # Without the second argv, assume they want to read from stdin
    if len(args) == 1:
        args.append('-')

    if opts.format not in formats and opts.format != 'auto':
        raise InvalidDataFormat(opts.format)

    cli(opts, args)
    sys.exit(0)


if __name__ == '__main__':
    main()
