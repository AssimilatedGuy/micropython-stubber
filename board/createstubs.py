"""
Create stubs for (all) modules on a MicroPython board
Copyright (c) 2019-2020 Jos Verlinde
"""
# pylint: disable= invalid-name, missing-function-docstring, import-outside-toplevel, logging-not-lazy
import sys
import gc
import logging
import uos as os
from utime import sleep_us
from ujson import dumps

ENOENT = 2
stbr_v = '1.3.10'
# deal with ESP32 firmware specific implementations.
try:
    from machine import resetWDT #LoBo
except ImportError:
    def resetWDT():
        pass

class Stubber():
    "Generate stubs for modules in firmware"
    def __init__(self, path: str = None, firmware_id: str = None):
        self.init_mem = gc.mem_free()
        try:
            if os.uname().release == '1.13.0' and os.uname().version < 'v1.13-103':
                raise NotImplementedError("MicroPython 1.13.0 cannot be stubbed")
        except AttributeError:
            pass

        self._log = logging.getLogger('stubber')
        self._report = []
        self.info = self._info()

        gc.collect()
        self._fwid = str(firmware_id).lower() or "{family}-{port}-{ver}".format(**self.info).lower()

        if not path:
            path = get_param()

        if path:
            if path.endswith('/'):
                path = path[:-1]
        else:
            path = get_root()
        self.path = "{0}/stubs/{family}-{port}-{1}".format(path, flat(self.info['ver']), **self.info)

        self._log.debug(self.path)
        try:
            self.ensure_folder(path + "/")
        except OSError:
            self._log.error("error creating stub folder {}".format(path))
        self.prblm = ["upysh", "webrepl_setup", "http_client", "http_client_ssl", "http_server", "http_server_ssl"]
        self.excl = ["webrepl", "_webrepl", "port_diag", "example_sub_led.py", "example_pub_button.py"]
        # there is no option to discover modules from upython, need to hardcode
        # below contains combined modules from  Micropython ESP8622, ESP32, Loboris, pycom and ulab
        # modules to stub : 118
        self.mods = [line.rstrip('\r').rstrip('\n') for line in open('stublist.txt')]
        
        # try to avoid running out of memory with nested mods
        # self.include_nested = gc.mem_free() > 3200 # pylint: disable=no-member

    @staticmethod
    def _info():
        "collect base information on this runtime"
        i = {'name': sys.implementation.name,    # - micropython
             'release': '0.0.0',                 # mpy semver from sys.implementation or os.uname()release
             'version': '0.0.0',                 # major.minor.0
             'build': '',                        # parsed from version
             'sysname': 'unknown',               # esp32
             'nodename': 'unknown',              # ! not on all builds
             'machine': 'unknown',               # ! not on all builds
             'family': sys.implementation.name,  # fw families, micropython , pycopy , lobo , pycomm
             'platform': sys.platform,               # port: esp32 / win32 / linux
             'port': sys.platform,               # port: esp32 / win32 / linux
             'ver': ''                           # short version
            }
        try:
            i['release'] = ".".join([str(i) for i in sys.implementation.version])
            i['version'] = i['release']
            i['name'] = sys.implementation.name
            # i['mpy'] = sys.implementation.mpy    # esp8622 mem constraints
        except AttributeError:
            pass
        if sys.platform not in ('unix', 'win32', 'esp8266'):
            try:
                u = os.uname()
                i['sysname'] = u.sysname
                i['nodename'] = u.nodename
                i['release'] = u.release
                i['machine'] = u.machine
                # parse micropython build info
                if ' on ' in u.version:
                    s = u.version.split('on ')[0]
                    try:
                        i['build'] = s.split('-')[1]
                    except IndexError:
                        pass
            except (IndexError, AttributeError, TypeError):
                pass

        try: # families
            from pycopy import const
            i['family'] = 'pycopy'
            del const
        except (ImportError, KeyError):
            pass
        if i['platform'] == 'esp32_LoBo':
            i['family'] = 'loboris'
            i['port'] = 'esp32'
        elif i['sysname'] == 'ev3':
            # ev3 pybricks
            i['family'] = 'ev3-pybricks'
            i['release'] = "1.0.0"
            try:
                # Version 2.0 introduces the EV3Brick() class.
                from pybricks.hubs import EV3Brick
                i['release'] = "2.0.0"
            except ImportError:
                pass

        # version info
        if i['release']:
            i['ver'] = 'v'+i['release']
        if i['family'] != 'loboris':
            if i['release'] >= '1.10.0' and i['release'].endswith('.0'):
                #drop the .0 for newer releases
                i['ver'] = i['release'][:-2]
            else:
                i['ver'] = i['release']
            # add the build nr
            if i['build'] != '':
                i['ver'] += '-'+i['build']
        # removed due to ESP8622 mem constraints
        # if 'mpy' in i:          # mpy on some v1.11+ builds
        #     sys_mpy = i['mpy']
        #     arch = [None, 'x86', 'x64', 'armv6', 'armv6m',
        #             'armv7m', 'armv7em', 'armv7emsp', 'armv7emdp',
        #             'xtensa', 'xtensawin'][sys_mpy >> 10]
        #     if arch:
        #         i['arch'] = arch
        return i

    def get_obj_attributes(self, obj: object):
        "extract information of the objects members and attributes"
        result = []
        errors = []
        name = None
        self._log.debug('get attributes {} {}'.format(repr(obj), obj))
        for name in dir(obj):
            try:
                val = getattr(obj, name)
                # name , value , type
                result.append((name, repr(val), repr(type(val)), val))
                # self._log.info( result[-1])
            except AttributeError as e:
                errors.append("Couldn't get attribute '{}' from object '{}', Err: {}".format(name, obj, e))
        gc.collect()
        return result, errors

    def add_modules(self, modules: list):
        "Add additional modules to be exported"
        self.mods = sorted(set(self.mods) | set(modules))

    def create_all_stubs(self):
        "Create stubs for all configured modules"
        self._log.info("Start micropython-stubber v{} on {}".format(stbr_v, self._fwid))
        # start with the (more complex) modules with a / first to reduce memory problems
        # 
        #MEM self.mods = [m for m in self.mods if '/' in m] + [m for m in self.mods if '/' not in m]
        gc.collect()
        for mod_nm in self.mods:
            if mod_nm.startswith("_") and mod_nm != '_thread':
                self._log.warning("Skip module: {:<20}        : Internal ".format(mod_nm))
                continue
            if mod_nm in self.prblm:
                self._log.warning("Skip module: {:<20}        : Known prblm".format(mod_nm))
                continue
            if mod_nm in self.excl:
                self._log.warning("Skip module: {:<20}        : Excluded".format(mod_nm))
                continue

            f_nm = "{}/{}.py".format(
                self.path,
                mod_nm.replace(".", "/")
            )
            gc.collect()
            m1 = gc.mem_free() # pylint: disable=no-member
            self._log.info("Stub module: {:<20} to file: {:<55} mem:{:>5}".format(mod_nm, f_nm, m1))
            try:
                self.create_module_stub(mod_nm, f_nm)
            except OSError:
                pass
            gc.collect()
            self._log.debug("Memory     : {:>20} {:>6X}".format(m1, m1-gc.mem_free())) # pylint: disable=no-member
        self._log.info('Finally done')

    def create_module_stub(self, mod_nm: str, f_nm: str = None):
        "Create a Stub of a single python module"
        if mod_nm.startswith("_") and mod_nm != '_thread':
            self._log.warning("SKIPPING internal module:{}".format(mod_nm))
            return

        if mod_nm in self.prblm:
            self._log.warning("SKIPPING prblm module:{}".format(mod_nm))
            return
        if '/' in mod_nm:
            #for nested modules
            self.ensure_folder(f_nm)
            mod_nm = mod_nm.replace('/', '.')

        if f_nm is None:
            f_nm = mod_nm.replace('.', '_') + ".py"

        #import the module (as new_mod) to examine it
        failed = False
        new_mod = None
        try:
            new_mod = __import__(mod_nm, None, None, ('*'))
        except ImportError:
            failed = True
            self._log.warning("Skip module: {:<20}        : Failed to import".format(mod_nm))
            if not '.' in mod_nm:
                return

        #re-try import after importing pars
        if failed and '.' in mod_nm:
            self._log.debug("re-try import with pars")
            lvls = mod_nm.split('.')
            for n in range(1, len(lvls)):
                par_nm = ".".join(lvls[0:n])
                try:
                    par = __import__(par_nm)
                    del par
                except (ImportError, KeyError):
                    pass
            try:
                new_mod = __import__(mod_nm, None, None, ('*'))
                self._log.debug("OK , imported module: {} ".format(mod_nm))
            except ImportError: # now bail out
                self._log.debug("Failed to import module: {}".format(mod_nm))
                return

        # Start a new file
        with open(f_nm, "w") as fp:
            # todo: improve header
            s = "\"\"\"\nModule: '{0}' on {1}\n\"\"\"\n# MCU: {2}\n# Stubber: {3}\n".format(
                mod_nm, self._fwid, self.info, stbr_v)
            fp.write(s)
            self.write_object_stub(fp, new_mod, mod_nm, "")
            self._report.append({"module":mod_nm, "file": f_nm})

        if not mod_nm in ["os", "sys", "logging", "gc"]:
            #try to unload the module unless we use it
            try:
                del new_mod
            except (OSError, KeyError):#lgtm [py/unreachable-statement]
                self._log.warning("could not del new_mod")
            for m in sys.modules:
                if not m in ["os", "sys", "logging", "gc"]:
                    try:
                        del sys.modules[mod_nm]
                    except KeyError:
                        self._log.debug("could not del modules[{}]".format(mod_nm))
            gc.collect()

    def write_object_stub(self, fp, object_expr: object, obj_name: str, indent: str):
        "Write a module/object stub to an open file. Can be called recursive."
        if object_expr in self.prblm:
            self._log.warning("SKIPPING prblm module:{}".format(object_expr))
            return

        self._log.debug("DUMP    : {}".format(object_expr))
        items, errors = self.get_obj_attributes(object_expr)

        if errors:
            self._log.error(errors)

        for name, rep, typ, obj in sorted(items, key=lambda x: x[0]):
            if name.startswith("__"):
                #skip internals
                continue

            # allow the scheduler to run on LoBo based FW
            resetWDT()
            sleep_us(1)

            self._log.debug("DUMPING {}{}{}:{}".format(indent, object_expr, name, typ))

            if typ in ["<class 'function'>", "<class 'bound_method'>"]:
                s = indent + "def " + name + "():\n"    #todo: add self, and optional params
                s += indent + "    pass\n\n"
                fp.write(s)
                self._log.debug('\n'+s)

            elif typ in ["<class 'str'>", "<class 'int'>", "<class 'float'>"]:
                s = indent + name + " = " + rep + "\n"
                fp.write(s)
                self._log.debug('\n'+s)
            #new class
            elif typ == "<class 'type'>" and indent == "":
                # full expansion only on toplevel
                # stub style : Empty comment ... + hardcoded 4 spaces
                s = "\n" + indent + "class " + name + ":\n"  # What about superclass?
                s += indent + "    ''\n"

                fp.write(s)
                self._log.debug('\n'+s)

                self._log.debug("# recursion..")
                self.write_object_stub(fp, obj, "{0}.{1}".format(obj_name, name), indent + "    ")
            else:
                # keep only the name
                fp.write(indent + name + " = None\n")
        del items
        del errors
        try:
            del name, rep, typ, obj # pylint: disable=undefined-loop-variable
        except (OSError, KeyError):#lgtm [py/unreachable-statement]
            pass


    def clean(self, path: str = None):
        "Remove all files from the stub folder"
        if path is None:
            path = self.path
        self._log.info("Clean/remove files in folder: {}".format(path))
        try:
            items = os.listdir(path)
        except (OSError, AttributeError):#lgtm [py/unreachable-statement]
            # os.listdir fails on unix
            return
        for fn in items:
            try:
                item = "{}/{}".format(path, fn)
                os.remove(item)
            except OSError:
                try: #folder
                    self.clean(item)
                    os.rmdir(item)
                except OSError:
                    pass

    def report(self, filename: str = "modules.json"):
        "create json with list of exported modules"
        self._log.info("Created stubs for {} modules on board {}\nPath: {}".format(
            len(self._report),
            self._fwid,
            self.path
            ))
        f_name = "{}/{}".format(self.path, filename)
        gc.collect()
        try:
            # write json by node to reduce memory requirements
            with open(f_name, 'w') as f:
                f.write('{')
                f.write(dumps({'firmware': self.info})[1:-1])
                f.write(',')
                f.write(dumps({'stubber':{'version': stbr_v}})[1:-1])
                f.write(',')
                f.write('"modules" :[')
                start = True
                for n in self._report:
                    if start:
                        start = False
                    else:
                        f.write(',')
                    f.write(dumps(n))
                f.write(']}')
        except OSError:
            self._log.error("Failed to create the report.")

    def ensure_folder(self, path: str):
        "Create nested folders if needed"
        i = start = 0
        while i != -1:
            i = path.find('/', start)
            if i != -1:
                if i == 0:
                    p = path[0]
                else:
                    p = path[0:i]
                # p = partial folder
                try:
                    _ = os.stat(p)
                except OSError as e:
                    # folder does not exist
                    if e.args[0] == ENOENT:
                        try:
                            os.mkdir(p)
                        except OSError as e2:
                            self._log.error('failed to create folder {}'.format(p))
                            raise e2
                    else:
                        self._log.error('failed to create folder {}'.format(p))
                        raise e
            #next level deep
            start = i+1

def get_root()->str:
    "Determine the root folder of the device"
    try:
        r = "/flash"
        _ = os.stat(r)
    except OSError as e:
        if e.args[0] == ENOENT:
            try:
                r = os.getcwd()
            except:
                # unix port
                r = '.'
        else:
            r = '/'
    return r

def flat(s):
    "Turn a fwid from '1.2.3' into '1_2_3' to be used in filename"
    # path name restrictions
    chars = " .()/\\:$"
    for c in chars:
        s = s.replace(c, "_")
    return s

def show_help():
    print("-p, --path   path to store the stubs in, defaults to '.'")
    sys.exit(1)

def get_param()->str:
    "get --path from cmdline. [unix/win]"
    path = None
    if len(sys.argv) == 3:
        cmd = (sys.argv[1]).lower()
        if cmd in ('--path', '-p'):
            path = sys.argv[2]
        else:
            show_help()
    elif len(sys.argv) >= 2:
        show_help()
    return path

def uPy()->bool:
    "runtime test to determine full or micropython"
    #pylint: disable=unused-variable,eval-used
    try:
        # either test should fail on micropython
        # a) https://docs.micropython.org/en/latest/genrst/syntax.html#spaces
        # b) https://docs.micropython.org/en/latest/genrst/builtin_types.html#bytes-with-keywords-not-implemented
        a = eval("1and 0")
        b = bytes("abc", encoding="utf8")
        return False
    except (NotImplementedError, SyntaxError):
        return True

def _log_mem(start_free):
    # logging for mem optimisation
    gc.collect()
    free = gc.mem_free()
    used = start_free - free
    logging.info('start free:{:,}, end: {:,}, used {:,}'.format(start_free, free, used))
    with open('./memory.csv', 'a') as file:
        file.write('{},{},{},{}\n'.format(start_free, free, used, sys.platform))

def main():
    print('stubber version :', stbr_v)
    try:
        logging.basicConfig(level=logging.INFO)
    except NameError:
        pass
    stubber = Stubber()

    print(stubber.info)
    # Option: Specify a firmware name & version
    # stubber = Stubber(firmware_id='HoverBot v1.2.1')
    stubber.clean()
    # # Option: Add your own modules
    # # stubber.add_modules(['bluetooth','GPS'])
    stubber.create_all_stubs()
    stubber.report()

    # logging from mem optimisation
    _log_mem(stubber.init_mem)

if __name__ == "__main__" or uPy():
    main()
