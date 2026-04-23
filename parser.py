import sys
import json
import lexer

class SyntaxErrorExt(Exception):
    pass

# ---------------------------------------------------------------------------
# Terminal / Non-terminal sets
# ---------------------------------------------------------------------------
TERMINALS = {
    'PREPROCESSOR', 'USING', 'NAMESPACE', 'STD',
    'MAIN', 'CIN', 'COUT', 'ENDL', 'RETURN',
    'VOID', 'INT', 'FLOAT', 'DOUBLE', 'CHAR', 'BOOL', 'CONST',
    'FOR', 'WHILE', 'DO', 'IF', 'ELSE', 'BREAK', 'CONTINUE',
    'EQ', 'NEQ', 'LT', 'GT', 'LEQ', 'GEQ',
    'SHL', 'SHR',
    'AND', 'OR', 'NOT',
    'INC', 'DEC',
    'ASSIGN', 'PLUS_ASSIGN', 'MINUS_ASSIGN', 'TIMES_ASSIGN', 'DIV_ASSIGN',
    'PLUS', 'MINUS', 'TIMES', 'DIVIDE', 'MOD',
    'SEMI', 'COMMA', 'LBRACE', 'RBRACE', 'LPAREN', 'RPAREN',
    'LBRACKET', 'RBRACKET',
    'NUMBER', 'FLOAT_NUM', 'STRING', 'CHAR_LIT', 'TRUE', 'FALSE',
    'IDENTIFIER', 'EOF'
}

def node(ntype, **kwargs):
    d = {"type": ntype}
    d.update(kwargs)
    return d

# ---------------------------------------------------------------------------
# Grammar  (each entry: LHS, [RHS symbols], semantic-action)
# ---------------------------------------------------------------------------
RULES = [
    # Augmented start
    ("S'",          ["Program"],                    lambda p: p[0][1]),

    # Program -> GlobalList
    ("Program",     ["GlobalList"],                 lambda p: node("Program", body=p[0][1])),

    # GlobalList (left-recursive)
    ("GlobalList",  ["GlobalList", "Global"],       lambda p: p[0][1] + [p[1][1]]),
    ("GlobalList",  ["Global"],                     lambda p: [p[0][1]]),
    ("GlobalList",  [],                             lambda p: []),

    # Global declarations
    ("Global",      ["IncludeStmt"],                lambda p: p[0][1]),
    ("Global",      ["UsingStmt"],                  lambda p: p[0][1]),
    ("Global",      ["FunctionDef"],                lambda p: p[0][1]),

    # #include
    ("IncludeStmt", ["PREPROCESSOR"],
        lambda p: node("IncludeStatement", value=p[0][1], line=p[0][2])),

    # using namespace std;
    ("UsingStmt",   ["USING", "NAMESPACE", "STD", "SEMI"],
        lambda p: node("UsingStatement", ns=p[2][1], line=p[0][2])),

    # int main() { ... }
    ("FunctionDef", ["RetType", "MAIN", "LPAREN", "RPAREN", "LBRACE", "StmtList", "RBRACE"],
        lambda p: node("MainFunction", body=p[5][1], line=p[1][2])),

    # Return types
    ("RetType",     ["INT"],     lambda p: "int"),
    ("RetType",     ["VOID"],    lambda p: "void"),
    ("RetType",     ["FLOAT"],   lambda p: "float"),
    ("RetType",     ["DOUBLE"],  lambda p: "double"),

    # Type (for declarations)
    ("Type",        ["INT"],     lambda p: p[0][1]),
    ("Type",        ["FLOAT"],   lambda p: p[0][1]),
    ("Type",        ["DOUBLE"],  lambda p: p[0][1]),
    ("Type",        ["CHAR"],    lambda p: p[0][1]),
    ("Type",        ["BOOL"],    lambda p: p[0][1]),
    ("Type",        ["CONST", "INT"],    lambda p: "const int"),
    ("Type",        ["CONST", "FLOAT"],  lambda p: "const float"),
    ("Type",        ["CONST", "DOUBLE"], lambda p: "const double"),

    # StatementList
    ("StmtList",    ["StmtList", "Stmt"],  lambda p: p[0][1] + [p[1][1]]),
    ("StmtList",    ["Stmt"],              lambda p: [p[0][1]]),
    ("StmtList",    [],                    lambda p: []),

    # Statement kinds
    ("Stmt",        ["DeclStmt"],          lambda p: p[0][1]),
    ("Stmt",        ["AssignStmt"],        lambda p: p[0][1]),
    ("Stmt",        ["CompoundAssign"],    lambda p: p[0][1]),
    ("Stmt",        ["IncrStmt"],          lambda p: p[0][1]),
    ("Stmt",        ["WhileLoop"],         lambda p: p[0][1]),
    ("Stmt",        ["ForLoop"],           lambda p: p[0][1]),
    ("Stmt",        ["DoWhile"],           lambda p: p[0][1]),
    ("Stmt",        ["IfStmt"],            lambda p: p[0][1]),
    ("Stmt",        ["BreakStmt"],         lambda p: p[0][1]),
    ("Stmt",        ["ContinueStmt"],      lambda p: p[0][1]),
    ("Stmt",        ["CinStmt"],           lambda p: p[0][1]),
    ("Stmt",        ["CoutStmt"],          lambda p: p[0][1]),
    ("Stmt",        ["ReturnStmt"],        lambda p: p[0][1]),
    ("Stmt",        ["ExprStmt"],          lambda p: p[0][1]),

    # Block or single statement for loops / ifs
    ("BlockOrStmt", ["LBRACE", "StmtList", "RBRACE"], lambda p: p[1][1]),
    ("BlockOrStmt", ["Stmt"],                         lambda p: [p[0][1]]),

    # --- Declarations ---
    # int x;
    ("DeclStmt",    ["Type", "IDENTIFIER", "SEMI"],
        lambda p: node("Declaration", var_type=p[0][1], id=p[1][1], value=None, line=p[1][2])),
    # int x = expr;
    ("DeclStmt",    ["Type", "IDENTIFIER", "ASSIGN", "Expr", "SEMI"],
        lambda p: node("Declaration", var_type=p[0][1], id=p[1][1], value=p[3][1], line=p[1][2])),
    # int x, y;
    ("DeclStmt",    ["Type", "VarList", "SEMI"],
        lambda p: node("MultiDeclaration", var_type=p[0][1], vars=p[1][1], line=p[0][2])),

    # VarList
    ("VarList",     ["VarList", "COMMA", "VarItem"],  lambda p: p[0][1] + [p[2][1]]),
    ("VarList",     ["VarItem", "COMMA", "VarItem"],  lambda p: [p[0][1], p[2][1]]),

    ("VarItem",     ["IDENTIFIER"],
        lambda p: node("VarDecl", id=p[0][1], value=None, line=p[0][2])),
    ("VarItem",     ["IDENTIFIER", "ASSIGN", "Expr"],
        lambda p: node("VarDecl", id=p[0][1], value=p[2][1], line=p[0][2])),

    # --- Assignment ---
    ("AssignStmt",  ["IDENTIFIER", "ASSIGN", "Expr", "SEMI"],
        lambda p: node("Assignment", id=p[0][1], op="=", value=p[2][1], line=p[0][2])),

    # Compound assignments: x += expr;
    ("CompoundAssign", ["IDENTIFIER", "PLUS_ASSIGN",  "Expr", "SEMI"],
        lambda p: node("Assignment", id=p[0][1], op="+=", value=p[2][1], line=p[0][2])),
    ("CompoundAssign", ["IDENTIFIER", "MINUS_ASSIGN", "Expr", "SEMI"],
        lambda p: node("Assignment", id=p[0][1], op="-=", value=p[2][1], line=p[0][2])),
    ("CompoundAssign", ["IDENTIFIER", "TIMES_ASSIGN", "Expr", "SEMI"],
        lambda p: node("Assignment", id=p[0][1], op="*=", value=p[2][1], line=p[0][2])),
    ("CompoundAssign", ["IDENTIFIER", "DIV_ASSIGN",   "Expr", "SEMI"],
        lambda p: node("Assignment", id=p[0][1], op="/=", value=p[2][1], line=p[0][2])),

    # x++; x--;
    ("IncrStmt",    ["IDENTIFIER", "INC", "SEMI"],
        lambda p: node("IncrDecr", id=p[0][1], op="++", line=p[0][2])),
    ("IncrStmt",    ["IDENTIFIER", "DEC", "SEMI"],
        lambda p: node("IncrDecr", id=p[0][1], op="--", line=p[0][2])),

    # --- Loops ---
    ("WhileLoop",   ["WHILE", "LPAREN", "Condition", "RPAREN", "BlockOrStmt"],
        lambda p: node("WhileLoop", condition=p[2][1], body=p[4][1], line=p[0][2])),

    # for (init; cond; update) { body } or for (...) stmt
    ("ForLoop",     ["FOR", "LPAREN", "ForInit", "Condition", "SEMI", "ForUpdate", "RPAREN", "BlockOrStmt"],
        lambda p: node("ForLoop", init=p[2][1], condition=p[3][1], update=p[5][1], body=p[7][1], line=p[0][2])),

    ("ForInit",     ["Type", "IDENTIFIER", "ASSIGN", "Expr", "SEMI"],
        lambda p: node("Declaration", var_type=p[0][1], id=p[1][1], value=p[3][1], line=p[1][2])),
    ("ForInit",     ["IDENTIFIER", "ASSIGN", "Expr", "SEMI"],
        lambda p: node("Assignment", id=p[0][1], op="=", value=p[2][1], line=p[0][2])),
    ("ForInit",     ["SEMI"],  lambda p: None),

    ("ForUpdate",   ["IDENTIFIER", "INC"],
        lambda p: node("IncrDecr", id=p[0][1], op="++", line=p[0][2])),
    ("ForUpdate",   ["IDENTIFIER", "DEC"],
        lambda p: node("IncrDecr", id=p[0][1], op="--", line=p[0][2])),
    ("ForUpdate",   ["IDENTIFIER", "ASSIGN", "Expr"],
        lambda p: node("Assignment", id=p[0][1], op="=", value=p[2][1], line=p[0][2])),
    ("ForUpdate",   ["IDENTIFIER", "PLUS_ASSIGN",  "Expr"],
        lambda p: node("Assignment", id=p[0][1], op="+=", value=p[2][1], line=p[0][2])),
    ("ForUpdate",   ["IDENTIFIER", "MINUS_ASSIGN", "Expr"],
        lambda p: node("Assignment", id=p[0][1], op="-=", value=p[2][1], line=p[0][2])),
    ("ForUpdate",   [],  lambda p: None),

    # do { } while ();
    ("DoWhile",     ["DO", "BlockOrStmt", "WHILE", "LPAREN", "Condition", "RPAREN", "SEMI"],
        lambda p: node("DoWhile", body=p[1][1], condition=p[4][1], line=p[0][2])),

    # --- If / Else ---
    ("IfStmt",      ["IF", "LPAREN", "Condition", "RPAREN", "BlockOrStmt", "ElseChain"],
        lambda p: node("IfStatement", condition=p[2][1], body=p[4][1], else_body=p[5][1], line=p[0][2])),

    ("ElseChain",   ["ELSE", "IF", "LPAREN", "Condition", "RPAREN", "BlockOrStmt", "ElseChain"],
        lambda p: [node("IfStatement", condition=p[3][1], body=p[5][1], else_body=p[6][1], line=p[1][2])]),
    ("ElseChain",   ["ELSE", "BlockOrStmt"],
        lambda p: p[1][1]),
    ("ElseChain",   [],  lambda p: None),

    # --- Jump statements ---
    ("BreakStmt",    ["BREAK",    "SEMI"],  lambda p: node("BreakStatement",    line=p[0][2])),
    ("ContinueStmt", ["CONTINUE", "SEMI"],  lambda p: node("ContinueStatement", line=p[0][2])),
    ("ReturnStmt",   ["RETURN", "Expr", "SEMI"],
        lambda p: node("ReturnStatement", value=p[1][1], line=p[0][2])),
    ("ReturnStmt",   ["RETURN", "SEMI"],
        lambda p: node("ReturnStatement", value=None, line=p[0][2])),

    # --- I/O ---
    # cin >> a >> b >> ...
    ("CinStmt",     ["CIN", "CinChain", "SEMI"],
        lambda p: node("CinStatement", ids=p[1][1], line=p[0][2])),
    ("CinChain",    ["CinChain", "SHR", "IDENTIFIER"],
        lambda p: p[0][1] + [p[2][1]]),
    ("CinChain",    ["SHR", "IDENTIFIER"],
        lambda p: [p[1][1]]),

    # cout << ... << endl;
    ("CoutStmt",    ["COUT", "CoutItems", "SEMI"],
        lambda p: node("CoutStatement", items=p[1][1], line=p[0][2])),
    ("CoutItems",   ["CoutItems", "SHL", "CoutAtom"],
        lambda p: p[0][1] + [p[2][1]]),
    ("CoutItems",   ["SHL", "CoutAtom"],
        lambda p: [p[1][1]]),

    ("CoutAtom",    ["ENDL"],
        lambda p: node("CoutItem", kind="endl",   value=None)),
    ("CoutAtom",    ["STRING"],
        lambda p: node("CoutItem", kind="string", value=p[0][1])),
    ("CoutAtom",    ["Expr"],
        lambda p: node("CoutItem", kind="expr",   value=p[0][1])),

    # Expression statement (bare expression like function call)
    ("ExprStmt",    ["Expr", "SEMI"],  lambda p: node("ExprStatement", expr=p[0][1], line=p[0][2])),

    # --- Conditions ---
    ("Condition",   ["Condition", "AND", "AndCond"],
        lambda p: node("LogicalExpr", op="&&", left=p[0][1], right=p[2][1])),
    ("Condition",   ["Condition", "OR",  "AndCond"],
        lambda p: node("LogicalExpr", op="||", left=p[0][1], right=p[2][1])),
    ("Condition",   ["AndCond"],  lambda p: p[0][1]),

    ("AndCond",     ["NOT", "AndCond"],
        lambda p: node("UnaryExpr", op="!", operand=p[1][1])),
    ("AndCond",     ["Expr", "RelOp", "Expr"],
        lambda p: node("Condition", left=p[0][1], operator=p[1][1], right=p[2][1])),
    ("AndCond",     ["Expr"],  lambda p: p[0][1]),

    ("RelOp",       ["EQ"],   lambda p: "=="),
    ("RelOp",       ["NEQ"],  lambda p: "!="),
    ("RelOp",       ["LT"],   lambda p: "<"),
    ("RelOp",       ["GT"],   lambda p: ">"),
    ("RelOp",       ["LEQ"],  lambda p: "<="),
    ("RelOp",       ["GEQ"],  lambda p: ">="),

    # --- Expressions (standard precedence: Expr > Term > Unary > Factor) ---
    ("Expr",        ["Expr", "PLUS",   "Term"],
        lambda p: node("BinaryExpression", operator="+",  left=p[0][1], right=p[2][1])),
    ("Expr",        ["Expr", "MINUS",  "Term"],
        lambda p: node("BinaryExpression", operator="-",  left=p[0][1], right=p[2][1])),
    ("Expr",        ["Term"],  lambda p: p[0][1]),

    ("Term",        ["Term",  "TIMES",  "Unary"],
        lambda p: node("BinaryExpression", operator="*",  left=p[0][1], right=p[2][1])),
    ("Term",        ["Term",  "DIVIDE", "Unary"],
        lambda p: node("BinaryExpression", operator="/",  left=p[0][1], right=p[2][1])),
    ("Term",        ["Term",  "MOD",    "Unary"],
        lambda p: node("BinaryExpression", operator="%",  left=p[0][1], right=p[2][1])),
    ("Term",        ["Unary"],  lambda p: p[0][1]),

    ("Unary",       ["MINUS", "Factor"],
        lambda p: node("UnaryExpr", op="neg", operand=p[1][1])),
    ("Unary",       ["NOT",   "Factor"],
        lambda p: node("UnaryExpr", op="!",   operand=p[1][1])),
    ("Unary",       ["Factor"],  lambda p: p[0][1]),

    ("Factor",      ["LPAREN", "Expr", "RPAREN"],  lambda p: p[1][1]),
    ("Factor",      ["IDENTIFIER", "LPAREN", "ArgList", "RPAREN"],
        lambda p: node("FunctionCall", name=p[0][1], args=p[2][1], line=p[0][2])),
    ("Factor",      ["IDENTIFIER"],
        lambda p: node("Identifier", value=p[0][1], line=p[0][2])),
    ("Factor",      ["NUMBER"],
        lambda p: node("Number",     value=p[0][1], line=p[0][2])),
    ("Factor",      ["FLOAT_NUM"],
        lambda p: node("FloatNumber", value=p[0][1], line=p[0][2])),
    ("Factor",      ["STRING"],
        lambda p: node("StringLiteral", value=p[0][1], line=p[0][2])),
    ("Factor",      ["CHAR_LIT"],
        lambda p: node("CharLiteral", value=p[0][1], line=p[0][2])),
    ("Factor",      ["TRUE"],
        lambda p: node("BoolLiteral", value=True, line=p[0][2])),
    ("Factor",      ["FALSE"],
        lambda p: node("BoolLiteral", value=False, line=p[0][2])),

    # Function call argument list
    ("ArgList",     ["ArgList", "COMMA", "Expr"],  lambda p: p[0][1] + [p[2][1]]),
    ("ArgList",     ["Expr"],                      lambda p: [p[0][1]]),
    ("ArgList",     [],                            lambda p: []),
]

NON_TERMINALS = set(r[0] for r in RULES)
SYMBOLS       = TERMINALS | NON_TERMINALS | {'$'}


# ---------------------------------------------------------------------------
# SLR(1) table construction
# ---------------------------------------------------------------------------

def get_first_sets():
    first = {s: set() for s in SYMBOLS}
    first[''] = set()
    for t in TERMINALS:
        first[t].add(t)
    first['$'].add('$')

    changed = True
    while changed:
        changed = False
        for lhs, rhs, _ in RULES:
            if not rhs:
                if '' not in first[lhs]:
                    first[lhs].add('')
                    changed = True
                continue
            for sym in rhs:
                for f in first[sym]:
                    if f and f not in first[lhs]:
                        first[lhs].add(f)
                        changed = True
                if '' not in first[sym]:
                    break
            else:
                if '' not in first[lhs]:
                    first[lhs].add('')
                    changed = True
    return first


def get_follow_sets(firsts):
    follow = {n: set() for n in NON_TERMINALS}
    follow["S'"].add('$')

    changed = True
    while changed:
        changed = False
        for lhs, rhs, _ in RULES:
            for i, sym in enumerate(rhs):
                if sym not in NON_TERMINALS:
                    continue
                nxt = rhs[i + 1:]
                eps_all = True
                for ns in nxt:
                    for f in firsts[ns]:
                        if f and f not in follow[sym]:
                            follow[sym].add(f)
                            changed = True
                    if '' not in firsts[ns]:
                        eps_all = False
                        break
                if eps_all:
                    for f in follow[lhs]:
                        if f not in follow[sym]:
                            follow[sym].add(f)
                            changed = True
    return follow


def closure(items):
    c = set(items)
    changed = True
    while changed:
        changed = False
        for (ri, di) in list(c):
            rhs = RULES[ri][1]
            if di < len(rhs):
                nxt = rhs[di]
                if nxt in NON_TERMINALS:
                    for i, (lh, _, _) in enumerate(RULES):
                        if lh == nxt and (i, 0) not in c:
                            c.add((i, 0))
                            changed = True
    return frozenset(c)


def goto(items, symbol):
    moved = set()
    for (ri, di) in items:
        rhs = RULES[ri][1]
        if di < len(rhs) and rhs[di] == symbol:
            moved.add((ri, di + 1))
    return closure(moved) if moved else frozenset()


def build_parser():
    firsts  = get_first_sets()
    follows = get_follow_sets(firsts)

    I0     = closure({(0, 0)})
    states = [I0]
    state_map = {I0: 0}
    transitions = {}

    worklist = [I0]
    while worklist:
        state = worklist.pop()
        si    = state_map[state]
        for sym in SYMBOLS:
            if sym in ('$', ''):
                continue
            nxt = goto(state, sym)
            if not nxt:
                continue
            if nxt not in state_map:
                state_map[nxt] = len(states)
                states.append(nxt)
                worklist.append(nxt)
            transitions[(si, sym)] = state_map[nxt]

    action     = {}
    goto_table = {}

    for state, si in state_map.items():
        for (ri, di) in state:
            lhs, rhs, _ = RULES[ri]
            if di == len(rhs):                     # reduce / accept
                if ri == 0:
                    action[(si, '$')] = ('accept', 0)
                else:
                    for f in follows[lhs]:
                        key = (si, f)
                        if key not in action:
                            action[key] = ('reduce', ri)
                        # on conflict prefer existing (shift-reduce: keep shift)
            else:
                a = rhs[di]
                if a in TERMINALS and (si, a) in transitions:
                    action[(si, a)] = ('shift', transitions[(si, a)])

        for nt in NON_TERMINALS:
            if (si, nt) in transitions:
                goto_table[(si, nt)] = transitions[(si, nt)]

    return action, goto_table


# Cache tables across calls in the same process
_action    = None
_goto_tbl  = None


def parse(token_list):
    global _action, _goto_tbl
    if _action is None:
        print(">> Building SLR(1) parse tables (Right-Most Derivation)...")
        _action, _goto_tbl = build_parser()
        print(">> Parse tables built successfully.")

    stack        = [0]
    sym_stack    = [("$", "$", 0)]
    idx          = 0

    while True:
        state = stack[-1]
        tok   = token_list[idx]
        kind, val, line = tok[0], tok[1], tok[2]

        if kind == 'EOF':
            kind = '$'

        act = _action.get((state, kind))

        if act is None:
            expected = sorted({sym for (s, sym) in _action if s == state and sym != '$'})
            raise SyntaxErrorExt(
                f"SYNTAX ERROR at Line {line}: Unexpected token '{val}' ({kind}).\n"
                f"  Expected one of: {', '.join(expected)}"
            )

        act_type, act_val = act

        if act_type == 'shift':
            stack.append(act_val)
            sym_stack.append((kind, val, line))
            idx += 1

        elif act_type == 'reduce':
            ri           = act_val
            lhs, rhs, fn = RULES[ri]
            p            = []
            if rhs:
                p         = sym_stack[-len(rhs):]
                stack     = stack[:-len(rhs)]
                sym_stack = sym_stack[:-len(rhs)]

            try:
                result = fn(p)
            except Exception as e:
                raise SyntaxErrorExt(
                    f"Semantic action error in rule {lhs} -> {rhs}: {e}"
                )

            new_state  = stack[-1]
            goto_state = _goto_tbl.get((new_state, lhs))
            if goto_state is None:
                raise SyntaxErrorExt(
                    f"GOTO error: no transition for ({new_state}, {lhs})"
                )

            node_line = p[0][2] if p else 1
            stack.append(goto_state)
            sym_stack.append((lhs, result, node_line))

        elif act_type == 'accept':
            return sym_stack[-1][1]


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    src_file = "test_program.cpp"
    if len(sys.argv) > 1:
        src_file = sys.argv[1]

    try:
        with open(src_file, 'r') as f:
            code = f.read()
        tokens = lexer.lex(code)
        ast    = parse(tokens)
        with open("ast_output.json", 'w') as f:
            json.dump(ast, f, indent=4)
        print("SUCCESS — AST written to ast_output.json")
    except Exception as e:
        print(f"FAILED: {e}")
