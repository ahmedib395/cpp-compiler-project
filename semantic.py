import sys
import json

class SemanticError(Exception):
    pass

class SemanticAnalyzer:
    def __init__(self, ast):
        self.ast        = ast
        self.scopes     = [{}]   # Stack of dictionaries for scoping
        self.loop_depth = 0

    def analyze(self):
        self.visit(self.ast)
        # Return the global scope for the final symbol table output
        return {k: v["type"] for k, v in self.scopes[0].items()}

    # ------------------------------------------------------------------
    def declare(self, var_id, var_type, line, is_const=False):
        # Check only the current (topmost) scope for re-declaration
        if var_id in self.scopes[-1]:
            raise SemanticError(
                f"SEMANTIC ERROR at Line {line}: "
                f"Variable '{var_id}' is already declared in this scope."
            )
        self.scopes[-1][var_id] = {"type": var_type, "const": is_const}

    def lookup(self, var_id, line):
        # Search from the inner scope outwards
        for scope in reversed(self.scopes):
            if var_id in scope:
                return scope[var_id]["type"]
        raise SemanticError(
                f"SEMANTIC ERROR at Line {line}: "
                f"Variable '{var_id}' used before declaration."
            )

    # ------------------------------------------------------------------
    def visit(self, node):
        if not node:
            return None
        nt = node.get("type")

        if nt == "Program":
            for stmt in node.get("body", []):
                self.visit(stmt)

        elif nt in ("IncludeStatement", "UsingStatement"):
            pass

        elif nt == "MainFunction":
            self.scopes.append({})
            for param in node.get("params", []):
                self.declare(param["id"], param["var_type"], param.get("line", 0))
            for stmt in node.get("body", []):
                self.visit(stmt)
            self.scopes.pop()

        elif nt == "FunctionDefinition":
            self.scopes.append({})
            for param in node.get("params", []):
                self.declare(param["id"], param["var_type"], param.get("line", 0))
            for stmt in node.get("body", []):
                self.visit(stmt)
            self.scopes.pop()

        # ---- Declarations ----------------------------------------
        elif nt == "Declaration":
            vid   = node["id"]
            vtype = node["var_type"]
            line  = node.get("line", 0)
            is_const = vtype.startswith("const")
            self.declare(vid, vtype, line, is_const)
            if node.get("value"):
                rtype = self.visit(node["value"])
                if rtype and not self._compatible(vtype, rtype):
                    raise SemanticError(
                        f"SEMANTIC ERROR at Line {line}: Type mismatch — "
                        f"cannot assign {rtype} to {vtype}."
                    )

        elif nt == "MultiDeclaration":
            vtype = node["var_type"]
            line  = node.get("line", 0)
            for vd in node.get("vars", []):
                self.declare(vd["id"], vtype, line)
                if vd.get("value"):
                    rtype = self.visit(vd["value"])
                    if rtype and not self._compatible(vtype, rtype):
                        raise SemanticError(
                            f"SEMANTIC ERROR at Line {line}: Type mismatch — "
                            f"cannot assign {rtype} to {vtype}."
                        )

        # ---- Assignment -------------------------------------------
        elif nt == "Assignment":
            vid  = node["id"]
            line = node.get("line", 0)
            vtype = self.lookup(vid, line)
            
            # Check if it's const
            is_const = False
            for scope in reversed(self.scopes):
                if vid in scope:
                    is_const = scope[vid].get("const", False)
                    break
            
            if is_const:
                raise SemanticError(
                    f"SEMANTIC ERROR at Line {line}: "
                    f"Assignment to const variable '{vid}'."
                )
            rtype = self.visit(node["value"])
            if rtype and not self._compatible(vtype, rtype):
                raise SemanticError(
                    f"SEMANTIC ERROR at Line {line}: Type mismatch — "
                    f"cannot assign {rtype} to {vtype}."
                )

        # ---- Incr/Decr --------------------------------------------
        elif nt == "IncrDecr":
            self.lookup(node["id"], node.get("line", 0))

        # ---- Loops -----------------------------------------------
        elif nt == "WhileLoop":
            self.visit(node.get("condition"))
            self.loop_depth += 1
            for s in node.get("body", []):
                self.visit(s)
            self.loop_depth -= 1

        elif nt == "ForLoop":
            self.visit(node.get("init"))
            self.visit(node.get("condition"))
            self.visit(node.get("update"))
            self.loop_depth += 1
            for s in node.get("body", []):
                self.visit(s)
            self.loop_depth -= 1

        elif nt == "DoWhile":
            self.loop_depth += 1
            for s in node.get("body", []):
                self.visit(s)
            self.loop_depth -= 1
            self.visit(node.get("condition"))

        # ---- If / Else -------------------------------------------
        elif nt == "IfStatement":
            self.visit(node.get("condition"))
            for s in node.get("body", []):
                self.visit(s)
            eb = node.get("else_body")
            if eb:
                if isinstance(eb, list):
                    for s in eb:
                        self.visit(s)
                else:
                    self.visit(eb)

        # ---- Jump ------------------------------------------------
        elif nt in ("BreakStatement", "ContinueStatement"):
            if self.loop_depth == 0:
                kw = "break" if nt == "BreakStatement" else "continue"
                raise SemanticError(
                    f"SEMANTIC ERROR at Line {node.get('line', 0)}: "
                    f"'{kw}' used outside a loop."
                )

        elif nt == "ReturnStatement":
            if node.get("value"):
                self.visit(node["value"])

        # ---- I/O -------------------------------------------------
        elif nt == "CinStatement":
            for vid in node.get("ids", []):
                self.lookup(vid, node.get("line", 0))

        elif nt == "CoutStatement":
            for item in node.get("items", []):
                if item.get("kind") == "expr":
                    self.visit(item.get("value"))

        # ---- Expressions -----------------------------------------
        elif nt == "Condition":
            self.visit(node.get("left"))
            self.visit(node.get("right"))

        elif nt == "LogicalExpr":
            self.visit(node.get("left"))
            self.visit(node.get("right"))

        elif nt == "BinaryExpression":
            lt = self.visit(node.get("left"))
            rt = self.visit(node.get("right"))
            return self._result_type(lt, rt)

        elif nt == "UnaryExpr":
            return self.visit(node.get("operand"))

        elif nt == "FunctionCall":
            for arg in node.get("args", []):
                self.visit(arg)
            return "int"   # treat all library calls as returning int for now

        elif nt == "Identifier":
            return self.lookup(node["value"], node.get("line", 0))

        elif nt == "Number":
            return "int"

        elif nt == "FloatNumber":
            return "float"

        elif nt == "StringLiteral":
            return "string"

        elif nt == "CharLiteral":
            return "char"

        elif nt == "BoolLiteral":
            return "bool"

        elif nt == "ExprStatement":
            self.visit(node.get("expr"))

        else:
            pass   # unknown node — silently skip

        return None

    # ------------------------------------------------------------------
    def _compatible(self, target, source):
        t = target.replace("const ", "")
        if t == source:
            return True
        numeric = {"int", "float", "double"}
        if t in numeric and source in numeric:
            return True
        if t == "bool" and source in ("int", "bool"):
            return True
        return False

    def _result_type(self, t1, t2):
        if "double" in (t1, t2):
            return "double"
        if "float" in (t1, t2):
            return "float"
        return "int"


# ---------------------------------------------------------------------------
if __name__ == '__main__':
    input_file = "ast_output.json"
    if len(sys.argv) > 1:
        input_file = sys.argv[1]

    try:
        with open(input_file) as f:
            ast = json.load(f)
    except FileNotFoundError:
        print(f"Error: {input_file} not found.")
        sys.exit(1)

    try:
        analyzer     = SemanticAnalyzer(ast)
        symbol_table = analyzer.analyze()
    except SemanticError as e:
        print(str(e))
        sys.exit(1)

    with open("symbol_table.json", 'w') as f:
        json.dump(symbol_table, f, indent=4)

    print("================== SEMANTIC ANALYZER ==================")
    print(f"Source AST:  {input_file}")
    print("Symbol Table:")
    for var, vtype in symbol_table.items():
        print(f"  {var}: {vtype}")
    print("=======================================================")
