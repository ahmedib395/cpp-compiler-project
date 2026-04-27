import json
from http.server import HTTPServer, BaseHTTPRequestHandler

import lexer
import parser
from semantic import SemanticAnalyzer, SemanticError
from icg import TACGenerator, TACOptimizer, TACExecutor


class CompilerHTTPRequestHandler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            with open('index.html', 'rb') as f:
                self.wfile.write(f.read())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        length = int(self.headers['Content-Length'])
        raw    = self.rfile.read(length)
        try:
            req = json.loads(raw.decode('utf-8'))
        except Exception:
            req = {}

        if self.path == '/compile':
            self._handle_compile(req)
        elif self.path == '/run':
            self._handle_run(req)
        else:
            self.send_response(404)
            self.end_headers()

    # ------------------------------------------------------------------
    # /compile  — runs phases 1-4, returns phase data + read_count
    # ------------------------------------------------------------------
    def _handle_compile(self, req):
        code = req.get('code', '')

        response = {
            "success":     True,
            "console":     "",
            "tokens":      "",
            "ast":         "",
            "symbol_table":"",
            "tac":         "",
            "read_count":  0,
            "error_phase": 0,
        }
        response["console"] += "Starting Compilation Build...\n\n"

        # Phase 1 — Lexical
        try:
            tokens = lexer.lex(code)
            response["console"] += "[1/4] Lexical Analysis:          PASS\n"
            disp = [t for t in tokens if t[0] != 'EOF']
            response["tokens"] = "\n".join(
                f"<{lexer.get_display_type(k)}, {v}, Line: {l}>" for k, v, l in disp
            )
        except lexer.LexicalError as e:
            response.update({"success": False, "error_phase": 1,
                             "console": response["console"] + f"[1/4] Lexical Analysis:          FAILED\n{e}\n",
                             "tokens": f"ERROR:\n{e}"})
            self._send_json(response); return

        # Phase 2 — Syntax
        try:
            ast, derivation = parser.parse(tokens)
            response["console"] += "[2/4] Top-Down Expansion (Parser):   PASS\n"
            barrier = "\n\n" + "="*70 + "\n" + " "*24 + "ABSTRACT SYNTAX TREE\n" + "="*70 + "\n\n"
            response["ast"]      = "--- TOP-DOWN EXPANSION (RIGHT-MOST DERIVATION STEPS) ---\n\n" + "\n\n".join(derivation) + barrier + json.dumps(ast, indent=4)
        except parser.SyntaxErrorExt as e:
            response.update({"success": False, "error_phase": 2,
                             "console": response["console"] + f"[2/4] Top-Down Expansion (Parser):   FAILED\n{e}\n",
                             "ast": f"ERROR:\n{e}"})
            self._send_json(response); return

        # Phase 3 — Semantic
        try:
            analyzer = SemanticAnalyzer(ast)
            sym      = analyzer.analyze()
            response["console"]       += "[3/4] Semantic Analysis:         PASS\n"
            response["symbol_table"]   = json.dumps(sym, indent=4)
        except SemanticError as e:
            response.update({"success": False, "error_phase": 3,
                             "console": response["console"] + f"[3/4] Semantic Analysis:         FAILED\n{e}\n",
                             "symbol_table": f"ERROR:\n{e}"})
            self._send_json(response); return

        # Phase 4 — ICG
        try:
            raw_tac = TACGenerator(ast).generate()
            opt_tac = TACOptimizer(raw_tac).optimize()
            response["console"] += "[4/4] Interm. Code Gen:          PASS\n"
            response["tac"] = (
                "=== UNOPTIMIZED TAC ===\n" + "\n".join(raw_tac) +
                "\n\n=== OPTIMIZED TAC ===\n"  + "\n".join(opt_tac)
            )
            # Count how many 'read' instructions are in the optimised TAC
            response["read_count"] = sum(1 for line in opt_tac if line.startswith("read "))
        except Exception as e:
            response.update({"success": False, "error_phase": 4,
                             "console": response["console"] + f"[4/4] Interm. Code Gen:          FAILED\n{e}\n",
                             "tac": f"ERROR:\n{e}"})
            self._send_json(response); return

        response["console"] += "\n========================\nBUILD SUCCESSFUL!\n"
        if response["read_count"] > 0:
            response["console"] += (
                f"\n>> Program requires {response['read_count']} input value(s).\n"
                ">> Enter them in the Output terminal.\n"
            )

        self._send_json(response)

    # ------------------------------------------------------------------
    # /run  — full compile + Execute with provided stdin values
    # ------------------------------------------------------------------
    def _handle_run(self, req):
        response = {"success": True, "program_output": "", "error": ""}
        try:
            code         = req.get('code', '')
            stdin_values = req.get('stdin', [])

            tokens  = lexer.lex(code)
            ast, _     = parser.parse(tokens)
            SemanticAnalyzer(ast).analyze()
            raw_tac = TACGenerator(ast).generate()
            opt_tac = TACOptimizer(raw_tac).optimize()

            # Parse stdin types
            parsed = []
            for s in (stdin_values if isinstance(stdin_values, list) else []):
                s = str(s).strip()
                try:    parsed.append(int(s));   continue
                except ValueError: pass
                try:    parsed.append(float(s)); continue
                except ValueError: pass
                parsed.append(s)

            executor = TACExecutor(opt_tac, stdin_values=parsed)
            output   = executor.run()
            response["program_output"] = output if output.strip() else "(no output)"
        except Exception as e:
            response["success"]        = False
            response["error"]          = str(e)
            response["program_output"] = f"(runtime error: {e})"

        self._send_json(response)



    # ------------------------------------------------------------------
    def _cors(self):
        self.send_header('Access-Control-Allow-Origin',  '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def _send_json(self, data):
        body = json.dumps(data).encode('utf-8')
        self.send_response(200)
        self._cors()
        self.send_header('Content-type',   'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


if __name__ == '__main__':
    import os
    # For deployment (Render, Heroku, etc.), use the PORT env var. Default to 8000 for local.
    port = int(os.environ.get('PORT', 8000))
    # Bind to 0.0.0.0 to allow external connections on cloud hosts
    httpd = HTTPServer(('0.0.0.0', port), CompilerHTTPRequestHandler)
    
    print("========================================")
    print(f"  C++ Compiler Web IDE — started!")
    print(f"  -> Listening on port {port}")
    print("========================================")
    httpd.serve_forever()
