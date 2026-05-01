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
            L_start  = self.new_label()
            L_update = self.new_label()
            L_end    = self.new_label()
            self.emit(f"{L_start}:")
            cond = self.visit(node["condition"])
            self.emit(f"ifFalse {cond} goto {L_end}")
            # continue targets L_update so the loop increment always runs
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
            cond = self.visit(node["condition"])
            eb   = node.get("else_body")

            if eb:
                L_else = self.new_label()
                L_end  = self.new_label()
                self.emit(f"ifFalse {cond} goto {L_else}")
                for s in node.get("body", []):
                    self.visit(s)
                self.emit(f"goto {L_end}")
                self.emit(f"{L_else}:")
                if isinstance(eb, list):
                    for s in eb:
                        self.visit(s)
                else:
                    self.visit(eb)
                self.emit(f"{L_end}:")
            else:
                L_end = self.new_label()
                self.emit(f"ifFalse {cond} goto {L_end}")
                for s in node.get("body", []):
                    self.visit(s)
                self.emit(f"{L_end}:")

        # ---- Jump -----------------------------------------------
        elif nt == "BreakStatement":
            if self.loop_stack:
                self.emit(f"goto {self.loop_stack[-1][1]}")

        elif nt == "ContinueStatement":
            if self.loop_stack:
                # Jump to the update label so loop increments still execute
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
            op      = node["op"]
            operand = self.visit(node["operand"])
            t       = self.new_temp()
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
# Phase 4-B: Constant-Folding Optimizer  (fully corrected)
# ---------------------------------------------------------------------------
class TACOptimizer:
    """
    Multi-pass TAC optimizer.  Passes (iterated to fixed-point):
      1. Constant folding + propagation
         - FIX: constant conditions in ifFalse/ifTrue are resolved at compile time.
         - FIX: constant table is only cleared at back-edge targets (loop headers),
                not at every label, so propagation survives linear-code labels.
      2. Unreachable code elimination
      3. Dead code elimination  (proper iterative backward-liveness dataflow)
         - FIX: no global variable seeding; a real CFG with fixed-point iteration
                is used, which is both safe AND correct inside loops.
      4. Peephole – single-use temporary inlining (copy propagation / condition
         simplification)
         - FIX: patterns t=v; ifFalse t goto L  →  ifFalse v goto L
                and    t=v; x=t                 →  x=v  are reduced.
    After the fixed-point loop:
      5. Label/jump optimisation (threading, consecutive-label merging, dead-label
         removal, goto-to-next-instruction removal)
         - FIX: update labels emitted for for-loop 'continue' are preserved.
    """

    def __init__(self, code):
        self.code      = code
        self.optimized = []

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _num(s):
        """Return numeric value if s is a literal, else None."""
        if isinstance(s, (int, float)):
            return s
        try:
            txt = str(s).strip()
            if "." in txt:
                return float(txt)
            return int(txt)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _eval(op, l, r):
        try:
            if op == '+':  return l + r
            if op == '-':  return l - r
            if op == '*':  return l * r
            if op == '/':  return l / r  if r != 0 else None
            if op == '%':  return int(l) % int(r) if r != 0 else None
            if op == '<':  return int(l <  r)
            if op == '>':  return int(l >  r)
            if op == '<=': return int(l <= r)
            if op == '>=': return int(l >= r)
            if op == '==': return int(l == r)
            if op == '!=': return int(l != r)
            if op == '&&': return int(bool(l) and bool(r))
            if op == '||': return int(bool(l) or  bool(r))
        except Exception:
            return None

    def _is_temp(self, name):
        return isinstance(name, str) and name.startswith('t') and name[1:].isdigit()

    # ------------------------------------------------------------------ label index
    @staticmethod
    def _label_index(code):
        """Return {label_name: line_index}."""
        idx = {}
        for i, instr in enumerate(code):
            if instr.endswith(':') and not instr.startswith('if'):
                idx[instr[:-1]] = i
        return idx

    # ------------------------------------------------------------------ CFG uses/defs
    def _uses_defs(self, instr):
        """
        Return (uses: frozenset, defs: frozenset) for a single TAC instruction.
        Used by the liveness dataflow analysis.
        """
        uses = set()
        defs = set()

        OPERATORS = {'+','-','*','/','%','<','>','<=','>=','==','!=','&&','||',
                     'neg','!','call','goto','ifFalse','ifTrue','return','print',
                     'read','param','\\n'}

        def add_use(tok):
            tok = tok.strip()
            if (tok and tok not in OPERATORS
                    and self._num(tok) is None
                    and not (tok.startswith('"') and tok.endswith('"'))):
                uses.add(tok)

        parts = instr.split()
        if not parts or instr.endswith(':'):
            return frozenset(), frozenset()

        kw = parts[0]

        if kw == 'goto':
            pass
        elif kw in ('ifFalse', 'ifTrue'):
            add_use(parts[1])
        elif kw == 'return':
            if len(parts) > 1:
                add_use(parts[1])
        elif kw == 'print':
            rest = instr[6:].strip()
            if rest != '\\n' and not (rest.startswith('"') and rest.endswith('"')):
                add_use(rest)
        elif kw == 'read':
            if len(parts) > 1:
                defs.add(parts[1])          # read writes the variable
        elif kw == 'param':
            if len(parts) > 1:
                defs.add(parts[1])          # param defines the local
        elif len(parts) >= 3 and parts[1] == '=':
            defs.add(parts[0])
            rhs = instr.split('=', 1)[1].strip()
            if rhs.startswith('call '):
                try:
                    args_str = rhs.split('(', 1)[1].rsplit(')', 1)[0]
                    for a in args_str.split(','):
                        add_use(a.strip())
                except Exception:
                    pass
            else:
                for tok in parts[2:]:
                    if tok not in OPERATORS:
                        add_use(tok)

        return frozenset(uses), frozenset(defs)

    # ------------------------------------------------------------------ liveness
    def _compute_liveness(self, code):
        """
        Proper iterative backward dataflow.
        Returns (live_in[i], live_out[i]) for each instruction index.
        Handles arbitrary control flow (back-edges / loops) correctly.
        """
        n = len(code)
        labels = self._label_index(code)

        # Build successor lists
        succs = [[] for _ in range(n)]
        for i, instr in enumerate(code):
            parts = instr.split()
            if not parts:
                if i + 1 < n:
                    succs[i].append(i + 1)
                continue
            kw = parts[0]
            is_label = instr.endswith(':') and not instr.startswith('if')

            if is_label:
                if i + 1 < n:
                    succs[i].append(i + 1)
            elif kw == 'goto':
                tgt = parts[1]
                if tgt in labels:
                    succs[i].append(labels[tgt])
            elif kw in ('ifFalse', 'ifTrue'):
                tgt = parts[3]
                if tgt in labels:
                    succs[i].append(labels[tgt])
                if i + 1 < n:
                    succs[i].append(i + 1)
            elif kw == 'return' or instr == 'return':
                pass  # terminal
            else:
                if i + 1 < n:
                    succs[i].append(i + 1)

        # Precompute uses/defs
        ud = [self._uses_defs(code[i]) for i in range(n)]

        live_in  = [set() for _ in range(n)]
        live_out = [set() for _ in range(n)]

        # Worklist: process in reverse post-order approximation (reverse order suffices
        # for a first pass; the loop repeats until stable).
        changed = True
        while changed:
            changed = False
            for i in range(n - 1, -1, -1):
                new_out = set()
                for s in succs[i]:
                    new_out |= live_in[s]

                uses_i, defs_i = ud[i]
                new_in = uses_i | (new_out - defs_i)

                if new_in != live_in[i] or new_out != live_out[i]:
                    live_in[i]  = new_in
                    live_out[i] = new_out
                    changed = True

        return live_in, live_out

    # ================================================================== PASSES

    # ------------------------------------------------------------------ Pass 1
    def _constant_fold_propagate(self, code):
        """
        Constant folding + propagation with:
          - constant branch elimination (ifFalse/ifTrue on a known constant)
          - constant table cleared only at back-edge labels (loop headers),
            not at every label, preserving propagation across sequential blocks.
        """
        labels = self._label_index(code)

        # Identify back-edge targets: a label L is a back-edge target if any
        # 'goto L' instruction appears AFTER position labels[L] in the listing.
        back_edge_labels = set()
        for i, instr in enumerate(code):
            parts = instr.split()
            if parts and parts[0] == 'goto':
                tgt = parts[1]
                if tgt in labels and labels[tgt] <= i:
                    back_edge_labels.add(tgt)
        # ifTrue back-edges (do-while)
        for i, instr in enumerate(code):
            parts = instr.split()
            if parts and parts[0] == 'ifTrue':
                tgt = parts[3]
                if tgt in labels and labels[tgt] <= i:
                    back_edge_labels.add(tgt)

        result = []
        consts = {}   # var -> folded numeric constant

        for instr in code:
            parts = instr.split()
            if not parts:
                result.append(instr)
                continue

            # ---- Label ---------------------------------------------------
            if instr.endswith(':') and not instr.startswith('if'):
                result.append(instr)
                lname = instr[:-1]
                if lname in back_edge_labels:
                    # Conservative: clear everything at loop-header labels to
                    # avoid propagating stale loop-variable constants.
                    consts.clear()
                # At non-back-edge labels we intentionally keep the constant
                # table so propagation survives if/else merges in linear code.
                continue

            # ---- goto ----------------------------------------------------
            if parts[0] == 'goto':
                result.append(instr)
                continue

            # ---- ifFalse / ifTrue  (FIX: constant-condition folding) -----
            if parts[0] in ('ifFalse', 'ifTrue'):
                cond_var = parts[1]
                label    = parts[3]
                resolved = consts.get(cond_var, cond_var)
                n        = self._num(resolved)
                if n is not None:
                    # Condition is a compile-time constant.
                    always_jump = (parts[0] == 'ifFalse' and not n) or \
                                  (parts[0] == 'ifTrue'  and bool(n))
                    if always_jump:
                        result.append(f"goto {label}")
                    # else: branch is never taken → emit nothing (dead branch)
                else:
                    # Substitute resolved variable name if different
                    new_cond = consts.get(cond_var, cond_var)
                    result.append(f"{parts[0]} {new_cond} {parts[2]} {label}")
                # After a conditional we cannot know which path was taken;
                # keep consts (they remain valid in both successor blocks for
                # variables that are not redefined on either path — a sound
                # over-approximation for our single-pass approach).
                continue

            # ---- return --------------------------------------------------
            if parts[0] == 'return':
                if len(parts) > 1:
                    val = consts.get(parts[1], parts[1])
                    result.append(f"return {val}")
                else:
                    result.append(instr)
                continue

            # ---- read var  (invalidates the variable) --------------------
            if parts[0] == 'read':
                result.append(instr)
                if len(parts) > 1:
                    consts.pop(parts[1], None)
                continue

            # ---- print val -----------------------------------------------
            if parts[0] == 'print':
                rest = instr[6:].strip()
                if rest != '\\n' and not (rest.startswith('"') and rest.endswith('"')):
                    resolved = consts.get(rest, rest)
                    result.append(f"print {resolved}")
                else:
                    result.append(instr)
                continue

            # ---- param ---------------------------------------------------
            if parts[0] == 'param':
                result.append(instr)
                continue

            # ---- Assignment: target = ... --------------------------------
            if len(parts) >= 3 and parts[1] == '=':
                target = parts[0]
                rhs    = instr.split('=', 1)[1].strip()

                if rhs.startswith('call '):
                    # Function call: result is unknown at compile time.
                    result.append(instr)
                    consts.pop(target, None)
                    continue

                if len(parts) == 3:           # target = val
                    val      = parts[2]
                    resolved = consts.get(val, val)
                    n        = self._num(resolved)
                    if n is not None:
                        consts[target] = n
                    else:
                        # Copy propagation: if val is another variable with a
                        # known alias, carry the alias forward.
                        consts.pop(target, None)
                    emit_val = resolved if n is None else n
                    result.append(f"{target} = {emit_val}")

                elif len(parts) == 4:         # target = op operand  (unary)
                    op, operand = parts[2], parts[3]
                    resolved    = consts.get(operand, operand)
                    n           = self._num(resolved)
                    if n is not None:
                        if op == 'neg':
                            res = -n
                        elif op == '!':
                            res = int(not bool(n))
                        else:
                            res = None
                        if res is not None:
                            consts[target] = res
                            result.append(f"{target} = {res}")
                            continue
                    consts.pop(target, None)
                    result.append(f"{target} = {op} {resolved}")

                elif len(parts) == 5:         # target = left op right  (binary)
                    left, op, right = parts[2], parts[3], parts[4]
                    res_l = consts.get(left,  left)
                    res_r = consts.get(right, right)
                    nl    = self._num(res_l)
                    nr    = self._num(res_r)
                    if nl is not None and nr is not None:
                        res = self._eval(op, nl, nr)
                        if res is not None:
                            consts[target] = res
                            result.append(f"{target} = {res}")
                            continue
                    consts.pop(target, None)
                    result.append(f"{target} = {res_l} {op} {res_r}")

                else:
                    result.append(instr)
                    consts.pop(target, None)
                continue

            # ---- anything else -------------------------------------------
            result.append(instr)

        return result

    # ------------------------------------------------------------------ Pass 2
    def _unreachable_code_elimination(self, code):
        """
        Remove instructions after unconditional goto/return until the next label.
        A label only resets the 'dead' flag if it is actually referenced by some
        goto / ifFalse / ifTrue / call in the code — orphaned labels left behind
        by constant-branch folding do NOT reset reachability.
        """
        # Collect all label names that are genuinely targeted
        referenced = {'main'}
        for instr in code:
            parts = instr.split()
            if not parts:
                continue
            if parts[0] == 'goto' and len(parts) > 1:
                referenced.add(parts[1])
            elif parts[0] in ('ifFalse', 'ifTrue') and len(parts) > 3:
                referenced.add(parts[3])
            elif 'call' in instr and '(' in instr:
                try:
                    fname = instr.split('call')[1].strip().split('(')[0].strip()
                    referenced.add(fname)
                except Exception:
                    pass

        result = []
        dead   = False
        for instr in code:
            parts    = instr.split()
            is_label = instr.endswith(':') and (not parts or parts[0] != 'if')
            if is_label:
                lname = instr[:-1]
                if lname in referenced:   # only live labels break dead-code runs
                    dead = False
            if not dead:
                result.append(instr)
            if not dead and parts and parts[0] in ('goto', 'return'):
                dead = True
        return result

    # ------------------------------------------------------------------ Pass 3
    def _dead_code_elimination(self, code):
        """
        Remove assignments whose target is not live after the instruction.
        Uses proper iterative backward dataflow — no global seeding.
        Function calls are never removed (they may have side effects).
        """
        _, live_out = self._compute_liveness(code)
        result = []
        for i, instr in enumerate(code):
            parts = instr.split()
            if len(parts) >= 3 and parts[1] == '=':
                target = parts[0]
                if 'call' not in instr and target not in live_out[i]:
                    continue  # dead assignment — drop it
            result.append(instr)
        return result

    # ------------------------------------------------------------------ Pass 4
    def _peephole_temp_inline(self, code):
        """
        Inline single-use temporaries to simplify the TAC and enable further
        constant-branch folding in subsequent passes.

        Patterns handled (only when the temporary t is used exactly once and the
        very next non-label instruction consumes it):
          t = <atom>; ifFalse t goto L  →  ifFalse <atom> goto L
          t = <atom>; ifTrue  t goto L  →  ifTrue  <atom> goto L
          t = <atom>; x = t             →  x = <atom>          (copy propagation)
          t = <atom>; print t           →  print <atom>
          t = <atom>; return t          →  return <atom>

        <atom> means a single token (constant or variable), NOT a computed expression,
        so the resulting TAC stays well-formed.
        """
        # Count how many times each name is used (on RHS / conditionals / print / return)
        use_count = {}
        OPERATORS = {'+','-','*','/','%','<','>','<=','>=','==','!=','&&','||',
                     'neg','!'}

        def count_use(tok):
            tok = tok.strip()
            if tok and self._num(tok) is None \
                    and tok not in OPERATORS \
                    and not (tok.startswith('"') and tok.endswith('"')):
                use_count[tok] = use_count.get(tok, 0) + 1

        for instr in code:
            parts = instr.split()
            if not parts or instr.endswith(':'):
                continue
            kw = parts[0]
            if kw in ('ifFalse', 'ifTrue'):
                count_use(parts[1])
            elif kw == 'print':
                rest = instr[6:].strip()
                if rest != '\\n' and not (rest.startswith('"') and rest.endswith('"')):
                    count_use(rest)
            elif kw == 'return' and len(parts) > 1:
                count_use(parts[1])
            elif len(parts) >= 3 and parts[1] == '=':
                rhs = instr.split('=', 1)[1].strip()
                if rhs.startswith('call '):
                    try:
                        args_str = rhs.split('(', 1)[1].rsplit(')', 1)[0]
                        for a in args_str.split(','):
                            count_use(a.strip())
                    except Exception:
                        pass
                else:
                    for tok in parts[2:]:
                        if tok not in OPERATORS:
                            count_use(tok)

        # Single-use temp inlining (look-ahead one instruction)
        result   = []
        skip_set = set()

        for i, instr in enumerate(code):
            if i in skip_set:
                continue

            parts = instr.split()
            # Pattern: t = <atom>  where t is a temp used exactly once
            if (len(parts) == 3 and parts[1] == '='
                    and self._is_temp(parts[0])
                    and use_count.get(parts[0], 0) == 1):

                t, atom = parts[0], parts[2]

                # Find the next meaningful (non-empty, non-label) instruction
                j = i + 1
                while j < len(code) and (not code[j].strip()
                                          or (code[j].endswith(':') and not code[j].startswith('if'))):
                    j += 1

                if j < len(code):
                    nxt   = code[j]
                    nparts = nxt.split()

                    if nparts and nparts[0] in ('ifFalse', 'ifTrue') and nparts[1] == t:
                        result.append(f"{nparts[0]} {atom} {nparts[2]} {nparts[3]}")
                        skip_set.add(j)
                        continue

                    if (len(nparts) == 3 and nparts[1] == '='
                            and len(nparts) == 3 and nparts[2] == t):
                        result.append(f"{nparts[0]} = {atom}")
                        skip_set.add(j)
                        continue

                    if nparts and nparts[0] == 'print' and nxt[6:].strip() == t:
                        result.append(f"print {atom}")
                        skip_set.add(j)
                        continue

                    if nparts and nparts[0] == 'return' and len(nparts) > 1 and nparts[1] == t:
                        result.append(f"return {atom}")
                        skip_set.add(j)
                        continue

            result.append(instr)

        return result

    # ------------------------------------------------------------------ Pass 5
    def _label_jump_optimization(self, code):
        """
        Iterative label and jump cleanup:
          a) Jump threading: goto L where L: goto M  →  goto M
          b) Consecutive label merging
          c) goto-to-next-label removal
          d) Dead label removal

        Update labels generated for for-loop 'continue' are preserved because
        they appear as targets of goto instructions and survive the used-label
        analysis automatically.
        """
        changed = True
        while changed:
            changed = False

            labels = self._label_index(code)

            # ---- (a+b) Build redirection map ----------------------------
            redir = {}
            for lname, pos in labels.items():
                # Skip over consecutive labels
                j = pos + 1
                while j < len(code) and code[j].endswith(':') \
                        and not code[j].startswith('if'):
                    other = code[j][:-1]
                    if other not in redir:
                        redir[other] = lname   # merge other → lname
                    j += 1
                # Jump threading
                if j < len(code) and code[j].startswith('goto '):
                    tgt = code[j].split()[1]
                    if tgt != lname:
                        redir[lname] = tgt

            # Resolve chains (handles A→B→C)
            def resolve(lbl, seen=None):
                seen = seen or set()
                if lbl in seen or lbl not in redir:
                    return lbl
                seen.add(lbl)
                return resolve(redir[lbl], seen)

            if redir:
                new_code = []
                for instr in code:
                    parts = instr.split()
                    if not parts:
                        new_code.append(instr)
                        continue
                    if parts[0] == 'goto':
                        r = resolve(parts[1])
                        if r != parts[1]:
                            changed = True
                        new_code.append(f"goto {r}")
                    elif parts[0] in ('ifFalse', 'ifTrue'):
                        r = resolve(parts[3])
                        if r != parts[3]:
                            changed = True
                        new_code.append(f"{parts[0]} {parts[1]} {parts[2]} {r}")
                    else:
                        new_code.append(instr)
                code = new_code

            # ---- (c) Remove goto whose target is the very next label ----
            new_code = []
            for i, instr in enumerate(code):
                parts = instr.split()
                if parts and parts[0] == 'goto':
                    tgt = parts[1]
                    j = i + 1
                    while j < len(code) and not code[j].strip():
                        j += 1
                    if j < len(code) and code[j] == f"{tgt}:":
                        changed = True
                        continue
                new_code.append(instr)
            code = new_code

            # ---- (d) Dead label removal ---------------------------------
            used_labels = {'main'}
            for instr in code:
                parts = instr.split()
                if not parts:
                    continue
                if parts[0] == 'goto':
                    used_labels.add(parts[1])
                elif parts[0] in ('ifTrue', 'ifFalse'):
                    used_labels.add(parts[3])
                elif 'call' in instr and '(' in instr:
                    fname = instr.split('call')[1].strip().split('(')[0].strip()
                    used_labels.add(fname)
            # Preserve function-definition labels (label immediately before 'param')
            labels_now = self._label_index(code)
            for lname, pos in labels_now.items():
                if pos + 1 < len(code) and code[pos + 1].startswith('param '):
                    used_labels.add(lname)

            new_code = []
            for instr in code:
                if instr.endswith(':') and not instr.startswith('if'):
                    lname = instr[:-1]
                    if lname not in used_labels:
                        changed = True
                        continue
                new_code.append(instr)
            code = new_code

        return code

    # ================================================================== PUBLIC
    def optimize(self):
        code = list(self.code)

        # Iterate all passes until the code stabilises (fixed-point).
        prev       = None
        iterations = 0
        max_iters  = 20   # safety cap

        while prev != code and iterations < max_iters:
            prev = list(code)
            iterations += 1
            code = self._constant_fold_propagate(code)
            code = self._unreachable_code_elimination(code)
            code = self._dead_code_elimination(code)
            code = self._peephole_temp_inline(code)

        # Label/jump pass runs once after convergence (it is already iterative
        # internally and does not interact with the data-flow passes).
        code = self._label_jump_optimization(code)

        self.optimized = code
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
        self.max_steps    = 1_000_000
        self.max_output   = 2_000
        self.current_instr= ""

    # ------------------------------------------------------------------
    def run(self):
        labels = {}
        func_boundaries = []
        import re as _re

        for i, instr in enumerate(self.tac):
            if instr.endswith(':') and not instr.startswith('if'):
                name = instr[:-1]
                labels[name] = i
                # Only user-defined functions (not generated L1/L2/... labels, not main)
                if name != 'main' and not _re.match(r'^L\d+$', name):
                    # Scan for the first 'return' BEFORE the next function-def label
                    for j in range(i + 1, len(self.tac)):
                        next_instr = self.tac[j]
                        # Stop if we reach another function-definition label
                        if (next_instr.endswith(':')
                                and not next_instr.startswith('if')
                                and next_instr[:-1] != name):
                            break
                        if next_instr == "return":
                            func_boundaries.append((i, j))
                            break

        pc = 0
        for i, instr in enumerate(self.tac):
            if instr == 'main:':
                pc = i + 1
                break

        steps      = 0
        call_stack = []

        while pc < len(self.tac):
            if steps > self.max_steps:
                self.output_lines.append(
                    "\n[RUNTIME ERROR] Maximum instruction limit exceeded (possible infinite loop).")
                self.output_lines.append("--- Debug Info ---")
                self.output_lines.append("Variables: " + str(self.env))
                self.output_lines.append("Last 5 instructions:")
                for dbg in self.tac[max(0, pc - 5):pc]:
                    self.output_lines.append("  " + dbg)
                break
            if len(self.output_lines) > self.max_output:
                self.output_lines.append(
                    "\n[RUNTIME ERROR] Standard output limit exceeded (buffer overflow).")
                break
            steps += 1

            # Skip function bodies when in global scope
            if not call_stack:
                skip = False
                for start, end in func_boundaries:
                    if start <= pc <= end:
                        pc   = end + 1
                        skip = True
                        break
                if skip:
                    continue

            if pc >= len(self.tac):
                break

            instr = self.tac[pc]
            parts = instr.split()
            pc   += 1

            if not parts or instr.endswith(':'):
                continue

            self.current_instr = instr

            try:
                if parts[0] == 'goto':
                    pc = labels[parts[1]] + 1
                    continue

                if parts[0] == 'ifFalse':
                    cond = self._val(parts[1])
                    if not cond:
                        pc = labels[parts[3]] + 1
                    continue

                if parts[0] == 'ifTrue':
                    cond = self._val(parts[1])
                    if cond:
                        pc = labels[parts[3]] + 1
                    continue

                if parts[0] == 'return':
                    if not call_stack:
                        break
                    rv = self._val(parts[1]) if len(parts) > 1 else 0
                    ret_pc, target, caller_env = call_stack.pop()
                    self.env = caller_env
                    if target:
                        self.env[target] = rv
                    pc = ret_pc
                    continue

                if parts[0] == 'read':
                    vid = parts[1]
                    try:
                        raw = next(self.stdin_iter)
                        self.env[vid] = self._parse_val(str(raw))
                    except StopIteration:
                        self.env[vid] = 0
                    continue

                if parts[0] == 'print':
                    rest = instr[6:]
                    if rest == '\\n':
                        self.output_lines.append('\n')
                    elif rest.startswith('"') and rest.endswith('"'):
                        self.output_lines.append(rest[1:-1])
                    else:
                        self.output_lines.append(str(self._val(rest)))
                    continue

                if parts[0] == 'param':
                    continue

                if len(parts) >= 3 and parts[1] == '=':
                    target = parts[0]

                    if parts[2] == 'call':
                        call_expr = instr.split('=', 1)[1].strip()[len("call "):].strip()
                        if '(' in call_expr:
                            fname    = call_expr.split('(')[0].strip()
                            args_str = call_expr.split('(', 1)[1].rsplit(')', 1)[0]
                        else:
                            fname    = call_expr.strip()
                            args_str = ""

                        if fname in labels:
                            args_vals = [self._val(a.strip())
                                         for a in args_str.split(',')
                                         if a.strip()] if args_str else []
                            call_stack.append((pc, target, self.env.copy()))
                            new_env = {}
                            f_pc    = labels[fname] + 1
                            idx     = 0
                            while (f_pc < len(self.tac)
                                   and self.tac[f_pc].strip().startswith('param ')):
                                pname = self.tac[f_pc].strip().split()[1]
                                if idx < len(args_vals):
                                    new_env[pname] = args_vals[idx]
                                idx  += 1
                                f_pc += 1
                            self.env = new_env
                            pc = f_pc
                        else:
                            self.env[target] = 0

                    elif len(parts) == 3:
                        self.env[target] = self._val(parts[2])

                    elif len(parts) == 4:
                        op, operand = parts[2], parts[3]
                        v = self._val(operand)
                        if op == 'neg':
                            self.env[target] = -v
                        elif op == '!':
                            self.env[target] = int(not bool(v))
                        else:
                            self.env[target] = v

                    elif len(parts) == 5:
                        left  = self._val(parts[2])
                        op    = parts[3]
                        right = self._val(parts[4])
                        self.env[target] = self._arith(op, left, right)
                    continue

            except Exception as e:
                self.output_lines.append(f"\n[RUNTIME ERROR] {str(e)}")
                break

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
        if not token:
            return 0
        token = token.strip()
        if token in self.env:
            return self.env[token]
        if token.startswith('"') and token.endswith('"'):
            return token[1:-1]
        if token.isidentifier() and token not in ('neg', '!', 'call', 'true', 'false'):
            raise Exception(
                f"Variable '{token}' used before assignment at: {self.current_instr}")
        return self._parse_val(token)

    def _arith(self, op, l, r):
        try:
            lv = float(l)
            rv = float(r)
        except (ValueError, TypeError):
            lv = rv = 0.0

        if   op == '+':  res = lv + rv
        elif op == '-':  res = lv - rv
        elif op == '*':  res = lv * rv
        elif op == '/':
            if rv == 0:
                raise Exception(f"Division by zero at: {self.current_instr}")
            res = lv / rv
        elif op == '%':
            if rv == 0:
                raise Exception(f"Division by zero at: {self.current_instr}")
            res = lv % rv
        elif op == '<':  res = 1 if lv <  rv else 0
        elif op == '>':  res = 1 if lv >  rv else 0
        elif op == '<=': res = 1 if lv <= rv else 0
        elif op == '>=': res = 1 if lv >= rv else 0
        elif op == '==': res = 1 if lv == rv else 0
        elif op == '!=': res = 1 if lv != rv else 0
        elif op == '&&': res = 1 if lv and rv else 0
        elif op == '||': res = 1 if lv or  rv else 0
        else:            res = 0

        if isinstance(res, float) and res.is_integer():
            return int(res)
        return res


# ---------------------------------------------------------------------------
# Standalone entry-point
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

    executor = TACExecutor(opt_tac)
    output   = executor.run()
    print("\n===== PROGRAM OUTPUT =====")
    print(output if output.strip()
          else "(no output — program uses cin, provide stdin values)")
