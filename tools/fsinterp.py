#!/usr/bin/env python3
"""
fsinterp -- a small interpreter for the subset of FeatureScript that the
LEOPARD VENT feature's geometry is written in.

Onshape is the only place FeatureScript runs, so this exists to execute the
pure-maths functions of projects/leopard-vent/featurescript/leopard_vent.fs
here, and compare what they produce with tools/fsmirror.py -- which is what
the measurements were taken on. It is not a FeatureScript implementation:

  * It parses the whole file, but only runs top-level `function`s and simple
    `const`s. Feature definitions, annotations, enums' annotations and bound
    specs are skipped or stubbed.
  * Values: numbers, strings, booleans, undefined, arrays and maps (with
    value semantics on every write into one: a[i] = v, m.k = v, a[i].k = v),
    Vectors (with FeatureScript's operators), enums and functions. Units are
    plain multipliers: millimeter = 1, degree = pi/180, radian = 1 -- enough
    for maths written in millimetres; so atan2 here returns plain radians.
  * Built-ins: the std functions that file's maths calls, and no others.
    Anything else is an error, which is the point -- a typo in a function
    name fails here instead of in Onshape.

    fsinterp.py FILE.fs FUNCTION [JSON-ARGS]      call one function
"""

from __future__ import annotations

import json
import math
import re
import sys

# ---------------------------------------------------------------- tokens

TOKEN = re.compile(r"""
    (?P<ws>\s+|//[^\n]*|/\*.*?\*/)
  | (?P<num>\d+\.\d*(?:[eE][-+]?\d+)?|\d*\.\d+(?:[eE][-+]?\d+)?|\d+(?:[eE][-+]?\d+)?)
  | (?P<str>"(?:\\.|[^"\\])*")
  | (?P<id>[A-Za-z_][A-Za-z_0-9]*)
  | (?P<op>==|!=|<=|>=|&&|\|\||\+=|-=|\*=|/=|->|[-+*/%<>=!?:;,.()\[\]{}~^@])
""", re.S | re.X)


def tokenize(src):
    out, pos = [], 0
    while pos < len(src):
        m = TOKEN.match(src, pos)
        if not m:
            raise SyntaxError(f"bad character {src[pos]!r} at line {src.count(chr(10), 0, pos) + 1}")
        pos = m.end()
        kind = m.lastgroup
        if kind == "ws":
            continue
        line = src.count("\n", 0, m.start()) + 1
        val = m.group(kind)
        if kind == "num":
            out.append(("num", float(val), line))
        elif kind == "str":
            out.append(("str", json.loads(val), line))
        else:
            out.append((kind, val, line))
    out.append(("eof", None, 0))
    return out


# ---------------------------------------------------------------- values

class Vec(tuple):
    def __add__(s, o): return Vec(a + b for a, b in zip(s, _vec(o)))
    def __sub__(s, o): return Vec(a - b for a, b in zip(s, _vec(o)))
    def __mul__(s, k):
        if isinstance(k, Vec):
            return Vec(a * b for a, b in zip(s, k))
        return Vec(a * k for a in s)
    __rmul__ = __mul__
    def __truediv__(s, k): return Vec(a / k for a in s)
    def __neg__(s): return Vec(-a for a in s)


def _vec(o):
    if not isinstance(o, Vec):
        raise TypeError(f"vector arithmetic with a non-vector {o!r}")
    return o


class EnumVal:
    def __init__(self, enum, name):
        self.enum, self.name = enum, name
    def __repr__(self): return f"{self.enum}.{self.name}"


class FsError(Exception):
    pass


class Thrown(Exception):
    def __init__(self, value):
        self.value = value


class Return(Exception):
    def __init__(self, value):
        self.value = value


class Break(Exception):
    pass


class Continue(Exception):
    pass


# Type annotations are checked as Onshape checks them at run time: a value
# that fails a parameter's `is T`, or a function's `returns T`, is an error.
# Types that only Onshape values carry (Context, Sketch, Query, ...) are not
# modelled and pass.
def type_ok(v, t):
    if t == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    if t == "boolean":
        return isinstance(v, bool)
    if t == "string":
        return isinstance(v, str)
    if t == "map":
        return isinstance(v, dict)
    if t == "array":
        return isinstance(v, (list, tuple))
    if t == "Vector":
        return isinstance(v, (list, tuple)) and len(v) >= 1 and all(
            isinstance(x, (int, float)) and not isinstance(x, bool) for x in v)
    if t == "function":
        return callable(v)
    if t[:1].isupper() and t.startswith("Leopard"):
        return isinstance(v, EnumVal) and v.enum == t
    return True


class Func:
    def __init__(self, name, params, body, closure, interp, rtype=None):
        self.name, self.params, self.body, self.closure, self.interp = name, params, body, closure, interp
        self.rtype = rtype

    def __call__(self, *args):
        if len(args) != len(self.params):
            raise FsError(f"{self.name}: expected {len(self.params)} arguments, got {len(args)}")
        env = Env(self.closure)
        for (p, t), a in zip(self.params, args):
            if t is not None and not type_ok(a, t):
                raise FsError(f"{self.name}: argument {p} is not {t}: {a!r:.80}")
            env.declare(p, a)
        value = None
        try:
            self.interp.exec_block(self.body, env)
        except Return as r:
            value = r.value
        if self.rtype is not None and not type_ok(value, self.rtype):
            raise FsError(f"{self.name}: returned {value!r:.80}, not {self.rtype}")
        return value


class Env:
    def __init__(self, parent=None):
        self.vars, self.parent = {}, parent

    def declare(self, name, value):
        self.vars[name] = value

    def find(self, name):
        e = self
        while e is not None:
            if name in e.vars:
                return e
            e = e.parent
        raise FsError(f"undefined name {name!r}")

    def get(self, name):
        return self.find(name).vars[name]

    def set(self, name, value):
        self.find(name).vars[name] = value


# ---------------------------------------------------------------- parser
#
# Statements and expressions become small tuples; the interpreter walks them.

# Words FeatureScript reserves, so they cannot name a variable, parameter or
# function. `box` is the one that bit: it is FeatureScript's mutable-reference
# type (`new box(x)`), and Onshape rejected `const box = ...` with
# "mismatched input 'box' expecting ID". Known reserved words, not
# necessarily all of them.
RESERVED = {
    "annotation", "as", "box", "break", "case", "catch", "const", "continue", "default",
    "else", "enum", "export", "false", "for", "function", "if", "import", "in", "inf",
    "is", "new", "operator", "precondition", "predicate", "return", "returns", "silent",
    "switch", "throw", "true", "try", "type", "typecheck", "undefined", "var", "while",
}


class Parser:
    def __init__(self, tokens):
        self.t, self.i = tokens, 0

    def peek(self, k=0): return self.t[self.i + k]
    def at(self, val): return self.peek()[1] == val and self.peek()[0] in ("op", "id")

    def take(self, val=None):
        tok = self.t[self.i]
        if val is not None and not (tok[1] == val and tok[0] in ("op", "id")):
            raise SyntaxError(f"line {tok[2]}: expected {val!r}, got {tok[1]!r}")
        self.i += 1
        return tok

    def ident(self):
        tok = self.take()
        if tok[0] != "id":
            raise SyntaxError(f"line {tok[2]}: expected a name, got {tok[1]!r}")
        return tok[1]

    def new_name(self):
        """A name being declared: a variable, parameter or function."""
        tok = self.peek()
        name = self.ident()
        if name in RESERVED:
            raise SyntaxError(f"line {tok[2]}: {name!r} is a reserved word in FeatureScript")
        return name

    def skip_balanced(self, open_, close):
        depth = 0
        while True:
            tok = self.take()
            if tok[1] == open_ and tok[0] == "op":
                depth += 1
            elif tok[1] == close and tok[0] == "op":
                depth -= 1
                if depth == 0:
                    return

    # top level -------------------------------------------------------
    def program(self):
        items = []
        while self.peek()[0] != "eof":
            if self.at("FeatureScript"):
                while not self.at(";"):
                    self.take()
                self.take(";")
            elif self.at("import"):
                while not self.at(";"):
                    self.take()
                self.take(";")
            elif self.at("annotation"):
                self.take()
                self.skip_balanced("{", "}")
            elif self.at("export"):
                self.take()
            elif self.at("enum"):
                self.take()
                name = self.ident()
                self.take("{")
                values = []
                while not self.at("}"):
                    if self.at("annotation"):
                        self.take()
                        self.skip_balanced("{", "}")
                    elif self.at(","):
                        self.take()
                    else:
                        values.append(self.ident())
                self.take("}")
                items.append(("enum", name, values))
            elif self.at("const"):
                self.take()
                name = self.ident()
                self.take("=")
                if self.at("defineFeature"):
                    self.take()
                    self.skip_balanced("(", ")")
                    self.take(";")
                    continue
                expr = self.expr()
                self.take(";")
                items.append(("const", name, expr))
            elif self.at("function"):
                self.take()
                name = self.new_name()
                params = self.params()
                rtype = None
                if self.at("returns"):
                    self.take()
                    rtype = self.ident()
                body = self.block()
                items.append(("function", name, params, body, rtype))
            else:
                tok = self.peek()
                raise SyntaxError(f"line {tok[2]}: unexpected {tok[1]!r} at top level")
        return items

    def params(self):
        self.take("(")
        ps = []
        while not self.at(")"):
            name, ptype = self.new_name(), None
            if self.at("is"):
                self.take()
                ptype = self.ident()
            ps.append((name, ptype))
            if self.at(","):
                self.take()
        self.take(")")
        return ps

    # statements --------------------------------------------------------
    def block(self):
        self.take("{")
        stmts = []
        while not self.at("}"):
            stmts.append(self.statement())
        self.take("}")
        return stmts

    def statement(self):
        line = self.peek()[2]
        if self.at("{"):
            return ("block", self.block())
        if self.at("var") or self.at("const"):
            self.take()
            name = self.new_name()
            expr = None
            if self.at("="):
                self.take()
                expr = self.expr()
            self.take(";")
            return ("decl", name, expr, line)
        if self.at("if"):
            self.take()
            self.take("(")
            cond = self.expr()
            self.take(")")
            then = self.statement()
            other = None
            if self.at("else"):
                self.take()
                other = self.statement()
            return ("if", cond, then, other)
        if self.at("while"):
            self.take()
            self.take("(")
            cond = self.expr()
            self.take(")")
            return ("while", cond, self.statement())
        if self.at("for"):
            self.take()
            self.take("(")
            if self.peek()[1] == "var" and self.peek(2)[1] == "in":
                self.take("var")
                name = self.new_name()
                self.take("in")
                seq = self.expr()
                self.take(")")
                return ("forin", name, seq, self.statement())
            init = self.statement()             # a decl, ends with ;
            cond = self.expr()
            self.take(";")
            update = self.simple()
            self.take(")")
            return ("for", init, cond, update, self.statement())
        if self.at("return"):
            self.take()
            expr = None if self.at(";") else self.expr()
            self.take(";")
            return ("return", expr)
        if self.at("break"):
            self.take()
            self.take(";")
            return ("break",)
        if self.at("continue"):
            self.take()
            self.take(";")
            return ("continue",)
        if self.at("throw"):
            self.take()
            expr = self.expr()
            self.take(";")
            return ("throw", expr)
        st = self.simple()
        self.take(";")
        return st

    def simple(self):
        target = self.expr()
        for op in ("=", "+=", "-=", "*=", "/="):
            if self.at(op):
                self.take()
                return ("assign", target, op, self.expr())
        return ("expr", target)

    # expressions -------------------------------------------------------
    def expr(self):
        cond = self.binary(0)
        if self.at("?"):
            self.take()
            a = self.expr()
            self.take(":")
            b = self.expr()
            return ("ternary", cond, a, b)
        return cond

    LEVELS = [["||"], ["&&"], ["==", "!="], ["<", "<=", ">", ">=", "is"], ["+", "-", "~"], ["*", "/", "%"]]

    def binary(self, level):
        if level == len(self.LEVELS):
            return self.unary()
        left = self.binary(level + 1)
        while self.peek()[0] in ("op", "id") and self.peek()[1] in self.LEVELS[level]:
            op = self.take()[1]
            if op == "is":
                left = ("is", left, self.ident())
            else:
                left = ("bin", op, left, self.binary(level + 1))
        return left

    def unary(self):
        if self.at("-"):
            self.take()
            return ("neg", self.unary())
        if self.at("!"):
            self.take()
            return ("not", self.unary())
        return self.postfix(self.primary())

    def postfix(self, node):
        while True:
            if self.at("("):
                self.take()
                args = []
                while not self.at(")"):
                    args.append(self.expr())
                    if self.at(","):
                        self.take()
                self.take(")")
                node = ("call", node, args)
            elif self.at("["):
                self.take()
                idx = self.expr()
                self.take("]")
                node = ("index", node, idx)
            elif self.at("."):
                self.take()
                node = ("member", node, self.ident())
            elif self.at("as"):
                self.take()
                self.ident()
            else:
                return node

    def primary(self):
        tok = self.peek()
        if tok[0] == "num":
            self.take()
            return ("lit", tok[1])
        if tok[0] == "str":
            self.take()
            return ("lit", tok[1])
        if self.at("("):
            self.take()
            e = self.expr()
            self.take(")")
            return e
        if self.at("["):
            self.take()
            items = []
            while not self.at("]"):
                items.append(self.expr())
                if self.at(","):
                    self.take()
            self.take("]")
            return ("array", items)
        if self.at("{"):
            self.take()
            pairs = []
            while not self.at("}"):
                if self.at("("):
                    self.take()
                    key = self.expr()
                    self.take(")")
                else:
                    key = self.primary()
                self.take(":")
                pairs.append((key, self.expr()))
                if self.at(","):
                    self.take()
            self.take("}")
            return ("map", pairs)
        if self.at("function"):
            self.take()
            params = self.params()
            return ("lambda", params, self.block())
        if tok[0] == "id":
            self.take()
            if tok[1] == "true":
                return ("lit", True)
            if tok[1] == "false":
                return ("lit", False)
            if tok[1] == "undefined":
                return ("lit", None)
            return ("name", tok[1], tok[2])
        raise SyntaxError(f"line {tok[2]}: unexpected {tok[1]!r}")


# ---------------------------------------------------------------- interpreter

def _num(x):
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise FsError(f"expected a number, got {x!r}")
    return x


def fs_str(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float) and v.is_integer() and abs(v) < 1e15:
        return str(int(v))
    return str(v)


def fs_sort(arr, cmp):
    import functools
    return sorted(arr, key=functools.cmp_to_key(lambda a, b: (lambda r: (r > 0) - (r < 0))(cmp(a, b))))


def fs_min(*a):
    if len(a) == 1:
        return min(a[0])
    return min(a[0], a[1])


def fs_max(*a):
    if len(a) == 1:
        return max(a[0])
    return max(a[0], a[1])


def fs_round_to(v, p):
    f = 10 ** p
    return math.floor(v * f + 0.5) / f


BUILTINS = {
    "vector": lambda *a: Vec(a if len(a) > 1 else a[0]),
    "norm": lambda v: math.sqrt(sum(x * x for x in _vec(v))),
    "normalize": lambda v: (lambda n: Vec(x / n for x in v))(math.sqrt(sum(x * x for x in _vec(v)))),
    "dot": lambda a, b: sum(x * y for x, y in zip(_vec(a), _vec(b))),
    "append": lambda arr, v: list(arr) + [v],
    "size": lambda c: len(c),
    "concatenateArrays": lambda arrs: [x for a in arrs for x in a],
    "subArray": lambda a, s, e=None: list(a[int(s):]) if e is None else list(a[int(s):int(e)]),
    "sort": fs_sort,
    "reverse": lambda a: list(reversed(a)),
    "min": fs_min,
    "max": fs_max,
    "abs": lambda x: abs(_num(x)),
    "sqrt": lambda x: math.sqrt(_num(x)),
    "floor": lambda x: float(math.floor(_num(x))),
    "ceil": lambda x: float(math.ceil(_num(x))),
    "round": lambda x: float(math.floor(_num(x) + 0.5)),
    "clamp": lambda v, lo, hi: min(max(v, lo), hi),
    "sin": lambda a: math.sin(_num(a)),
    "cos": lambda a: math.cos(_num(a)),
    "acos": lambda x: math.acos(_num(x)),
    "atan2": lambda y, x: math.atan2(_num(y), _num(x)),   # radians: FeatureScript's comes with units
    "roundToPrecision": fs_round_to,
    "regenError": lambda msg, *rest: {"message": msg},
    "PI": math.pi,
    "inf": math.inf,
    "degree": math.pi / 180,
    "radian": 1.0,
    "millimeter": 1.0,
}


class Interp:
    def __init__(self, src):
        self.globals = Env()
        for k, v in BUILTINS.items():
            self.globals.declare(k, v)
        items = Parser(tokenize(src)).program()
        consts = []
        for it in items:
            if it[0] == "enum":
                self.globals.declare(it[1], {v: EnumVal(it[1], v) for v in it[2]})
            elif it[0] == "function":
                self.globals.declare(it[1], Func(it[1], it[2], it[3], self.globals, self, it[4]))
            elif it[0] == "const":
                consts.append(it)
        for _, name, expr in consts:
            try:
                self.globals.declare(name, self.eval(expr, self.globals))
            except FsError:
                pass                             # bound specs etc.: unit keys we do not model

    def call(self, name, *args):
        return self.globals.get(name)(*args)

    # statements --------------------------------------------------------
    def exec_block(self, stmts, env):
        for s in stmts:
            self.exec(s, env)

    def exec(self, s, env):
        k = s[0]
        if k == "block":
            self.exec_block(s[1], Env(env))
        elif k == "decl":
            env.declare(s[1], None if s[2] is None else self.eval(s[2], env))
        elif k == "assign":
            self.assign(s[1], s[2], self.eval(s[3], env), env)
        elif k == "expr":
            self.eval(s[1], env)
        elif k == "if":
            if self.truth(self.eval(s[1], env)):
                self.exec(s[2], Env(env))
            elif s[3] is not None:
                self.exec(s[3], Env(env))
        elif k == "while":
            while self.truth(self.eval(s[1], env)):
                try:
                    self.exec(s[2], Env(env))
                except Break:
                    break
                except Continue:
                    continue
        elif k == "for":
            loop_env = Env(env)
            self.exec(s[1], loop_env)
            while self.truth(self.eval(s[2], loop_env)):
                try:
                    self.exec(s[4], Env(loop_env))
                except Break:
                    break
                except Continue:
                    pass
                self.exec(s[3], loop_env)
        elif k == "forin":
            seq = self.eval(s[2], env)
            if not isinstance(seq, (list, tuple)):
                raise FsError("for-in over a non-array")
            for v in list(seq):
                inner = Env(env)
                inner.declare(s[1], v)
                try:
                    self.exec(s[3], inner)
                except Break:
                    break
                except Continue:
                    continue
        elif k == "return":
            raise Return(None if s[1] is None else self.eval(s[1], env))
        elif k == "break":
            raise Break()
        elif k == "continue":
            raise Continue()
        elif k == "throw":
            raise Thrown(self.eval(s[1], env))
        else:
            raise FsError(f"unknown statement {k}")

    def assign(self, target, op, value, env):
        if op != "=":
            cur = self.eval(target, env)
            value = self.binop(op[0], cur, value)
        self.store(target, value, env)

    def store(self, target, value, env):
        """x = v, a[i] = v, m.k = v, and any nesting of them (a[i].k[j] = v).
        FeatureScript containers are values: each one on the way down is
        copied before it is written into, and written back in turn."""
        if target[0] == "name":
            env.set(target[1], value)
            return
        if target[0] not in ("index", "member"):
            raise FsError(f"cannot assign to {target}")
        container = self.eval(target[1], env)
        if target[0] == "member":
            if not isinstance(container, dict):
                raise FsError(f"member .{target[2]} of a non-map {container!r:.60}")
            container = dict(container)
            container[target[2]] = value
        elif isinstance(container, dict):
            container = dict(container)
            container[self.eval(target[2], env)] = value
        elif isinstance(container, (list, tuple)) and not isinstance(container, Vec):
            container = list(container)
            key = self.eval(target[2], env)
            i = int(key)
            if key != i or i < 0 or i >= len(container):
                raise FsError(f"index {key} out of range for size {len(container)}")
            container[i] = value
        else:
            raise FsError(f"indexing a {type(container).__name__} to assign")
        self.store(target[1], container, env)

    # expressions -------------------------------------------------------
    def truth(self, v):
        if not isinstance(v, bool):
            raise FsError(f"condition is not a boolean: {v!r}")
        return v

    def binop(self, op, a, b):
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        if op == "/":
            return a / b
        if op == "%":
            return math.fmod(_num(a), _num(b))
        if op == "~":
            return fs_str(a) + fs_str(b)
        if op == "<":
            return a < b
        if op == "<=":
            return a <= b
        if op == ">":
            return a > b
        if op == ">=":
            return a >= b
        if op == "==":
            return a == b
        if op == "!=":
            return a != b
        raise FsError(f"unknown operator {op}")

    def eval(self, n, env):
        k = n[0]
        if k == "lit":
            return n[1]
        if k == "name":
            return env.get(n[1])
        if k == "array":
            return [self.eval(x, env) for x in n[1]]
        if k == "map":
            return {self.eval(kk, env): self.eval(v, env) for kk, v in n[1]}
        if k == "ternary":
            return self.eval(n[2], env) if self.truth(self.eval(n[1], env)) else self.eval(n[3], env)
        if k == "bin":
            op = n[1]
            if op == "&&":
                return self.truth(self.eval(n[2], env)) and self.truth(self.eval(n[3], env))
            if op == "||":
                return self.truth(self.eval(n[2], env)) or self.truth(self.eval(n[3], env))
            return self.binop(op, self.eval(n[2], env), self.eval(n[3], env))
        if k == "neg":
            return -self.eval(n[1], env)
        if k == "not":
            return not self.truth(self.eval(n[1], env))
        if k == "is":
            v = self.eval(n[1], env)
            t = n[2]
            if t == "Vector":
                return isinstance(v, Vec)
            if t == "number":
                return isinstance(v, (int, float)) and not isinstance(v, bool)
            if t in ("Line", "Circle"):
                return isinstance(v, dict) and v.get("__type") == t
            raise FsError(f"cannot test 'is {t}'")
        if k == "call":
            fn = self.eval(n[1], env)
            args = [self.eval(a, env) for a in n[2]]
            if not callable(fn):
                raise FsError(f"calling a non-function {n[1]}")
            return fn(*args)
        if k == "index":
            c = self.eval(n[1], env)
            key = self.eval(n[2], env)
            if isinstance(c, dict):
                return c.get(key)
            if isinstance(c, (list, tuple)):
                i = int(key)
                if key != i or i < 0 or i >= len(c):
                    raise FsError(f"index {key} out of range for size {len(c)}")
                return c[i]
            raise FsError(f"indexing a {type(c).__name__}")
        if k == "member":
            c = self.eval(n[1], env)
            if not isinstance(c, dict):
                raise FsError(f"member .{n[2]} of a non-map {c!r}")
            return c.get(n[2])
        if k == "lambda":
            return Func("<lambda>", n[1], n[2], env, self)
        raise FsError(f"unknown expression {k}")


def to_fs(v):
    """JSON-ish Python value -> interpreter value (2-element number lists become Vectors)."""
    if isinstance(v, (list, tuple)):
        if len(v) in (2, 3) and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v):
            return Vec(float(x) for x in v)
        return [to_fs(x) for x in v]
    if isinstance(v, dict):
        return {k: to_fs(x) for k, x in v.items()}
    if isinstance(v, int) and not isinstance(v, bool):
        return float(v)
    return v


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    it = Interp(open(sys.argv[1]).read())
    args = to_fs(json.loads(sys.argv[3])) if len(sys.argv) > 3 else []
    print(it.call(sys.argv[2], *args))
    return 0


if __name__ == "__main__":
    sys.exit(main())
