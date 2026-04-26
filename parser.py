import sys
import json

class SyntaxErrorExt(Exception):
    pass

def node(ntype, **kwargs):
    d = {"type": ntype}
    d.update(kwargs)
    return d

class CSTNode:
    def __init__(self, lhs, rhs_symbols):
        self.lhs = lhs
        self.rhs_symbols = rhs_symbols

class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0
        self.current_token = self.tokens[self.pos] if self.tokens else ('EOF', 'EOF', -1)

    def advance(self):
        self.pos += 1
        if self.pos < len(self.tokens):
            self.current_token = self.tokens[self.pos]
        else:
            self.current_token = ('EOF', 'EOF', -1)

    def match(self, expected_type):
        if self.current_token[0] == expected_type:
            val = self.current_token[1]
            line = self.current_token[2]
            self.advance()
            return val, line
        else:
            raise SyntaxErrorExt(f"SYNTAX ERROR at Line {self.current_token[2]}: Expected {expected_type}, got '{self.current_token[1]}' ({self.current_token[0]})")

    def peek(self):
        return self.current_token[0]

    def parse(self):
        print(">> Initializing Top-Down Parser Engine (Recursive Descent)...")
        ast, cst = self.parse_Program()
        if self.peek() != 'EOF' and self.peek() != '$':
            raise SyntaxErrorExt(f"SYNTAX ERROR at Line {self.current_token[2]}: Unexpected token '{self.current_token[1]}' after program end.")
        
        print(">> Parse completed. Generating Right-Most Derivation sequence...")
        derivation = self.generate_rmd(cst)
        return ast, derivation

    def generate_rmd(self, cst_root):
        steps = []
        current_sentential = [cst_root]
        step_counter = 1
        
        # Gather all actual literal values for the "Final:" step
        final_literals = []
        def gather_terminals(node):
            if isinstance(node, CSTNode):
                for child in node.rhs_symbols:
                    gather_terminals(child)
            elif node != "empty":
                final_literals.append(str(node[1]))
        gather_terminals(cst_root)
        
        # Readable Token Aliases (to make it look like Joe's format)
        token_aliases = {
            'IDENTIFIER': 'id',
            'NUMBER': 'num',
            'FLOAT_NUM': 'num',
            'INT': 'type',
            'FLOAT': 'type',
            'DOUBLE': 'type',
            'CHAR': 'type',
            'BOOL': 'type',
            'VOID': 'type',
            'LBRACE': '{',
            'RBRACE': '}',
            'LPAREN': '(',
            'RPAREN': ')',
            'SEMI': ';',
            'ASSIGN': '=',
            'PLUS': '+',
            'MINUS': '-',
            'MUL': '*',
            'DIV': '/',
            'SHL': '<<',
            'SHR': '>>',
            'COUT': 'cout',
            'CIN': 'cin',
            'RETURN': 'return',
            'MAIN': 'main',
            'IF': 'if',
            'ELSE': 'else',
            'WHILE': 'while',
            'FOR': 'for'
        }
        
        while True:
            # Format current sentential form
            str_form = []
            for n in current_sentential:
                if isinstance(n, CSTNode):
                    str_form.append(n.lhs)
                elif n == "empty":
                    continue # Skip empty entirely
                else:
                    # Apply readable token alias if it exists, otherwise use the token type name
                    tok_name = n[0]
                    str_form.append(token_aliases.get(tok_name, tok_name))
            
            # Remove extra spaces if list is empty
            form_str = " ".join(str_form).strip()
            
            if step_counter == 1:
                steps.append(f"Step {step_counter}:\n{cst_root.lhs} -> {form_str}")
            else:
                steps.append(f"Step {step_counter}:\n-> {form_str}")
                
            step_counter += 1
            
            # Find RIGHT-MOST CSTNode (Strict Right-Most Derivation)
            idx = -1
            for i in range(len(current_sentential)-1, -1, -1):
                if isinstance(current_sentential[i], CSTNode):
                    idx = i
                    break
                    
            if idx == -1:
                break
                
            node_to_expand = current_sentential[idx]
            rhs = node_to_expand.rhs_symbols
            if not rhs:
                rhs = ["empty"]
            current_sentential = current_sentential[:idx] + rhs + current_sentential[idx+1:]
            
        steps.append(f"Final:\n-> {' '.join(final_literals)}\n\nVALID")
        return steps

    # --- Grammar Rules ---

    def parse_Program(self):
        inc_ast, inc_cst = self.parse_IncludeStmt()
        use_ast, use_cst = self.parse_UsingStmt()
        gl_ast, gl_cst = self.parse_GlobalList()
        
        ast = node("Program", body=[inc_ast, use_ast] + gl_ast)
        cst = CSTNode("Program", [inc_cst, use_cst, gl_cst])
        return ast, cst

    def parse_IncludeStmt(self):
        val, _ = self.match('PREPROCESSOR')
        ast = node("IncludeStatement", value=val, line=self.current_token[2])
        cst = CSTNode("IncludeStmt", [('PREPROCESSOR', val)])
        return ast, cst

    def parse_UsingStmt(self):
        self.match('USING')
        self.match('NAMESPACE')
        val, _ = self.match('IDENTIFIER')
        self.match('SEMI')
        ast = node("UsingStatement", ns=val, line=self.current_token[2])
        cst = CSTNode("UsingStmt", [('USING', 'using'), ('NAMESPACE', 'namespace'), ('IDENTIFIER', val), ('SEMI', ';')])
        return ast, cst

    def parse_GlobalList(self):
        ast_list = []
        cst_list = []
        
        while self.peek() in ('INT', 'FLOAT', 'DOUBLE', 'CHAR', 'BOOL', 'VOID', 'CONST'):
            g_ast, g_cst = self.parse_Global()
            ast_list.append(g_ast)
            
            # Left recursion flattening for CST: GlobalList -> GlobalList Global
            if not cst_list:
                cst_list = [CSTNode("GlobalList", ["empty"]), g_cst]
            else:
                cst_list = [CSTNode("GlobalList", cst_list), g_cst]
                
        if not cst_list:
            cst_list = ["empty"]
            
        return ast_list, CSTNode("GlobalList", cst_list) if isinstance(cst_list, list) else cst_list

    def parse_Global(self):
        # Could be FunctionDef or Declaration (both start with Type)
        # We need to peek ahead
        saved_pos = self.pos
        typ_ast, typ_cst = self.parse_Type()
        
        if self.peek() == 'MAIN':
            self.pos = saved_pos
            self.current_token = self.tokens[self.pos]
            f_ast, f_cst = self.parse_FunctionDef()
            return f_ast, CSTNode("Global", [f_cst])
            
        # It's an identifier. Could be function or decl.
        self.match('IDENTIFIER')
        if self.peek() == 'LPAREN':
            self.pos = saved_pos
            self.current_token = self.tokens[self.pos]
            f_ast, f_cst = self.parse_FunctionDef()
            return f_ast, CSTNode("Global", [f_cst])
        else:
            self.pos = saved_pos
            self.current_token = self.tokens[self.pos]
            d_ast, d_cst = self.parse_Declaration()
            return d_ast, CSTNode("Global", [d_cst])

    def parse_FunctionDef(self):
        typ_ast, typ_cst = self.parse_Type()
        line = self.current_token[2]
        
        if self.peek() == 'MAIN':
            name, _ = self.match('MAIN')
        else:
            name, _ = self.match('IDENTIFIER')
            
        self.match('LPAREN')
        p_ast, p_cst = self.parse_ParamList()
        self.match('RPAREN')
        self.match('LBRACE')
        s_ast, s_cst = self.parse_StatementList()
        self.match('RBRACE')
        
        if name == 'main':
            ast = node("MainFunction", params=p_ast, body=s_ast, line=line)
        else:
            ast = node("FunctionDefinition", name=name, return_type=typ_ast, params=p_ast, body=s_ast, line=line)
            
        cst = CSTNode("FunctionDef", [
            typ_cst, 
            ('MAIN' if name == 'main' else 'IDENTIFIER', name), 
            ('LPAREN', '('), p_cst, ('RPAREN', ')'), 
            ('LBRACE', '{'), s_cst, ('RBRACE', '}')
        ])
        return ast, cst

    def parse_ParamList(self):
        if self.peek() in ('INT', 'FLOAT', 'DOUBLE', 'CHAR', 'BOOL', 'VOID', 'CONST'):
            ast_list = []
            cst_list = []
            
            p_ast, p_cst = self.parse_Param()
            ast_list.append(p_ast)
            cst_list = [p_cst]
            
            while self.peek() == 'COMMA':
                self.match('COMMA')
                p_ast, p_cst = self.parse_Param()
                ast_list.append(p_ast)
                cst_list = [CSTNode("ParamItems", cst_list), ('COMMA', ','), p_cst]
                
            return ast_list, CSTNode("ParamList", [CSTNode("ParamItems", cst_list)])
        else:
            return [], CSTNode("ParamList", ["empty"])

    def parse_Param(self):
        typ_ast, typ_cst = self.parse_Type()
        id_val, line = self.match('IDENTIFIER')
        return node("Parameter", var_type=typ_ast, id=id_val, line=line), CSTNode("Param", [typ_cst, ('IDENTIFIER', id_val)])

    def parse_Type(self):
        if self.peek() == 'CONST':
            self.match('CONST')
            t_tok = self.peek()
            t_val, _ = self.match(t_tok)
            return f"const {t_val.lower()}", CSTNode("Type", [('CONST', 'const'), (t_tok, t_val)])
        else:
            t_tok = self.peek()
            t_val, _ = self.match(t_tok)
            return t_val.lower(), CSTNode("Type", [(t_tok, t_val)])

    def parse_StatementList(self):
        ast_list = []
        cst_list = []
        
        while self.peek() not in ('RBRACE', 'EOF', '$'):
            s_ast, s_cst = self.parse_Statement()
            ast_list.append(s_ast)
            
            # Left recursion flattening for CST: StatementList -> StatementList Statement
            if not cst_list:
                cst_list = [CSTNode("StatementList", ["empty"]), s_cst]
            else:
                cst_list = [CSTNode("StatementList", cst_list), s_cst]
                
        if not cst_list:
            cst_list = ["empty"]
            
        return ast_list, CSTNode("StatementList", cst_list) if isinstance(cst_list, list) else cst_list

    def parse_Statement(self):
        if self.peek() in ('INT', 'FLOAT', 'DOUBLE', 'CHAR', 'BOOL', 'VOID', 'CONST'):
            ast, cst = self.parse_Declaration()
            return ast, CSTNode("Statement", [cst])
        elif self.peek() == 'WHILE':
            ast, cst = self.parse_WhileLoop()
            return ast, CSTNode("Statement", [cst])
        elif self.peek() == 'FOR':
            ast, cst = self.parse_ForLoop()
            return ast, CSTNode("Statement", [cst])
        elif self.peek() == 'DO':
            ast, cst = self.parse_DoWhile()
            return ast, CSTNode("Statement", [cst])
        elif self.peek() == 'IF':
            ast, cst = self.parse_IfStatement()
            return ast, CSTNode("Statement", [cst])
        elif self.peek() == 'BREAK':
            ast, cst = self.parse_BreakStmt()
            return ast, CSTNode("Statement", [cst])
        elif self.peek() == 'CONTINUE':
            ast, cst = self.parse_ContinueStmt()
            return ast, CSTNode("Statement", [cst])
        elif self.peek() == 'CIN':
            ast, cst = self.parse_CinStmt()
            return ast, CSTNode("Statement", [cst])
        elif self.peek() == 'COUT':
            ast, cst = self.parse_CoutStmt()
            return ast, CSTNode("Statement", [cst])
        elif self.peek() == 'RETURN':
            ast, cst = self.parse_ReturnStmt()
            return ast, CSTNode("Statement", [cst])
        elif self.peek() == 'IDENTIFIER':
            # Could be Assignment, Increment, Decrement, or Function Call (Expr)
            saved_pos = self.pos
            self.match('IDENTIFIER')
            nxt = self.peek()
            self.pos = saved_pos
            self.current_token = self.tokens[self.pos]
            
            if nxt in ('ASSIGN', 'PLUS_ASSIGN', 'MINUS_ASSIGN', 'TIMES_ASSIGN', 'DIV_ASSIGN', 'INC', 'DEC'):
                ast, cst = self.parse_Assignment()
                return ast, CSTNode("Statement", [cst])
            else:
                line = self.current_token[2]
                expr_ast, expr_cst = self.parse_Expression()
                self.match('SEMI')
                return node("ExprStatement", expr=expr_ast, line=line), CSTNode("Statement", [expr_cst, ('SEMI', ';')])
        else:
            # Maybe ExprStmt
            line = self.current_token[2]
            expr_ast, expr_cst = self.parse_Expression()
            self.match('SEMI')
            return node("ExprStatement", expr=expr_ast, line=line), CSTNode("Statement", [expr_cst, ('SEMI', ';')])

    def parse_Declaration(self):
        typ_ast, typ_cst = self.parse_Type()
        line = self.current_token[2]
        
        # Check if it's a VarList
        saved_pos = self.pos
        self.match('IDENTIFIER')
        is_list = False
        if self.peek() in ('COMMA',):
            is_list = True
        elif self.peek() == 'ASSIGN':
            self.match('ASSIGN')
            # skip expr
            while self.peek() not in ('SEMI', 'COMMA', 'EOF'):
                self.advance()
            if self.peek() == 'COMMA':
                is_list = True
        
        self.pos = saved_pos
        self.current_token = self.tokens[self.pos]
        
        if is_list:
            vars_ast = []
            cst_list = []
            
            id_val, _ = self.match('IDENTIFIER')
            if self.peek() == 'ASSIGN':
                self.match('ASSIGN')
                v_expr_ast, v_expr_cst = self.parse_Expression()
                vars_ast.append(node("VarDecl", id=id_val, value=v_expr_ast, line=line))
                cst_list = [CSTNode("VarItem", [('IDENTIFIER', id_val), ('ASSIGN', '='), v_expr_cst])]
            else:
                vars_ast.append(node("VarDecl", id=id_val, value=None, line=line))
                cst_list = [CSTNode("VarItem", [('IDENTIFIER', id_val)])]
                
            while self.peek() == 'COMMA':
                self.match('COMMA')
                id_val, _ = self.match('IDENTIFIER')
                if self.peek() == 'ASSIGN':
                    self.match('ASSIGN')
                    v_expr_ast, v_expr_cst = self.parse_Expression()
                    vars_ast.append(node("VarDecl", id=id_val, value=v_expr_ast, line=line))
                    cst_list = [CSTNode("VarList", cst_list), ('COMMA', ','), CSTNode("VarItem", [('IDENTIFIER', id_val), ('ASSIGN', '='), v_expr_cst])]
                else:
                    vars_ast.append(node("VarDecl", id=id_val, value=None, line=line))
                    cst_list = [CSTNode("VarList", cst_list), ('COMMA', ','), CSTNode("VarItem", [('IDENTIFIER', id_val)])]
            
            self.match('SEMI')
            ast = node("MultiDeclaration", var_type=typ_ast, vars=vars_ast, line=line)
            return ast, CSTNode("Declaration", [typ_cst, CSTNode("VarList", cst_list), ('SEMI', ';')])
        else:
            id_val, _ = self.match('IDENTIFIER')
            if self.peek() == 'ASSIGN':
                self.match('ASSIGN')
                expr_ast, expr_cst = self.parse_Expression()
                self.match('SEMI')
                ast = node("Declaration", var_type=typ_ast, id=id_val, value=expr_ast, line=line)
                return ast, CSTNode("Declaration", [typ_cst, ('IDENTIFIER', id_val), ('ASSIGN', '='), expr_cst, ('SEMI', ';')])
            else:
                self.match('SEMI')
                ast = node("Declaration", var_type=typ_ast, id=id_val, value=None, line=line)
                return ast, CSTNode("Declaration", [typ_cst, ('IDENTIFIER', id_val), ('SEMI', ';')])

    def parse_Assignment(self):
        line = self.current_token[2]
        id_val, _ = self.match('IDENTIFIER')
        
        if self.peek() == 'INC':
            self.match('INC')
            self.match('SEMI')
            return node("IncrDecr", id=id_val, op="++", line=line), CSTNode("Assignment", [('IDENTIFIER', id_val), ('INC', '++'), ('SEMI', ';')])
        elif self.peek() == 'DEC':
            self.match('DEC')
            self.match('SEMI')
            return node("IncrDecr", id=id_val, op="--", line=line), CSTNode("Assignment", [('IDENTIFIER', id_val), ('DEC', '--'), ('SEMI', ';')])
        else:
            op_tok = self.peek()
            op_val = self.current_token[1]
            self.advance()
            expr_ast, expr_cst = self.parse_Expression()
            self.match('SEMI')
            return node("Assignment", id=id_val, op=op_val, value=expr_ast, line=line), CSTNode("Assignment", [('IDENTIFIER', id_val), (op_tok, op_val), expr_cst, ('SEMI', ';')])

    def parse_WhileLoop(self):
        line = self.current_token[2]
        self.match('WHILE')
        self.match('LPAREN')
        cond_ast, cond_cst = self.parse_Condition()
        self.match('RPAREN')
        body_ast, body_cst = self.parse_BlockOrStmt()
        return node("WhileLoop", condition=cond_ast, body=body_ast, line=line), CSTNode("WhileLoop", [('WHILE', 'while'), ('LPAREN', '('), cond_cst, ('RPAREN', ')'), body_cst])

    def parse_ForLoop(self):
        line = self.current_token[2]
        self.match('FOR')
        self.match('LPAREN')
        
        # Init
        if self.peek() in ('INT', 'FLOAT', 'DOUBLE', 'CHAR', 'BOOL', 'CONST'):
            typ_ast, typ_cst = self.parse_Type()
            id_val, l2 = self.match('IDENTIFIER')
            self.match('ASSIGN')
            expr_ast, expr_cst = self.parse_Expression()
            self.match('SEMI')
            init_ast = node("Declaration", var_type=typ_ast, id=id_val, value=expr_ast, line=l2)
            init_cst = CSTNode("ForInit", [typ_cst, ('IDENTIFIER', id_val), ('ASSIGN', '='), expr_cst, ('SEMI', ';')])
        elif self.peek() == 'IDENTIFIER':
            id_val, l2 = self.match('IDENTIFIER')
            self.match('ASSIGN')
            expr_ast, expr_cst = self.parse_Expression()
            self.match('SEMI')
            init_ast = node("Assignment", id=id_val, op="=", value=expr_ast, line=l2)
            init_cst = CSTNode("ForInit", [('IDENTIFIER', id_val), ('ASSIGN', '='), expr_cst, ('SEMI', ';')])
        else:
            self.match('SEMI')
            init_ast = None
            init_cst = CSTNode("ForInit", [('SEMI', ';')])
            
        # Cond
        cond_ast, cond_cst = self.parse_Condition()
        self.match('SEMI')
        
        # Update
        if self.peek() == 'IDENTIFIER':
            id_val, l2 = self.match('IDENTIFIER')
            if self.peek() == 'INC':
                self.match('INC')
                upd_ast = node("IncrDecr", id=id_val, op="++", line=l2)
                upd_cst = CSTNode("ForUpdate", [('IDENTIFIER', id_val), ('INC', '++')])
            elif self.peek() == 'DEC':
                self.match('DEC')
                upd_ast = node("IncrDecr", id=id_val, op="--", line=l2)
                upd_cst = CSTNode("ForUpdate", [('IDENTIFIER', id_val), ('DEC', '--')])
            else:
                op_tok = self.peek()
                op_val = self.current_token[1]
                self.advance()
                expr_ast, expr_cst = self.parse_Expression()
                upd_ast = node("Assignment", id=id_val, op=op_val, value=expr_ast, line=l2)
                upd_cst = CSTNode("ForUpdate", [('IDENTIFIER', id_val), (op_tok, op_val), expr_cst])
        else:
            upd_ast = None
            upd_cst = CSTNode("ForUpdate", ["empty"])
            
        self.match('RPAREN')
        body_ast, body_cst = self.parse_BlockOrStmt()
        
        return node("ForLoop", init=init_ast, condition=cond_ast, update=upd_ast, body=body_ast, line=line), CSTNode("ForLoop", [('FOR', 'for'), ('LPAREN', '('), init_cst, cond_cst, ('SEMI', ';'), upd_cst, ('RPAREN', ')'), body_cst])

    def parse_DoWhile(self):
        line = self.current_token[2]
        self.match('DO')
        body_ast, body_cst = self.parse_BlockOrStmt()
        self.match('WHILE')
        self.match('LPAREN')
        cond_ast, cond_cst = self.parse_Condition()
        self.match('RPAREN')
        self.match('SEMI')
        return node("DoWhile", body=body_ast, condition=cond_ast, line=line), CSTNode("DoWhile", [('DO', 'do'), body_cst, ('WHILE', 'while'), ('LPAREN', '('), cond_cst, ('RPAREN', ')'), ('SEMI', ';')])

    def parse_IfStatement(self):
        line = self.current_token[2]
        self.match('IF')
        self.match('LPAREN')
        cond_ast, cond_cst = self.parse_Condition()
        self.match('RPAREN')
        body_ast, body_cst = self.parse_BlockOrStmt()
        else_ast, else_cst = self.parse_ElsePart()
        return node("IfStatement", condition=cond_ast, body=body_ast, else_body=else_ast, line=line), CSTNode("IfStatement", [('IF', 'if'), ('LPAREN', '('), cond_cst, ('RPAREN', ')'), body_cst, else_cst])

    def parse_ElsePart(self):
        if self.peek() == 'ELSE':
            line = self.current_token[2]
            self.match('ELSE')
            if self.peek() == 'IF':
                self.match('IF')
                self.match('LPAREN')
                cond_ast, cond_cst = self.parse_Condition()
                self.match('RPAREN')
                body_ast, body_cst = self.parse_BlockOrStmt()
                else_ast, else_cst = self.parse_ElsePart()
                return [node("IfStatement", condition=cond_ast, body=body_ast, else_body=else_ast, line=line)], CSTNode("ElsePart", [('ELSE', 'else'), ('IF', 'if'), ('LPAREN', '('), cond_cst, ('RPAREN', ')'), body_cst, else_cst])
            else:
                body_ast, body_cst = self.parse_BlockOrStmt()
                return body_ast, CSTNode("ElsePart", [('ELSE', 'else'), body_cst])
        return None, CSTNode("ElsePart", ["empty"])

    def parse_BlockOrStmt(self):
        if self.peek() == 'LBRACE':
            self.match('LBRACE')
            ast_list, cst_list = self.parse_StatementList()
            self.match('RBRACE')
            return ast_list, CSTNode("BlockOrStmt", [('LBRACE', '{'), cst_list, ('RBRACE', '}')])
        else:
            ast, cst = self.parse_Statement()
            return [ast], CSTNode("BlockOrStmt", [cst])

    def parse_BreakStmt(self):
        line = self.current_token[2]
        self.match('BREAK')
        self.match('SEMI')
        return node("BreakStatement", line=line), CSTNode("BreakStmt", [('BREAK', 'break'), ('SEMI', ';')])

    def parse_ContinueStmt(self):
        line = self.current_token[2]
        self.match('CONTINUE')
        self.match('SEMI')
        return node("ContinueStatement", line=line), CSTNode("ContinueStmt", [('CONTINUE', 'continue'), ('SEMI', ';')])

    def parse_ReturnStmt(self):
        line = self.current_token[2]
        self.match('RETURN')
        if self.peek() == 'SEMI':
            self.match('SEMI')
            return node("ReturnStatement", value=None, line=line), CSTNode("ReturnStmt", [('RETURN', 'return'), ('SEMI', ';')])
        else:
            expr_ast, expr_cst = self.parse_Expression()
            self.match('SEMI')
            return node("ReturnStatement", value=expr_ast, line=line), CSTNode("ReturnStmt", [('RETURN', 'return'), expr_cst, ('SEMI', ';')])

    def parse_CinStmt(self):
        line = self.current_token[2]
        self.match('CIN')
        ids = []
        cst_list = None
        while self.peek() == 'SHR':
            self.match('SHR')
            id_val, _ = self.match('IDENTIFIER')
            ids.append(id_val)
            if cst_list is None:
                cst_list = [('SHR', '>>'), ('IDENTIFIER', id_val)]
            else:
                cst_list = [CSTNode("CinChain", cst_list), ('SHR', '>>'), ('IDENTIFIER', id_val)]
        self.match('SEMI')
        
        # Adjust CST for the loop to match original grammar style (optional, but good for right-most)
        cst_node = CSTNode("CinChain", cst_list) if cst_list else CSTNode("CinChain", ["empty"])
        return node("CinStatement", ids=ids, line=line), CSTNode("CinStmt", [('CIN', 'cin'), cst_node, ('SEMI', ';')])

    def parse_CoutStmt(self):
        line = self.current_token[2]
        self.match('COUT')
        items = []
        cst_list = None
        while self.peek() == 'SHL':
            self.match('SHL')
            if self.peek() == 'ENDL':
                self.match('ENDL')
                items.append(node("CoutItem", kind="endl", value=None))
                atom_cst = CSTNode("CoutAtom", [('ENDL', 'endl')])
            elif self.peek() == 'STRING':
                val, _ = self.match('STRING')
                items.append(node("CoutItem", kind="string", value=val))
                atom_cst = CSTNode("CoutAtom", [('STRING', val)])
            else:
                expr_ast, expr_cst = self.parse_Expression()
                items.append(node("CoutItem", kind="expr", value=expr_ast))
                atom_cst = CSTNode("CoutAtom", [expr_cst])
                
            if cst_list is None:
                cst_list = [('SHL', '<<'), atom_cst]
            else:
                cst_list = [CSTNode("CoutItems", cst_list), ('SHL', '<<'), atom_cst]
                
        self.match('SEMI')
        cst_node = CSTNode("CoutItems", cst_list) if cst_list else CSTNode("CoutItems", ["empty"])
        return node("CoutStatement", items=items, line=line), CSTNode("CoutStmt", [('COUT', 'cout'), cst_node, ('SEMI', ';')])

    def parse_Condition(self):
        ast, cst = self.parse_AndCond()
        while self.peek() == 'OR':
            self.match('OR')
            right_ast, right_cst = self.parse_AndCond()
            ast = node("LogicalExpr", op="||", left=ast, right=right_ast)
            cst = CSTNode("Condition", [cst, ('OR', '||'), right_cst])
        return ast, cst

    def parse_AndCond(self):
        ast, cst = self.parse_CondAtom()
        while self.peek() == 'AND':
            self.match('AND')
            right_ast, right_cst = self.parse_CondAtom()
            ast = node("LogicalExpr", op="&&", left=ast, right=right_ast)
            cst = CSTNode("AndCond", [cst, ('AND', '&&'), right_cst])
        return ast, cst

    def parse_CondAtom(self):
        if self.peek() == 'NOT':
            self.match('NOT')
            inner_ast, inner_cst = self.parse_CondAtom()
            return node("UnaryExpr", op="!", operand=inner_ast), CSTNode("CondAtom", [('NOT', '!'), inner_cst])
        else:
            left_ast, left_cst = self.parse_Expression()
            if self.peek() in ('EQ', 'NEQ', 'LT', 'GT', 'LEQ', 'GEQ'):
                op_tok = self.peek()
                op_val = self.current_token[1]
                self.advance()
                right_ast, right_cst = self.parse_Expression()
                
                # RelOp CST
                rel_cst = CSTNode("RelOp", [(op_tok, op_val)])
                
                # Convert operator for AST
                if op_tok == 'EQ': op = '=='
                elif op_tok == 'NEQ': op = '!='
                elif op_tok == 'LEQ': op = '<='
                elif op_tok == 'GEQ': op = '>='
                else: op = op_val
                
                return node("Condition", left=left_ast, operator=op, right=right_ast), CSTNode("CondAtom", [left_cst, rel_cst, right_cst])
            return left_ast, CSTNode("CondAtom", [left_cst])

    def parse_Expression(self):
        ast, cst = self.parse_Term()
        while self.peek() in ('PLUS', 'MINUS'):
            op_tok = self.peek()
            op_val = self.current_token[1]
            self.advance()
            right_ast, right_cst = self.parse_Term()
            ast = node("BinaryExpression", operator="+" if op_tok == 'PLUS' else "-", left=ast, right=right_ast)
            cst = CSTNode("Expression", [cst, (op_tok, op_val), right_cst])
        return ast, cst

    def parse_Term(self):
        ast, cst = self.parse_Unary()
        while self.peek() in ('TIMES', 'DIVIDE', 'MOD'):
            op_tok = self.peek()
            op_val = self.current_token[1]
            self.advance()
            right_ast, right_cst = self.parse_Unary()
            op = "*" if op_tok == 'TIMES' else ("/" if op_tok == 'DIVIDE' else "%")
            ast = node("BinaryExpression", operator=op, left=ast, right=right_ast)
            cst = CSTNode("Term", [cst, (op_tok, op_val), right_cst])
        return ast, cst

    def parse_Unary(self):
        if self.peek() == 'MINUS':
            self.match('MINUS')
            fac_ast, fac_cst = self.parse_Factor()
            return node("UnaryExpr", op="neg", operand=fac_ast), CSTNode("Unary", [('MINUS', '-'), fac_cst])
        elif self.peek() == 'NOT':
            self.match('NOT')
            fac_ast, fac_cst = self.parse_Factor()
            return node("UnaryExpr", op="!", operand=fac_ast), CSTNode("Unary", [('NOT', '!'), fac_cst])
        else:
            ast, cst = self.parse_Factor()
            return ast, CSTNode("Unary", [cst])

    def parse_Factor(self):
        line = self.current_token[2]
        if self.peek() == 'LPAREN':
            self.match('LPAREN')
            expr_ast, expr_cst = self.parse_Expression()
            self.match('RPAREN')
            return expr_ast, CSTNode("Factor", [('LPAREN', '('), expr_cst, ('RPAREN', ')')])
        elif self.peek() == 'NUMBER':
            val, _ = self.match('NUMBER')
            return node("Number", value=val, line=line), CSTNode("Factor", [('NUMBER', val)])
        elif self.peek() == 'FLOAT_NUM':
            val, _ = self.match('FLOAT_NUM')
            return node("FloatNumber", value=val, line=line), CSTNode("Factor", [('FLOAT_NUM', val)])
        elif self.peek() == 'STRING':
            val, _ = self.match('STRING')
            return node("StringLiteral", value=val, line=line), CSTNode("Factor", [('STRING', val)])
        elif self.peek() == 'CHAR_LIT':
            val, _ = self.match('CHAR_LIT')
            return node("CharLiteral", value=val, line=line), CSTNode("Factor", [('CHAR_LIT', val)])
        elif self.peek() == 'TRUE':
            val, _ = self.match('TRUE')
            return node("BoolLiteral", value=True, line=line), CSTNode("Factor", [('TRUE', 'true')])
        elif self.peek() == 'FALSE':
            val, _ = self.match('FALSE')
            return node("BoolLiteral", value=False, line=line), CSTNode("Factor", [('FALSE', 'false')])
        elif self.peek() == 'IDENTIFIER':
            id_val, _ = self.match('IDENTIFIER')
            if self.peek() == 'LPAREN':
                self.match('LPAREN')
                args_ast, args_cst = self.parse_ArgList()
                self.match('RPAREN')
                return node("FunctionCall", name=id_val, args=args_ast, line=line), CSTNode("Factor", [('IDENTIFIER', id_val), ('LPAREN', '('), args_cst, ('RPAREN', ')')])
            else:
                return node("Identifier", value=id_val, line=line), CSTNode("Factor", [('IDENTIFIER', id_val)])
        else:
            raise SyntaxErrorExt(f"SYNTAX ERROR at Line {line}: Unexpected token '{self.current_token[1]}' in Factor.")

    def parse_ArgList(self):
        if self.peek() in ('RPAREN', 'EOF'):
            return [], CSTNode("ArgList", ["empty"])
            
        ast_list = []
        cst_list = []
        
        expr_ast, expr_cst = self.parse_Expression()
        ast_list.append(expr_ast)
        cst_list = [expr_cst]
        
        while self.peek() == 'COMMA':
            self.match('COMMA')
            expr_ast, expr_cst = self.parse_Expression()
            ast_list.append(expr_ast)
            cst_list = [CSTNode("ArgList", cst_list), ('COMMA', ','), expr_cst]
            
        return ast_list, CSTNode("ArgList", cst_list)

def parse(tokens):
    parser = Parser(tokens)
    return parser.parse()
