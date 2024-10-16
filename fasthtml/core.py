"""The `FastHTML` subclass of `Starlette`, along with the `RouterX` and `RouteX` classes it automatically uses."""

# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/api/00_core.ipynb.

# %% auto 0
__all__ = ['empty', 'htmx_hdrs', 'fh_cfg', 'htmx_resps', 'htmx_exts', 'htmxsrc', 'htmxwssrc', 'fhjsscr', 'htmxctsrc', 'surrsrc',
           'scopesrc', 'viewport', 'charset', 'all_meths', 'parsed_date', 'snake2hyphens', 'HtmxHeaders', 'HttpHeader',
           'HtmxResponseHeaders', 'form2dict', 'parse_form', 'flat_xt', 'Beforeware', 'EventStream', 'signal_shutdown',
           'WS_RouteX', 'uri', 'decode_uri', 'flat_tuple', 'Redirect', 'RouteX', 'RouterX', 'get_key', 'def_hdrs',
           'FastHTML', 'serve', 'Client', 'cookie', 'reg_re_param', 'MiddlewareBase', 'FtResponse', 'unqid', 'Pusher']

# %% ../nbs/api/00_core.ipynb
import json,uuid,inspect,types,uvicorn,signal,asyncio,threading

from fastcore.utils import *
from fastcore.xml import *
from fastcore.meta import use_kwargs_dict

from types import UnionType, SimpleNamespace as ns, GenericAlias
from typing import Optional, get_type_hints, get_args, get_origin, Union, Mapping, TypedDict, List, Any
from datetime import datetime,date
from dataclasses import dataclass,fields
from collections import namedtuple
from inspect import isfunction,ismethod,Parameter,get_annotations
from functools import wraps, partialmethod, update_wrapper
from http import cookies
from urllib.parse import urlencode, parse_qs, quote, unquote
from copy import copy,deepcopy
from warnings import warn
from dateutil import parser as dtparse
from httpx import ASGITransport, AsyncClient
from anyio import from_thread
from uuid import uuid4
from base64 import b85encode,b64encode

from .starlette import *

empty = Parameter.empty

# %% ../nbs/api/00_core.ipynb
def _sig(f): return signature_ex(f, True)

# %% ../nbs/api/00_core.ipynb
def parsed_date(s:str):
    "Convert `s` to a datetime"
    return dtparse.parse(s)

# %% ../nbs/api/00_core.ipynb
def snake2hyphens(s:str):
    "Convert `s` from snake case to hyphenated and capitalised"
    s = snake2camel(s)
    return camel2words(s, '-')

# %% ../nbs/api/00_core.ipynb
htmx_hdrs = dict(
    boosted="HX-Boosted",
    current_url="HX-Current-URL",
    history_restore_request="HX-History-Restore-Request",
    prompt="HX-Prompt",
    request="HX-Request",
    target="HX-Target",
    trigger_name="HX-Trigger-Name",
    trigger="HX-Trigger")

@dataclass
class HtmxHeaders:
    boosted:str|None=None; current_url:str|None=None; history_restore_request:str|None=None; prompt:str|None=None
    request:str|None=None; target:str|None=None; trigger_name:str|None=None; trigger:str|None=None
    def __bool__(self): return any(hasattr(self,o) for o in htmx_hdrs)

def _get_htmx(h):
    res = {k:h.get(v.lower(), None) for k,v in htmx_hdrs.items()}
    return HtmxHeaders(**res)

# %% ../nbs/api/00_core.ipynb
def _mk_list(t, v): return [t(o) for o in v]

# %% ../nbs/api/00_core.ipynb
fh_cfg = AttrDict(indent=True)

# %% ../nbs/api/00_core.ipynb
def _fix_anno(t):
    "Create appropriate callable type for casting a `str` to type `t` (or first type in `t` if union)"
    origin = get_origin(t)
    if origin is Union or origin is UnionType or origin in (list,List):
        t = first(o for o in get_args(t) if o!=type(None))
    d = {bool: str2bool, int: str2int, date: str2date, UploadFile: noop}
    res = d.get(t, t)
    if origin in (list,List): return partial(_mk_list, res)
    return lambda o: res(o[-1]) if isinstance(o,(list,tuple)) else res(o)

# %% ../nbs/api/00_core.ipynb
def _form_arg(k, v, d):
    "Get type by accessing key `k` from `d`, and use to cast `v`"
    if v is None: return
    if not isinstance(v, (str,list,tuple)): return v
    # This is the type we want to cast `v` to
    anno = d.get(k, None)
    if not anno: return v
    return _fix_anno(anno)(v)

# %% ../nbs/api/00_core.ipynb
@dataclass
class HttpHeader: k:str;v:str

# %% ../nbs/api/00_core.ipynb
def _to_htmx_header(s):
    return 'HX-' + s.replace('_', '-').title()

htmx_resps = dict(location=None, push_url=None, redirect=None, refresh=None, replace_url=None,
                 reswap=None, retarget=None, reselect=None, trigger=None, trigger_after_settle=None, trigger_after_swap=None)

# %% ../nbs/api/00_core.ipynb
@use_kwargs_dict(**htmx_resps)
def HtmxResponseHeaders(**kwargs):
    "HTMX response headers"
    res = tuple(HttpHeader(_to_htmx_header(k), v) for k,v in kwargs.items())
    return res[0] if len(res)==1 else res

# %% ../nbs/api/00_core.ipynb
def _annotations(anno):
    "Same as `get_annotations`, but also works on namedtuples"
    if is_namedtuple(anno): return {o:str for o in anno._fields}
    return get_annotations(anno)

# %% ../nbs/api/00_core.ipynb
def _is_body(anno): return issubclass(anno, (dict,ns)) or _annotations(anno)

# %% ../nbs/api/00_core.ipynb
def _formitem(form, k):
    "Return single item `k` from `form` if len 1, otherwise return list"
    o = form.getlist(k)
    return o[0] if len(o) == 1 else o if o else None

# %% ../nbs/api/00_core.ipynb
def form2dict(form: FormData) -> dict:
    "Convert starlette form data to a dict"
    return {k: _formitem(form, k) for k in form}

# %% ../nbs/api/00_core.ipynb
async def parse_form(req: Request) -> FormData:
    "Starlette errors on empty multipart forms, so this checks for that situation"
    ctype = req.headers.get("Content-Type", "")
    if not ctype.startswith("multipart/form-data"): return await req.form()
    try: boundary = ctype.split("boundary=")[1].strip()
    except IndexError: raise HTTPException(400, "Invalid form-data: no boundary")
    min_len = len(boundary) + 6
    clen = int(req.headers.get("Content-Length", "0"))
    if clen <= min_len: return FormData()
    return await req.form()

# %% ../nbs/api/00_core.ipynb
async def _from_body(req, p):
    anno = p.annotation
    # Get the fields and types of type `anno`, if available
    d = _annotations(anno)
    if req.headers.get('content-type', None)=='application/json': data = await req.json()
    else: data = form2dict(await parse_form(req))
    if req.query_params: data = {**data, **dict(req.query_params)}
    cargs = {k: _form_arg(k, v, d) for k, v in data.items() if not d or k in d}
    return anno(**cargs)

# %% ../nbs/api/00_core.ipynb
async def _find_p(req, arg:str, p:Parameter):
    "In `req` find param named `arg` of type in `p` (`arg` is ignored for body types)"
    anno = p.annotation
    # If there's an annotation of special types, return object of that type
    # GenericAlias is a type of typing for iterators like list[int] that is not a class
    if isinstance(anno, type) and not isinstance(anno, GenericAlias):
        if issubclass(anno, Request): return req
        if issubclass(anno, HtmxHeaders): return _get_htmx(req.headers)
        if issubclass(anno, Starlette): return req.scope['app']
        if _is_body(anno): return await _from_body(req, p)
    # If there's no annotation, check for special names
    if anno is empty:
        if 'request'.startswith(arg.lower()): return req
        if 'session'.startswith(arg.lower()): return req.scope.get('session', {})
        if arg.lower()=='scope': return dict2obj(req.scope)
        if arg.lower()=='auth': return req.scope.get('auth', None)
        if arg.lower()=='htmx': return _get_htmx(req.headers)
        if arg.lower()=='app': return req.scope['app']
        if arg.lower()=='body': return (await req.body()).decode()
        if arg.lower() in ('hdrs','ftrs','bodykw','htmlkw'): return getattr(req, arg.lower())
        if arg!='resp': warn(f"`{arg} has no type annotation and is not a recognised special name, so is ignored.")
        return None
    # Look through path, cookies, headers, query, and body in that order
    res = req.path_params.get(arg, None)
    if res in (empty,None): res = req.cookies.get(arg, None)
    if res in (empty,None): res = req.headers.get(snake2hyphens(arg), None)
    if res in (empty,None): res = req.query_params.getlist(arg)
    if res==[]: res = None
    if res in (empty,None): res = _formitem(await parse_form(req), arg)
    # Raise 400 error if the param does not include a default
    if (res in (empty,None)) and p.default is empty: raise HTTPException(400, f"Missing required field: {arg}")
    # If we have a default, return that if we have no value
    if res in (empty,None): res = p.default
    # We can cast str and list[str] to types; otherwise just return what we have
    if not isinstance(res, (list,str)) or anno is empty: return res
    anno = _fix_anno(anno)
    try: return anno(res)
    except ValueError: raise HTTPException(404, req.url.path) from None

async def _wrap_req(req, params):
    return [await _find_p(req, arg, p) for arg,p in params.items()]

# %% ../nbs/api/00_core.ipynb
def flat_xt(lst):
    "Flatten lists"
    result = []
    if isinstance(lst,(FT,str)): lst=[lst]
    for item in lst:
        if isinstance(item, (list,tuple)): result.extend(item)
        else: result.append(item)
    return tuple(result)

# %% ../nbs/api/00_core.ipynb
class Beforeware:
    def __init__(self, f, skip=None): self.f,self.skip = f,skip or []

# %% ../nbs/api/00_core.ipynb
async def _handle(f, args, **kwargs):
    return (await f(*args, **kwargs)) if is_async_callable(f) else await run_in_threadpool(f, *args, **kwargs)

# %% ../nbs/api/00_core.ipynb
def _find_wsp(ws, data, hdrs, arg:str, p:Parameter):
    "In `data` find param named `arg` of type in `p` (`arg` is ignored for body types)"
    anno = p.annotation
    if isinstance(anno, type):
        if issubclass(anno, HtmxHeaders): return _get_htmx(hdrs)
        if issubclass(anno, Starlette): return ws.scope['app']
    if anno is empty:
        if arg.lower()=='ws': return ws
        if arg.lower()=='scope': return dict2obj(ws.scope)
        if arg.lower()=='data': return data
        if arg.lower()=='htmx': return _get_htmx(hdrs)
        if arg.lower()=='app': return ws.scope['app']
        if arg.lower()=='send': return partial(_send_ws, ws)
        return None
    res = data.get(arg, None)
    if res is empty or res is None: res = hdrs.get(arg, None)
    if res is empty or res is None: res = p.default
    # We can cast str and list[str] to types; otherwise just return what we have
    if not isinstance(res, (list,str)) or anno is empty: return res
    anno = _fix_anno(anno)
    return [anno(o) for o in res] if isinstance(res,list) else anno(res)

def _wrap_ws(ws, data, params):
    hdrs = {k.lower().replace('-','_'):v for k,v in data.pop('HEADERS', {}).items()}
    return [_find_wsp(ws, data, hdrs, arg, p) for arg,p in params.items()]

# %% ../nbs/api/00_core.ipynb
async def _send_ws(ws, resp):
    if not resp: return
    res = to_xml(resp, indent=fh_cfg.indent) if isinstance(resp, (list,tuple,FT)) or hasattr(resp, '__ft__') else resp
    await ws.send_text(res)

def _ws_endp(recv, conn=None, disconn=None):
    cls = type('WS_Endp', (WebSocketEndpoint,), {"encoding":"text"})
    
    async def _generic_handler(handler, ws, data=None):
        wd = _wrap_ws(ws, loads(data) if data else {}, _sig(handler).parameters)
        resp = await _handle(handler, wd)
        if resp: await _send_ws(ws, resp)

    async def _connect(self, ws):
        await ws.accept()
        await _generic_handler(conn, ws)

    async def _disconnect(self, ws, close_code): await _generic_handler(disconn, ws)
    async def _recv(self, ws, data): await _generic_handler(recv, ws, data)

    if    conn: cls.on_connect    = _connect
    if disconn: cls.on_disconnect = _disconnect
    cls.on_receive = _recv
    return cls

# %% ../nbs/api/00_core.ipynb
def EventStream(s):
    "Create a text/event-stream response from `s`"
    return StreamingResponse(s, media_type="text/event-stream")

# %% ../nbs/api/00_core.ipynb
def signal_shutdown():
    event = asyncio.Event()
    def signal_handler(signum, frame):
        event.set()
        signal.signal(signum, signal.SIG_DFL)
        os.kill(os.getpid(), signum)

    for sig in (signal.SIGINT, signal.SIGTERM): signal.signal(sig, signal_handler)
    return event

# %% ../nbs/api/00_core.ipynb
class WS_RouteX(WebSocketRoute):
    def __init__(self, app, path:str, recv, conn:callable=None, disconn:callable=None, *,
                 name=None, middleware=None):
        super().__init__(path, _ws_endp(recv, conn, disconn), name=name, middleware=middleware)
        self.methods = ['WS']

# %% ../nbs/api/00_core.ipynb
def uri(_arg, **kwargs):
    return f"{quote(_arg)}/{urlencode(kwargs, doseq=True)}"

# %% ../nbs/api/00_core.ipynb
def decode_uri(s): 
    arg,_,kw = s.partition('/')
    return unquote(arg), {k:v[0] for k,v in parse_qs(kw).items()}

# %% ../nbs/api/00_core.ipynb
from starlette.convertors import StringConvertor

# %% ../nbs/api/00_core.ipynb
StringConvertor.regex = "[^/]*"  # `+` replaced with `*`

@patch
def to_string(self:StringConvertor, value: str) -> str:
    value = str(value)
    assert "/" not in value, "May not contain path separators"
    # assert value, "Must not be empty"  # line removed due to errors
    return value

# %% ../nbs/api/00_core.ipynb
@patch
def url_path_for(self:HTTPConnection, name: str, **path_params):
    lp = self.scope['app'].url_path_for(name, **path_params)
    return URLPath(f"{self.scope['root_path']}{lp}", lp.protocol, lp.host)

# %% ../nbs/api/00_core.ipynb
_verbs = dict(get='hx-get', post='hx-post', put='hx-post', delete='hx-delete', patch='hx-patch', link='href')

def _url_for(req, t):
    if callable(t): t = t.__routename__
    kw = {}
    if t.find('/')>-1 and (t.find('?')<0 or t.find('/')<t.find('?')): t,kw = decode_uri(t)
    t,m,q = t.partition('?')    
    return f"{req.url_path_for(t, **kw)}{m}{q}"

def _find_targets(req, resp):
    if isinstance(resp, tuple):
        for o in resp: _find_targets(req, o)
    if isinstance(resp, FT):
        for o in resp.children: _find_targets(req, o)
        for k,v in _verbs.items():
            t = resp.attrs.pop(k, None)
            if t: resp.attrs[v] = _url_for(req, t)

def _apply_ft(o):
    if isinstance(o, tuple): o = tuple(_apply_ft(c) for c in o)
    if hasattr(o, '__ft__'): o = o.__ft__()
    if isinstance(o, FT): o.children = tuple(_apply_ft(c) for c in o.children)
    return o

def _to_xml(req, resp, indent):
    resp = _apply_ft(resp)
    _find_targets(req, resp)
    return to_xml(resp, indent)

# %% ../nbs/api/00_core.ipynb
def flat_tuple(o):
    "Flatten lists"
    result = []
    if not isinstance(o,(tuple,list)): o=[o]
    o = list(o)
    for item in o:
        if isinstance(item, (list,tuple)): result.extend(item)
        else: result.append(item)
    return tuple(result)

# %% ../nbs/api/00_core.ipynb
def _xt_cts(req, resp):
    resp = flat_tuple(resp)
    resp = resp + tuple(getattr(req, 'injects', ()))
    http_hdrs,resp = partition(resp, risinstance(HttpHeader))
    http_hdrs = {o.k:str(o.v) for o in http_hdrs}
    tasks,resp = partition(resp, risinstance(BackgroundTask))
    ts = BackgroundTasks()
    for t in tasks: ts.tasks.append(t)
    hdr_tags = 'title','meta','link','style','base'
    titles,bdy = partition(resp, lambda o: getattr(o, 'tag', '') in hdr_tags)
    if resp and 'hx-request' not in req.headers and not any(getattr(o, 'tag', '')=='html' for o in resp):
        if not titles: titles = [Title('FastHTML page')]
        resp = Html(Head(*titles, *flat_xt(req.hdrs)), Body(bdy, *flat_xt(req.ftrs), **req.bodykw), **req.htmlkw)
    return _to_xml(req, resp, indent=fh_cfg.indent), http_hdrs, ts

# %% ../nbs/api/00_core.ipynb
def _xt_resp(req, resp):
    cts,http_hdrs,tasks = _xt_cts(req, resp)
    return HTMLResponse(cts, headers=http_hdrs, background=tasks)

# %% ../nbs/api/00_core.ipynb
def _is_ft_resp(resp): return isinstance(resp, (list,tuple,HttpHeader,FT)) or hasattr(resp, '__ft__')

# %% ../nbs/api/00_core.ipynb
def _resp(req, resp, cls=empty):
    if not resp: resp=()
    if hasattr(resp, '__response__'): resp = resp.__response__(req)
    if cls in (Any,FT): cls=empty
    if isinstance(resp, FileResponse) and not os.path.exists(resp.path): raise HTTPException(404, resp.path)
    if cls is not empty: return cls(resp)
    if isinstance(resp, Response): return resp
    if _is_ft_resp(resp): return _xt_resp(req, resp)
    if isinstance(resp, str): cls = HTMLResponse
    elif isinstance(resp, Mapping): cls = JSONResponse
    else:
        resp = str(resp)
        cls = HTMLResponse
    return cls(resp)

# %% ../nbs/api/00_core.ipynb
class Redirect:
    "Use HTMX or Starlette RedirectResponse as required to redirect to `loc`"
    def __init__(self, loc): self.loc = loc
    def __response__(self, req):
        if 'hx-request' in req.headers: return HtmxResponseHeaders(redirect=self.loc)
        return RedirectResponse(self.loc, status_code=303)

# %% ../nbs/api/00_core.ipynb
async def _wrap_call(f, req, params):
    wreq = await _wrap_req(req, params)
    return await _handle(f, wreq)

# %% ../nbs/api/00_core.ipynb
class RouteX(Route):
    def __init__(self, app, path:str, endpoint, *, methods=None, name=None, include_in_schema=True, middleware=None):
        self.f,self.sig,self._app = endpoint,_sig(endpoint),app
        super().__init__(path, self._endp, methods=methods, name=name, include_in_schema=include_in_schema, middleware=middleware)

    async def _endp(self, req):
        resp = None
        req.injects = []
        req.hdrs,req.ftrs,req.htmlkw,req.bodykw = map(deepcopy, (self._app.hdrs,self._app.ftrs,self._app.htmlkw,self._app.bodykw))
        req.hdrs,req.ftrs = listify(req.hdrs),listify(req.ftrs)
        for b in self._app.before:
            if not resp:
                if isinstance(b, Beforeware): bf,skip = b.f,b.skip
                else: bf,skip = b,[]
                if not any(re.fullmatch(r, req.url.path) for r in skip):
                    resp = await _wrap_call(bf, req, _sig(bf).parameters)
        if not resp: resp = await _wrap_call(self.f, req, self.sig.parameters)
        for a in self._app.after:
            _,*wreq = await _wrap_req(req, _sig(a).parameters)
            nr = a(resp, *wreq)
            if nr: resp = nr
        return _resp(req, resp, self.sig.return_annotation)

# %% ../nbs/api/00_core.ipynb
class RouterX(Router):
    def __init__(self, app, routes=None, redirect_slashes=True, default=None, *, middleware=None):
        self._app = app
        super().__init__(routes, redirect_slashes, default, app.on_startup, app.on_shutdown,
                         lifespan=app.lifespan, middleware=middleware)
    
    def _add_route(self, route):
        route.methods = [m.upper() for m in listify(route.methods)]
        self.routes = [r for r in self.routes if not
                       (r.path==route.path and r.name == route.name and
                        ((route.methods is None) or (set(r.methods) == set(route.methods))))]
        self.routes.append(route)

    def add_route(self, path: str, endpoint: callable, methods=None, name=None, include_in_schema=True):
        route = RouteX(self._app, path, endpoint=endpoint, methods=methods, name=name, include_in_schema=include_in_schema)
        self._add_route(route)

    def add_ws(self, path: str, recv: callable, conn:callable=None, disconn:callable=None, name=None):
        route = WS_RouteX(self._app, path, recv=recv, conn=conn, disconn=disconn, name=name)
        self._add_route(route)

# %% ../nbs/api/00_core.ipynb
htmx_exts = {
    "head-support": "https://unpkg.com/htmx-ext-head-support@2.0.1/head-support.js", 
    "preload": "https://unpkg.com/htmx-ext-preload@2.0.1/preload.js", 
    "class-tools": "https://unpkg.com/htmx-ext-class-tools@2.0.1/class-tools.js", 
    "loading-states": "https://unpkg.com/htmx-ext-loading-states@2.0.0/loading-states.js", 
    "multi-swap": "https://unpkg.com/htmx-ext-multi-swap@2.0.0/multi-swap.js", 
    "path-deps": "https://unpkg.com/htmx-ext-path-deps@2.0.0/path-deps.js", 
    "remove-me": "https://unpkg.com/htmx-ext-remove-me@2.0.0/remove-me.js"
}

# %% ../nbs/api/00_core.ipynb
htmxsrc   = Script(src="https://unpkg.com/htmx.org@next/dist/htmx.min.js")
htmxwssrc = Script(src="https://unpkg.com/htmx-ext-ws/ws.js")
fhjsscr   = Script(src="https://cdn.jsdelivr.net/gh/answerdotai/fasthtml-js@1.0.4/fasthtml.js")
htmxctsrc = Script(src="https://unpkg.com/htmx-ext-transfer-encoding-chunked/transfer-encoding-chunked.js")
surrsrc   = Script(src="https://cdn.jsdelivr.net/gh/answerdotai/surreal@main/surreal.js")
scopesrc  = Script(src="https://cdn.jsdelivr.net/gh/gnat/css-scope-inline@main/script.js")
viewport  = Meta(name="viewport", content="width=device-width, initial-scale=1, viewport-fit=cover")
charset   = Meta(charset="utf-8")

# %% ../nbs/api/00_core.ipynb
def get_key(key=None, fname='.sesskey'):
    if key: return key
    fname = Path(fname)
    if fname.exists(): return fname.read_text()
    key = str(uuid.uuid4())
    fname.write_text(key)
    return key

# %% ../nbs/api/00_core.ipynb
def _list(o): return [] if not o else list(o) if isinstance(o, (tuple,list)) else [o]

# %% ../nbs/api/00_core.ipynb
def _wrap_ex(f, hdrs, ftrs, htmlkw, bodykw):
    async def _f(req, exc):
        req.hdrs,req.ftrs,req.htmlkw,req.bodykw = map(deepcopy, (hdrs, ftrs, htmlkw, bodykw))
        res = await _handle(f, (req, exc))
        return _resp(req, res)
    return _f

# %% ../nbs/api/00_core.ipynb
def _mk_locfunc(f,p):
    class _lf:
        def __init__(self): update_wrapper(self, f)
        def __call__(self, *args, **kw): return f(*args, **kw)
        def rt(self, **kw): return p + (f'?{urlencode(kw)}' if kw else '')
        def __str__(self): return p
    return _lf()

# %% ../nbs/api/00_core.ipynb
def def_hdrs(htmx=True, ct_hdr=False, ws_hdr=False, surreal=True):
    "Default headers for a FastHTML app"
    hdrs = []
    if surreal: hdrs = [surrsrc,scopesrc] + hdrs
    if ws_hdr: hdrs = [htmxwssrc] + hdrs
    if ct_hdr: hdrs = [htmxctsrc] + hdrs
    if htmx: hdrs = [htmxsrc,fhjsscr] + hdrs
    return [charset, viewport] + hdrs

# %% ../nbs/api/00_core.ipynb
class FastHTML(Starlette):
    def __init__(self, debug=False, routes=None, middleware=None, exception_handlers=None,
                 on_startup=None, on_shutdown=None, lifespan=None, hdrs=None, ftrs=None,
                 before=None, after=None, ws_hdr=False, ct_hdr=False,
                 surreal=True, htmx=True, default_hdrs=True, sess_cls=SessionMiddleware,
                 secret_key=None, session_cookie='session_', max_age=365*24*3600, sess_path='/',
                 same_site='lax', sess_https_only=False, sess_domain=None, key_fname='.sesskey',
                 htmlkw=None, **bodykw):
        middleware,before,after = map(_list, (middleware,before,after))
        hdrs,ftrs = listify(hdrs),listify(ftrs)
        htmlkw = htmlkw or {}
        if default_hdrs: hdrs = def_hdrs(htmx, ct_hdr=ct_hdr, ws_hdr=ws_hdr, surreal=surreal) + hdrs
        self.on_startup,self.on_shutdown,self.lifespan,self.hdrs,self.ftrs = on_startup,on_shutdown,lifespan,hdrs,ftrs
        self.before,self.after,self.htmlkw,self.bodykw = before,after,htmlkw,bodykw
        secret_key = get_key(secret_key, key_fname)
        if sess_cls:
            sess = Middleware(sess_cls, secret_key=secret_key,session_cookie=session_cookie,
                              max_age=max_age, path=sess_path, same_site=same_site,
                              https_only=sess_https_only, domain=sess_domain)
            middleware.append(sess)
        exception_handlers = ifnone(exception_handlers, {})
        if 404 not in exception_handlers: 
            def _not_found(req, exc): return  Response('404 Not Found', status_code=404)  
            exception_handlers[404] = _not_found
        excs = {k:_wrap_ex(v, hdrs, ftrs, htmlkw, bodykw) for k,v in exception_handlers.items()}
        super().__init__(debug, routes, middleware=middleware, exception_handlers=excs, on_startup=on_startup, on_shutdown=on_shutdown, lifespan=lifespan)
        self.router = RouterX(self, routes)

    def ws(self, path:str, conn=None, disconn=None, name=None):
        "Add a websocket route at `path`"
        def f(func=None):
            self.router.add_ws(path, func or noop, conn=conn, disconn=disconn, name=name)
            return func
        return f

# %% ../nbs/api/00_core.ipynb
all_meths = 'get post put delete patch head trace options'.split()

@patch
def route(self:FastHTML, path:str=None, methods=None, name=None, include_in_schema=True):
    "Add a route at `path`"
    pathstr = None if callable(path) else path
    def f(func):
        n,fn,p = name,func.__name__,pathstr
        if methods: m = [methods] if isinstance(methods,str) else methods
        elif fn in all_meths and p is not None: m = [fn]
        else: m = ['get','post']
        if not n: n = fn
        if not p: p = '/'+('' if fn=='index' else fn)
        self.router.add_route(p, func, methods=m, name=n, include_in_schema=include_in_schema)
        lf = _mk_locfunc(func, p)
        lf.__routename__ = n
        return lf
    return f(path) if callable(path) else f

# %% ../nbs/api/00_core.ipynb
for o in all_meths: setattr(FastHTML, o, partialmethod(FastHTML.route, methods=o))

# %% ../nbs/api/00_core.ipynb
def serve(
        appname=None, # Name of the module
        app='app', # App instance to be served
        host='0.0.0.0', # If host is 0.0.0.0 will convert to localhost
        port=None, # If port is None it will default to 5001 or the PORT environment variable
        reload=True, # Default is to reload the app upon code changes
        reload_includes:list[str]|str|None=None, # Additional files to watch for changes
        reload_excludes:list[str]|str|None=None # Files to ignore for changes
        ): 
    "Run the app in an async server, with live reload set as the default."
    bk = inspect.currentframe().f_back
    glb = bk.f_globals
    code = bk.f_code
    if not appname:
        if glb.get('__name__')=='__main__': appname = Path(glb.get('__file__', '')).stem
        elif code.co_name=='main' and bk.f_back.f_globals.get('__name__')=='__main__': appname = inspect.getmodule(bk).__name__
    if appname:
        if not port: port=int(os.getenv("PORT", default=5001))
        print(f'Link: http://{"localhost" if host=="0.0.0.0" else host}:{port}')
        uvicorn.run(f'{appname}:{app}', host=host, port=port, reload=reload, reload_includes=reload_includes, reload_excludes=reload_excludes)

# %% ../nbs/api/00_core.ipynb
class Client:
    "A simple httpx ASGI client that doesn't require `async`"
    def __init__(self, app, url="http://testserver"):
        self.cli = AsyncClient(transport=ASGITransport(app), base_url=url)

    def _sync(self, method, url, **kwargs):
        async def _request(): return await self.cli.request(method, url, **kwargs)
        with from_thread.start_blocking_portal() as portal: return portal.call(_request)

for o in ('get', 'post', 'delete', 'put', 'patch', 'options'): setattr(Client, o, partialmethod(Client._sync, o))

# %% ../nbs/api/00_core.ipynb
def cookie(key: str, value="", max_age=None, expires=None, path="/", domain=None, secure=False, httponly=False, samesite="lax",):
    "Create a 'set-cookie' `HttpHeader`"
    cookie = cookies.SimpleCookie()
    cookie[key] = value
    if max_age is not None: cookie[key]["max-age"] = max_age
    if expires is not None:
        cookie[key]["expires"] = format_datetime(expires, usegmt=True) if isinstance(expires, datetime) else expires
    if path is not None: cookie[key]["path"] = path
    if domain is not None: cookie[key]["domain"] = domain
    if secure: cookie[key]["secure"] = True
    if httponly: cookie[key]["httponly"] = True
    if samesite is not None:
        assert samesite.lower() in [ "strict", "lax", "none", ], "must be 'strict', 'lax' or 'none'"
        cookie[key]["samesite"] = samesite
    cookie_val = cookie.output(header="").strip()
    return HttpHeader("set-cookie", cookie_val)

# %% ../nbs/api/00_core.ipynb
def reg_re_param(m, s):
    cls = get_class(f'{m}Conv', sup=StringConvertor, regex=s)
    register_url_convertor(m, cls())

# %% ../nbs/api/00_core.ipynb
# Starlette doesn't have the '?', so it chomps the whole remaining URL
reg_re_param("path", ".*?")
reg_re_param("static", "ico|gif|jpg|jpeg|webm|css|js|woff|png|svg|mp4|webp|ttf|otf|eot|woff2|txt|html|map")

@patch
def static_route_exts(self:FastHTML, prefix='/', static_path='.', exts='static'):
    "Add a static route at URL path `prefix` with files from `static_path` and `exts` defined by `reg_re_param()`"
    @self.route(f"{prefix}{{fname:path}}.{{ext:{exts}}}")
    async def get(fname:str, ext:str): return FileResponse(f'{static_path}/{fname}.{ext}')

# %% ../nbs/api/00_core.ipynb
@patch
def static_route(self:FastHTML, ext='', prefix='/', static_path='.'):
    "Add a static route at URL path `prefix` with files from `static_path` and single `ext` (including the '.')"
    @self.route(f"{prefix}{{fname:path}}{ext}")
    async def get(fname:str): return FileResponse(f'{static_path}/{fname}{ext}')

# %% ../nbs/api/00_core.ipynb
class MiddlewareBase:
    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] not in ["http", "websocket"]:
            await self._app(scope, receive, send)
            return
        return HTTPConnection(scope)

# %% ../nbs/api/00_core.ipynb
class FtResponse:
    "Wrap an FT response with any Starlette `Response`"
    def __init__(self, content, status_code:int=200, headers=None, cls=HTMLResponse, media_type:str|None=None):
        self.content,self.status_code,self.headers = content,status_code,headers
        self.cls,self.media_type = cls,media_type
    
    def __response__(self, req):
        cts,httphdrs,tasks = _xt_cts(req, self.content)
        headers = {**(self.headers or {}), **httphdrs}
        return self.cls(cts, status_code=self.status_code, headers=headers, media_type=self.media_type, background=tasks)

# %% ../nbs/api/00_core.ipynb
def unqid():
    res = b64encode(uuid4().bytes)
    return '_' + res.decode().rstrip('=').translate(str.maketrans('+/', '_-'))

# %% ../nbs/api/00_core.ipynb
def _add_ids(s):
    if not isinstance(s, FT): return
    if not getattr(s, 'id', None): s.id = unqid()
    for c in s.children: _add_ids(c)

# %% ../nbs/api/00_core.ipynb
class Pusher:
    def __init__(self, app, dest_id='_dest', auto_id=True):
        store_attr()
        self._queue = None
        self('')
        @app.route
        def index():
            return Div(id=self.dest_id, hx_trigger='load', hx_ext="ws",
                       ws_send=True, ws_connect="/ws")
    
    @property
    def queue(self):
        self.set_q()
        return self._queue

    def set_q(self):
        if self._queue: return
        self._queue = asyncio.Queue()
        @self.app.ws("/ws")
        async def ws(ws, send):
            try:
                while True:  await send(await self.queue.get())
            except WebSocketDisconnect: self._queue=None

    def __call__(self, *s):
        id = getattr(s[0], 'id', None)
        if not id: s = Div(*s, hx_swap_oob='innerHTML', id=self.dest_id)
        if self.auto_id: _add_ids(s)
        self.queue.put_nowait(s)
