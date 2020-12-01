"""
Create stubs for (all) modules on a MicroPython board
Copyright (c) 2019-2020 Jos Verlinde
"""
import sys
import gc
import uos as os
from utime import sleep_us
from ujson import dumps
ENOENT=2
stbr_v='1.3.8'
try:
 from machine import resetWDT 
except ImportError:
 def resetWDT():
  pass
class Stubber():
 def __init__(self,path:str=None,firmware_id:str=None):
  self.init_mem=gc.mem_free()
  try:
   if os.uname().release=='1.13.0' and os.uname().version<'v1.13-103':
    raise NotImplementedError("MicroPyton 1.13.0 cannot be stubbed")
  except AttributeError:
   pass
  self._report=[]
  self.info=self._info()
  gc.collect()
  self._fwid=str(firmware_id).lower()or "{family}-{port}-{ver}".format(**self.info).lower()
  if not path:
   path=get_param()
  if path:
   if path.endswith('/'):
    path=path[:-1]
  else:
   path=get_root()
  self.path="{0}/stubs/{family}-{port}-{1}".format(path,flat(self.info['ver']),**self.info)
  try:
   self.ensure_folder(path+"/")
  except OSError:
   pass
  self.prblm=["upysh","webrepl_setup","http_client","http_client_ssl","http_server","http_server_ssl"]
  self.excl=["webrepl","_webrepl","port_diag","example_sub_led.py","example_pub_button.py"]
  self.mods=['_thread','ak8963','apa102','apa106','array','binascii','btree','bluetooth','builtins','cmath','collections','crypto','curl','dht','display','ds18x20','errno','esp','esp32','flashbdev','framebuf','freesans20','functools','gc','gsm','hashlib','heapq','inisetup','io','json','logging','lwip','machine','math','microWebSocket','microWebSrv','microWebTemplate','micropython','mpu6500','mpu9250','neopixel','network','ntptime','onewire','os','port_diag','pycom','pye','random','re','requests','select','socket','ssd1306','ssh','ssl','struct','sys','time','tpcalib','ubinascii','ucollections','ucryptolib','uctypes','uerrno','uhashlib','uheapq','uio','ujson','umqtt/robust','umqtt/simple','uos','upip','upip_utarfile','urandom','ure','urequests','urllib/urequest','uselect','usocket','ussl','ustruct','utime','utimeq','uwebsocket','uzlib','websocket','websocket_helper','writer','ymodem','zlib','pycom','crypto','pyb','stm','pycopy']
 @staticmethod
 def _info():
  i={'name':sys.implementation.name,'release':'0.0.0','version':'0.0.0','build':'','family':sys.implementation.name,'platform':sys.platform,'port':sys.platform,'ver':''}
  try:
   i['release']=".".join([str(i)for i in sys.implementation.version])
   i['version']=i['release']
   i['name']=sys.implementation.name
  except AttributeError:
   pass
  if sys.platform not in('unix','win32','esp8266'):
   try:
    u=os.uname()
    i['release']=u.release
    if ' on ' in u.version:
     s=u.version.split('on ')[0]
     try:
      i['build']=s.split('-')[1]
     except IndexError:
      pass
   except(IndexError,AttributeError):
    pass
  try:
   from pycopy import const
   i['family']='pycopy'
   del const
  except(ImportError,KeyError):
   pass
  if i['platform']=='esp32_LoBo':
   i['family']='loboris'
   i['port']='esp32'
  i['ver']='v'+i['release']
  if i['family']!='loboris':
   if i['release']>='1.10.0' and i['release'].endswith('.0'):
    i['ver']=i['release'][:-2]
   else:
    i['ver']=i['release']
   if i['build']!='':
    i['ver']+='-'+i['build']
  return i
 def get_obj_attributes(self,obj:object):
  result=[]
  errors=[]
  name=None
  for name in dir(obj):
   try:
    val=getattr(obj,name)
    result.append((name,repr(val),repr(type(val)),val))
   except AttributeError as e:
    errors.append("Couldn't get attribute '{}' from object '{}', Err: {}".format(name,obj,e))
  gc.collect()
  return result,errors
 def add_modules(self,modules:list):
  self.mods=sorted(set(self.mods)|set(modules))
 def create_all_stubs(self):
  self.mods=[m for m in self.mods if '/' in m]+[m for m in self.mods if '/' not in m]
  gc.collect()
  for mod_nm in self.mods:
   if mod_nm.startswith("_")and mod_nm!='_thread':
    continue
   if mod_nm in self.prblm:
    continue
   if mod_nm in self.excl:
    continue
   file_name="{}/{}.py".format(self.path,mod_nm.replace(".","/"))
   gc.collect()
   m1=gc.mem_free()
   print("Stub module: {:<20} to file: {:<55} mem:{:>5}".format(mod_nm,file_name,m1))
   try:
    self.create_module_stub(mod_nm,file_name)
   except OSError:
    pass
   gc.collect()
 def create_module_stub(self,mod_nm:str,file_name:str=None):
  if mod_nm.startswith("_")and mod_nm!='_thread':
   return
  if mod_nm in self.prblm:
   return
  if '/' in mod_nm:
   self.ensure_folder(file_name)
   mod_nm=mod_nm.replace('/','.')
  if file_name is None:
   file_name=mod_nm.replace('.','_')+".py"
  failed=False
  new_mod=None
  try:
   new_mod=__import__(mod_nm,None,None,('*'))
  except ImportError:
   failed=True
   if not '.' in mod_nm:
    return
  if failed and '.' in mod_nm:
   levels=mod_nm.split('.')
   for n in range(1,len(levels)):
    par_nm=".".join(levels[0:n])
    try:
     parent=__import__(par_nm)
     del parent
    except(ImportError,KeyError):
     pass
   try:
    new_mod=__import__(mod_nm,None,None,('*'))
   except ImportError:
    return
  with open(file_name,"w")as fp:
   s="\"\"\"\nModule: '{0}' on {1}\n\"\"\"\n# MCU: {2}\n# Stubber: {3}\n".format(mod_nm,self._fwid,self.info,stbr_v)
   fp.write(s)
   self.write_object_stub(fp,new_mod,mod_nm,"")
   self._report.append({"module":mod_nm,"file":file_name})
  if not mod_nm in["os","sys","logging","gc","createstubs"]:
   try:
    del new_mod
   except(OSError,KeyError):
    pass
   for m in sys.modules:
    if not m in["os","sys","logging","gc","createstubs"]:
     try:
      del sys.modules[mod_nm]
     except KeyError:
      pass
   gc.collect()
 def write_object_stub(self,fp,object_expr:object,obj_name:str,indent:str):
  if object_expr in self.prblm:
   return
  items,errors=self.get_obj_attributes(object_expr)
  for name,rep,typ,obj in sorted(items,key=lambda x:x[0]):
   if name.startswith("__"):
    continue
   resetWDT()
   sleep_us(1)
   if typ in["<class 'function'>","<class 'bound_method'>"]:
    s=indent+"def "+name+"():\n" 
    s+=indent+"    pass\n\n"
    fp.write(s)
   elif typ in["<class 'str'>","<class 'int'>","<class 'float'>"]:
    s=indent+name+" = "+rep+"\n"
    fp.write(s)
   elif typ=="<class 'type'>" and indent=="":
    s="\n"+indent+"class "+name+":\n" 
    s+=indent+"    ''\n"
    fp.write(s)
    self.write_object_stub(fp,obj,"{0}.{1}".format(obj_name,name),indent+"    ")
   else:
    fp.write(indent+name+" = None\n")
  del items
  del errors
  try:
   del name,rep,typ,obj 
  except(OSError,KeyError):
   pass
 def clean(self,path:str=None):
  if path is None:
   path=self.path
  print("Clean/remove files in folder: {}".format(path))
  try:
   items=os.listdir(path)
  except(OSError,AttributeError):
   return
  for fn in items:
   try:
    item="{}/{}".format(path,fn)
    os.remove(item)
   except OSError:
    try:
     self.clean(item)
     os.rmdir(item)
    except OSError:
     pass
 def report(self,filename:str="modules.json"):
  f_name="{}/{}".format(self.path,filename)
  gc.collect()
  try:
   with open(f_name,'w')as f:
    f.write('{')
    f.write(dumps({'firmware':self.info})[1:-1])
    f.write(',')
    f.write(dumps({'stubber':{'version':stbr_v}})[1:-1])
    f.write(',')
    f.write('"modules" :[')
    start=True
    for n in self._report:
     if start:
      start=False
     else:
      f.write(',')
     f.write(dumps(n))
    f.write(']}')
  except OSError:
   pass
 def ensure_folder(self,path:str):
  i=start=0
  while i!=-1:
   i=path.find('/',start)
   if i!=-1:
    if i==0:
     p=path[0]
    else:
     p=path[0:i]
    try:
     _=os.stat(p)
    except OSError as e:
     if e.args[0]==ENOENT:
      try:
       os.mkdir(p)
      except OSError as e2:
       raise e2
     else:
      raise e
   start=i+1
def get_root()->str:
 try:
  r="/flash"
  _=os.stat(r)
 except OSError as e:
  if e.args[0]==ENOENT:
   try:
    r=os.getcwd()
   except:
    r='.'
  else:
   r='/'
 return r
def flat(s):
 chars=" .()/\\:$"
 for c in chars:
  s=s.replace(c,"_")
 return s
def show_help():
 sys.exit(1)
def get_param()->str:
 path=None
 if len(sys.argv)==3:
  cmd=(sys.argv[1]).lower()
  if cmd in('--path','-p'):
   path=sys.argv[2]
  else:
   show_help()
 elif len(sys.argv)>=2:
  show_help()
 return path
def _log_mem(start_free):
 gc.collect()
 free=gc.mem_free()
 used= start_free-free
 print('start free:{:,}, end: {:,}, used {:,}'.format(start_free,free,used))
 with open('./memory.csv','a')as file:
  file.write('{},{},{},{}\n'.format(start_free,free,used,sys.platform))
def main():
 try:
  logging.basicConfig(level=logging.INFO)
 except NameError:
  pass
 stubber=Stubber()
 stubber.clean()
 stubber.create_all_stubs()
 stubber.report()
 _log_mem(stubber.init_mem)
main()
