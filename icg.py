import sys
import json
import math

# ---------------------------------------------------------------------------
# Phase 4-A: Three-Address Code Generator
# ---------------------------------------------------------------------------
class TACGenerator:
    def __init__(self, ast):
        self.ast         = ast
        self.code        = []
        self.temp_count  = 0
        self.label_count = 0
        self.loop_stack  = []   # (start_label, end_label)

    def new_temp(self):
        self.temp_count += 1
        return f"t{self.temp_count}"

    def new_label(self):
        self.label_count += 1
        return f"L{self.label_count}"

    def emit(self, instr):
        self.code.append(instr)

    def generate(self):
        self.visit(self.ast)
        return self.code

    # ------------------------------------------------------------------
    def visit(self, node):
        if not node:
            return None
        nt = node.get("type")

        if nt == "Program":
            for s in node.get("body", []):
                self.visit(s)

        elif nt in ("IncludeStatement", "UsingStatement"):
            pass

        elif nt == "MainFunction":
            self.emit("main:")
            for p in node.get("params", []):
                self.emit(f"param {p['id']}")
            for s in node.get("body", []):
                self.visit(s)

        elif nt == "FunctionDefinition":
            self.emit(f"{node['name']}:")
            for p in node.get("params", []):
                self.emit(f"param {p['id']}")
            for s in node.get("body", []):
                self.visit(s)
            self.emit("return")

        # ---- Declarations ----------------------------------------
        elif nt == "Declaration":
            vid = node["id"]
            if node.get("value"):
                val = self.visit(node["value"])
                self.emit(f"{vid} = {val}")

        elif nt == "MultiDeclaration":
            for vd in node.get("vars", []):
                if vd.get("value"):
                    val = self.visit(vd["value"])
                    self.emit(f"{vd['id']} = {val}")

        # ---- Assignment ------------------------------------------
        elif nt == "Assignment":
            vid = node["id"]
            op  = node.get("op", "=")
            val = self.visit(node["value"])
            if op == "=":
                self.emit(f"{vid} = {val}")
            else:                       # +=, -=, *=, /=
                arith = op[0]           # '+', '-', '*', '/'
                t = self.new_temp()
                self.emit(f"{t} = {vid} {arith} {val}")
                self.emit(f"{vid} = {t}")

        # ---- Incr/Decr ------------------------------------------
        elif nt == "IncrDecr":
            vid = node["id"]
            op  = node["op"]
            t   = self.new_temp()
            if op == "++":
                self.emit(f"{t} = {vid} + 1")
            else:
                self.emit(f"{t} = {vid} - 1")
            self.emit(f"{vid} = {t}")

        # ---- While ----------------------------------------------
        elif nt == "WhileLoop":
            L_start = self.new_label()
            L_end   = self.new_label()
            self.emit(f"{L_start}:")
            cond = self.visit(node["condition"])
            self.emit(f"ifFalse {cond} goto {L_end}")
            self.loop_stack.append((L_start, L_end))
            for s in node.get("body", []):
                self.visit(s)
            self.loop_stack.pop()
            self.emit(f"goto {L_start}")
            self.emit(f"{L_end}:")

        # ---- For ------------------------------------------------
        elif nt == "ForLoop":
            self.visit(node.get("init"))
            L_start = self.new_label()
            L_update = self.new_label()
            L_end   = self.new_label()
            self.emit(f"{L_start}:")
            cond = self.visit(node["condition"])
            self.emit(f"ifFalse {cond} goto {L_end}")
            self.loop_stack.append((L_update, L_end))
            for s in node.get("body", []):
                self.visit(s)
            self.emit(f"{L_update}:")
            self.visit(node.get("update"))
            self.loop_stack.pop()
            self.emit(f"goto {L_start}")
            self.emit(f"{L_end}:")

        # ---- Do-While -------------------------------------------
        elif nt == "DoWhile":
            L_start = self.new_label()
            L_cond  = self.new_label()
            L_end   = self.new_label()
            self.emit(f"{L_start}:")
            self.loop_stack.append((L_cond, L_end))
            for s in node.get("body", []):
                self.visit(s)
            self.loop_stack.pop()
            self.emit(f"{L_cond}:")
            cond = self.visit(node["condition"])
            self.emit(f"ifTrue {cond} goto {L_start}")
            self.emit(f"{L_end}:")

        # ---- If / Else ------------------------------------------
        elif nt == "IfStatement":
            cond    = self.visit(node["condition"])
            L_else  = self.new_label()
            L_end   = self.new_label()
            self.emit(f"ifFalse {cond} goto {L_else}")
            for s in node.get("body", []):
                self.visit(s)
            self.emit(f"goto {L_end}")
            self.emit(f"{L_else}:")
            eb = node.get("else_body")
            if eb:
                if isinstance(eb, list):
                    for s in eb:
                        self.visit(s)
                else:
                    self.visit(eb)
            self.emit(f"{L_end}:")

        # ---- Jump ----------------------------------------------
        elif nt == "BreakStatement":
            if self.loop_stack:
                self.emit(f"goto {self.loop_stack[-1][1]}")

        elif nt == "ContinueStatement":
            if self.loop_stack:
                self.emit(f"goto {self.loop_stack[-1][0]}")

        elif nt == "ReturnStatement":
            if node.get("value"):
                val = self.visit(node["value"])
                self.emit(f"return {val}")
            else:
                self.emit("return")

        # ---- I/O -----------------------------------------------
        elif nt == "CinStatement":
            for vid in node.get("ids", []):
                self.emit(f"read {vid}")

        elif nt == "CoutStatement":
            for item in node.get("items", []):
                kind = item.get("kind")
                if kind == "expr":
                    val = self.visit(item["value"])
                    self.emit(f"print {val}")
                elif kind == "string":
                    self.emit(f"print {item['value']}")
                elif kind == "endl":
                    self.emit("print \\n")

        # ---- Expressions ----------------------------------------
        elif nt in ("Condition", "LogicalExpr"):
            left  = self.visit(node.get("left"))
            right = self.visit(node.get("right"))
            op    = node.get("operator") or node.get("op")
            t     = self.new_temp()
            self.emit(f"{t} = {left} {op} {right}")
            return t

        elif nt == "BinaryExpression":
            left  = self.visit(node.get("left"))
            right = self.visit(node.get("right"))
            op    = node["operator"]
            t     = self.new_temp()
            self.emit(f"{t} = {left} {op} {right}")
            return t

        elif nt == "UnaryExpr":
            op = node["op"]
            operand = self.visit(node["operand"])
            t = self.new_temp()
            if op == "neg":
                self.emit(f"{t} = neg {operand}")
            else:
                self.emit(f"{t} = ! {operand}")
            return t

        elif nt == "FunctionCall":
            args = [self.visit(a) for a in node.get("args", [])]
            t    = self.new_temp()
            self.emit(f"{t} = call {node['name']}({', '.join(str(a) for a in args)})")
            return t

        elif nt == "ExprStatement":
            self.visit(node.get("expr"))

        elif nt == "Identifier":
            return node["value"]

        elif nt in ("Number", "FloatNumber"):
            return node["value"]

        elif nt == "StringLiteral":
            return node["value"]

        elif nt == "CharLiteral":
            return node["value"]

        elif nt == "BoolLiteral":
            return "1" if node["value"] else "0"

        return None


# ---------------------------------------------------------------------------
# Phase 4-B: Constant-Folding Optimizer
# ---------------------------------------------------------------------------
class TACOptimizer:
    def __init__(self, code):
        self.code          = code
        self.optimized     = []

    @staticmethod
    def _num(s):
        if isinstance(s, (int, float)):
            return s

        try:
            if "." in str(s):
                return float(s)
            return int(s)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _eval(op, l, r):
        try:
            if op == '+':  return l + r
            if op == '-':  return l - r
            if op == '*':  return l * r
            if op == '/':  return l / r if r != 0 else None
            if op == '%':  return l % r
            if op == '<':  return int(l < r)
            if op == '>':  return int(l > r)
            if op == '<=': return int(l <= r)
            if op == '>=': return int(l >= r)
            if op == '==': return int(l == r)
            if op == '!=': return int(l != r)
        except Exception:
            return None

    def get_used_vars(self, instructions):
        used = set()
        for instr in instructions:
            parts = instr.split()
            if not parts or instr.endswith(':'):
                continue

            if parts[0] == 'print':
                rest = instr[6:].strip()
                if rest != '\\n' and not (rest.startswith('"') and rest.endswith('"')):
                    used.add(rest)
            elif parts[0] == 'return':
                if len(parts) > 1:
                    used.add(parts[1])
            elif parts[0] in ('ifFalse', 'ifTrue'):
                used.add(parts[1])
            elif parts[0] == 'param':
                used.add(parts[1])
            elif '=' in parts:
                left, right = instr.split('=', 1)
                right = right.strip()
                if right.startswith('call '):
                    try:
                        args_str = right.split('(', 1)[1].rsplit(')', 1)[0]
                        for a in args_str.split(','):
                            a = a.strip()
                            if a and self._num(a) is None:
                                used.add(a)
                    except: pass
                else:
                    for p in right.split():
                        if p not in ('neg', '!', '+', '-', '*', '/', '%', '<', '>', '<=', '>=', '==', '!=', '&&', '||'):
                            if self._num(p) is None and not (p.startswith('"') and p.endswith('"')):
                                used.add(p)
        return used

    def optimize(self):
        consts = {}

        for instr in self.code:
            parts = instr.split()
            if not parts:
                continue

            # Label
            if instr.endswith(':'):
                self.optimized.append(instr)
                consts.clear()
                continue

            # goto
            if parts[0] == 'goto':
                self.optimized.append(instr)
                consts.clear()
                continue

            # ifFalse / ifTrue
            if parts[0] in ('ifFalse', 'ifTrue'):
                cvar = parts[1]
                if cvar in consts:
                    cv = consts[cvar]
                    is_true = bool(cv)
                    jump = (parts[0] == 'ifTrue' and is_true) or \
                           (parts[0] == 'ifFalse' and not is_true)
                    if jump:
                        self.optimized.append(f"goto {parts[3]}")
                    # else: skip (dead branch)
                else:
                    self.optimized.append(instr)
                consts.clear()
                continue

            # read / print / return / call / labels
            if parts[0] in ('read', 'print', 'return', 'call', 'main:') or instr.endswith(':'):
                if parts[0] in ('print', 'return') and len(parts) > 1:
                    val = parts[1]
                    resolved = consts.get(val, val)
                    self.optimized.append(f"{parts[0]} {resolved}")
                else:
                    self.optimized.append(instr)
                
                if parts[0] == 'read' and len(parts) > 1:
                    consts.pop(parts[1], None)
                
                # If it's a label or jump-related, clear constants to stay safe
                if instr.endswith(':') or parts[0] in ('call', 'read'):
                    consts.clear()
                continue

            # Assignment:  target = ...
            if '=' in parts and parts[1] == '=':
                target = parts[0]

                if len(parts) == 3:                 # target = val
                    val = parts[2]
                    resolved = consts.get(val, val)
                    self.optimized.append(f"{target} = {resolved}")
                    n = self._num(resolved)
                    if n is not None:
                        consts[target] = n
                    else:
                        consts.pop(target, None)

                elif len(parts) == 4:               # target = op operand  (unary neg / !)
                    op, operand = parts[2], parts[3]
                    operand = consts.get(operand, operand)
                    n = self._num(operand)
                    if n is not None:
                        if op == 'neg':
                            res = -n
                        elif op == '!':
                            res = int(not bool(n))
                        else:
                            res = None
                        if res is not None:
                            self.optimized.append(f"{target} = {res}")
                            consts[target] = res
                            continue
                    self.optimized.append(f"{target} = {op} {operand}")
                    consts.pop(target, None)

                elif len(parts) == 5:               # target = left op right
                    left, op, right = parts[2], parts[3], parts[4]
                    left  = consts.get(left,  left)
                    right = consts.get(right, right)
                    nl, nr = self._num(left), self._num(right)
                    if nl is not None and nr is not None:
                        res = self._eval(op, nl, nr)
                        if res is not None:
                            self.optimized.append(f"{target} = {res}")
                            consts[target] = res
                            continue
                    self.optimized.append(f"{target} = {left} {op} {right}")
                    consts.pop(target, None)

                else:
                    self.optimized.append(instr)
                    consts.pop(target, None)
                continue

            # Anything else
            self.optimized.append(instr)

        # ---------------------------------------------------------
        # Phase 2: Unreachable Code Elimination
        # ---------------------------------------------------------
        reachable = []
        unreachable_mode = False
        for instr in self.optimized:
            if instr.endswith(":"):
                unreachable_mode = False
                reachable.append(instr)
            elif not unreachable_mode:
                reachable.append(instr)
                if instr.startswith("goto ") or instr.startswith("return"):
                    unreachable_mode = True

        # ---------------------------------------------------------
        # Phase 3: Dead Code Elimination (Iterative)
        # ---------------------------------------------------------
        changed = True
        final_optimized = reachable
        while changed:
            changed = False
            used_vars = self.get_used_vars(final_optimized)
            
            new_optimized = []
            for instr in final_optimized:
                keep = True
                parts = instr.split()
                if len(parts) >= 3 and parts[1] == '=':
                    target = parts[0]
                    # Don't eliminate if target is a function call side-effect, just in case
                    if 'call' not in instr and target not in used_vars:
                        keep = False
                        changed = True
                
                if keep:
                    new_optimized.append(instr)
                    
            final_optimized = new_optimized

        self.optimized = final_optimized
        return self.optimized


# ---------------------------------------------------------------------------
# Execution Engine (runs optimised TAC, captures output)
# ---------------------------------------------------------------------------
class TACExecutor:
    """
    Interprets optimised Three-Address Code and returns:
      - program_output : str   (what cout printed)
      - stdin_needed   : bool  (True if the program uses 'read')
    """

    def __init__(self, tac, stdin_values=None):
        self.tac          = tac
        self.env          = {}
        self.output_lines = []
        self.stdin_iter   = iter(stdin_values or [])
        self.max_steps    = 100_000     # guard against infinite loops

    # ------------------------------------------------------------------
    def run(self):
        # Build label index
        labels = {}
        func_boundaries = [] # (start, end)
        
        for i, instr in enumerate(self.tac):
            if instr.endswith(':') and not instr.startswith('if'):
                name = instr[:-1]
                labels[name] = i
                # Find the corresponding return to know where the function ends
                for j in range(i + 1, len(self.tac)):
                    if self.tac[j] == "return":
                        func_boundaries.append((i, j))
                        break

        pc    = 0
        steps = 0
        call_stack = [] # (return_pc, target_var, saved_env)

        while pc < len(self.tac):
            if steps > self.max_steps:
                self.output_lines.append("[VM] Execution limit reached (possible infinite loop).")
                break
            steps += 1
            
            # Skip function bodies if we are in global scope
            if not call_stack:
                skip = False
                for start, end in func_boundaries:
                    if start <= pc <= end:
                        pc = end + 1
                        skip = True
                        break
                if skip: continue

            if pc >= len(self.tac): break
            
            instr = self.tac[pc]
            parts = instr.split()
            pc   += 1

            if not parts or instr.endswith(':'):
                continue

            # goto L
            if parts[0] == 'goto':
                if parts[1] in labels:
                    pc = labels[parts[1]] + 1
                continue

            # ifFalse cond goto L
            if parts[0] == 'ifFalse':
                cond  = self._val(parts[1])
                label = parts[3]
                if not cond:
                    pc = labels[label] + 1
                continue

            # ifTrue cond goto L
            if parts[0] == 'ifTrue':
                cond  = self._val(parts[1])
                label = parts[3]
                if cond:
                    pc = labels[label] + 1
                continue

            # return [val]
            if parts[0] == 'return':
                if not call_stack:
                    break 

                # 1. Capture value from the current (function) scope
                rv = self._val(parts[1]) if len(parts) > 1 else 0
                
                # 2. Restore caller's scope and return address
                ret_pc, target, caller_env = call_stack.pop()
                self.env = caller_env
                
                # 3. Inject the result into the caller's environment
                if target:
                    self.env[target] = rv
                
                pc = ret_pc
                continue

            # read var
            if parts[0] == 'read':
                vid = parts[1]
                try:
                    raw = next(self.stdin_iter)
                    self.env[vid] = self._parse_val(str(raw))
                except StopIteration:
                    self.env[vid] = 0
                continue

            # print val
            if parts[0] == 'print':
                rest = instr[6:]
                if rest == '\\n':
                    self.output_lines.append('\n')
                elif rest.startswith('"') and rest.endswith('"'):
                    self.output_lines.append(rest[1:-1])
                else:
                    self.output_lines.append(str(self._val(rest)))
                continue

            # param x (inside function, just placeholder)
            if parts[0] == 'param':
                continue

            # Assignment: target = ...
            if len(parts) >= 3 and parts[1] == '=':
                target = parts[0]

                # function call must be checked FIRST
                if parts[2] == 'call':              # t = call fname(args)
                    call_expr = instr.split('=', 1)[1].strip()   # "call add(3, 3)"
                    call_expr = call_expr[len("call "):].strip() # "add(3, 3)"

                    if '(' in call_expr:
                        fname = call_expr.split('(')[0].strip()
                        args_str = call_expr.split('(', 1)[1].rsplit(')', 1)[0]
                    else:
                        fname = call_expr.strip()
                        args_str = ""

                    if fname in labels:
                        args_vals = []
                        for arg in args_str.split(','):
                            clean_arg = arg.strip()
                            if clean_arg:
                                args_vals.append(self._val(clean_arg))

                        call_stack.append((pc, target, self.env.copy()))

                        new_env = {}
                        f_pc = labels[fname] + 1
                        arg_idx = 0
                        while f_pc < len(self.tac) and self.tac[f_pc].strip().startswith('param '):
                            pname = self.tac[f_pc].strip().split()[1]
                            if arg_idx < len(args_vals):
                                new_env[pname] = args_vals[arg_idx]
                            arg_idx += 1
                            f_pc += 1

                        self.env = new_env
                        pc = f_pc
                    else:
                        self.env[target] = 0

                elif len(parts) == 3:               # t = val
                    self.env[target] = self._val(parts[2])

                elif len(parts) == 4:               # t = op operand
                    op, operand = parts[2], parts[3]
                    v = self._val(operand)
                    if op == 'neg':
                        self.env[target] = -v
                    elif op == '!':
                        self.env[target] = int(not bool(v))
                    else:
                        self.env[target] = v

                elif len(parts) == 5:               # t = left op right
                    left  = self._val(parts[2])
                    op    = parts[3]
                    right = self._val(parts[4])
                    self.env[target] = self._arith(op, left, right)

                continue

        return ''.join(self.output_lines)

    # ------------------------------------------------------------------
    def _parse_val(self, s):
        try:
            return int(s)
        except ValueError:
            pass
        try:
            return float(s)
        except ValueError:
            return s

    def _val(self, token):
        if not token: return 0
        token = token.strip()
        if token in self.env:
            return self.env[token]
        return self._parse_val(token)

    def _arith(self, op, l, r):
        try:
            lv = float(l)
            rv = float(r)
            
            if op == '+':  res = lv + rv
            elif op == '-':  res = lv - rv
            elif op == '*':  res = lv * rv
            elif op == '/':  res = lv / rv if rv != 0 else "DIV/0"
            elif op == '%':  res = lv % rv
            elif op == '<':  res = 1 if lv < rv else 0
            elif op == '>':  res = 1 if lv > rv else 0
            elif op == '<=': res = 1 if lv <= rv else 0
            elif op == '>=': res = 1 if lv >= rv else 0
            elif op == '==': res = 1 if lv == rv else 0
            elif op == '!=': res = 1 if lv != rv else 0
            elif op == '&&': res = 1 if lv and rv else 0
            elif op == '||': res = 1 if lv or rv else 0
            else: res = 0

            # Smart conversion: 6.0 -> 6, but 15.5 stays 15.5
            if isinstance(res, float) and res.is_integer():
                return int(res)
            return res
        except:
            pass
        return 0

    def _call(self, call_str):
        # call_str looks like: "max(a, b)" or "abs(t1)"
        try:
            name, rest = call_str.split('(', 1)
            name = name.strip()
            args_str = rest.rstrip(')').strip()
            args = [self._val(a.strip()) for a in args_str.split(',') if a.strip()] if args_str else []
            # Standard C++ math/utility functions
            fn_map = {
                'max':  max,
                'min':  min,
                'abs':  abs,
                'sqrt': math.sqrt,
                'pow':  math.pow,
                'ceil': math.ceil,
                'floor':math.floor,
                'round':round,
            }
            if name in fn_map:
                return fn_map[name](*args)
        except Exception:
            pass
        return 0


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    input_file = "ast_output.json"
    if len(sys.argv) > 1:
        input_file = sys.argv[1]

    try:
        with open(input_file) as f:
            ast = json.load(f)
    except FileNotFoundError:
        print(f"Error: {input_file} not found.")
        sys.exit(1)

    tac_gen = TACGenerator(ast)
    raw_tac = tac_gen.generate()

    with open("tac_unoptimized.txt", "w") as f:
        f.write('\n'.join(raw_tac))

    optimizer = TACOptimizer(raw_tac)
    opt_tac   = optimizer.optimize()

    with open("tac_optimized.txt", "w") as f:
        f.write('\n'.join(opt_tac))

    print("================ INTERMEDIATE CODE GENERATION ================")
    print("Unoptimized TAC -> tac_unoptimized.txt")
    print("Optimized TAC   -> tac_optimized.txt")
    print("==============================================================")

    # Run Executor (stdin = empty)
    executor = TACExecutor(opt_tac)
    output = executor.run()
    print("\n===== PROGRAM OUTPUT (V2.0) =====")
    print(output if output.strip() else "(no output — program uses cin, provide stdin values)")
