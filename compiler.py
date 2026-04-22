import sys
import lexer
import parser
from semantic import SemanticAnalyzer, SemanticError
from icg import TACGenerator, TACOptimizer
import json

def compile_code(input_file):
    try:
        with open(input_file, 'r') as f:
            code = f.read()
    except FileNotFoundError:
        print(f"Error: {input_file} not found.")
        sys.exit(1)

    print(f"Compiling: {input_file}...\n")

    # Phase 1
    try:
        tokens = lexer.lex(code)
        print("[1/4] Lexical Analysis:          PASS")
    except lexer.LexicalError as e:
        print(f"[1/4] Lexical Analysis:          FAILED\n{e}")
        sys.exit(1)

    with open("tokens_output.txt", "w") as f:
        for kind, value, ln in tokens:
            f.write(f"<{kind}, {value}, Line: {ln}>\n")

    # Phase 2
    try:
        ast = parser.parse(tokens)
        print("[2/4] Syntax Analysis (SLR-1):   PASS")
    except parser.SyntaxErrorExt as e:
        print(f"[2/4] Syntax Analysis (SLR-1):   FAILED\n{e}")
        sys.exit(1)

    with open("ast_output.json", "w") as f:
        json.dump(ast, f, indent=4)

    # Phase 3
    try:
        analyzer     = SemanticAnalyzer(ast)
        symbol_table = analyzer.analyze()
        print("[3/4] Semantic Analysis:         PASS")
    except SemanticError as e:
        print(f"[3/4] Semantic Analysis:         FAILED\n{e}")
        sys.exit(1)

    with open("symbol_table.json", "w") as f:
        json.dump(symbol_table, f, indent=4)

    # Phase 4
    try:
        raw_tac = TACGenerator(ast).generate()
        with open("tac_unoptimized.txt", "w") as f:
            f.write('\n'.join(raw_tac))

        opt_tac = TACOptimizer(raw_tac).optimize()
        with open("tac_optimized.txt", "w") as f:
            f.write('\n'.join(opt_tac))

        print("[4/4] Intermediate Code Gen:     PASS")
    except Exception as e:
        print(f"[4/4] Intermediate Code Gen:     FAILED\n{e}")
        sys.exit(1)

    print("\nCompilation completed successfully!")
    print("\n--- OUTPUT FILES ---")
    print("  tokens_output.txt   | Phase 1: Lexical tokens")
    print("  ast_output.json     | Phase 2: Abstract Syntax Tree")
    print("  symbol_table.json   | Phase 3: Semantic Symbol Table")
    print("  tac_unoptimized.txt | Phase 4: Unoptimized TAC")
    print("  tac_optimized.txt   | Phase 4: Optimized TAC")
    print("\n--- SYMBOL TABLE ---")
    for var, vtype in symbol_table.items():
        print(f"  {var}: {vtype}")

if __name__ == "__main__":
    input_file = "test_program.cpp"
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    compile_code(input_file)
