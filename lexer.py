import re
import sys

class LexicalError(Exception):
    pass

TOKEN_TYPES = [
    ('COMMENT',      r'//.*|/\*[\s\S]*?\*/'),
    ('WHITESPACE',   r'\s+'),
    ('PREPROCESSOR', r'#\s*include\s*(<[a-zA-Z0-9_.]+>|"[^"]*")'),
    ('STRING',       r'"[^"\\]*(?:\\.[^"\\]*)*"'),
    ('CHAR_LIT',     r"'[^'\\]'|'\\.'"),
    ('FLOAT_NUM',    r'\b\d+\.\d*([eE][+-]?\d+)?\b|\b\d+[eE][+-]?\d+\b'),
    ('NUMBER',       r'\b\d+\b'),

    # We will match identifiers and check if they are keywords instead!

    ('IDENTIFIER',   r'\b[a-zA-Z_][a-zA-Z0-9_]*\b'),

    # Multi-char operators first
    ('INC',          r'\+\+'),
    ('DEC',          r'--'),
    ('PLUS_ASSIGN',  r'\+='),
    ('MINUS_ASSIGN', r'-='),
    ('TIMES_ASSIGN', r'\*='),
    ('DIV_ASSIGN',   r'/='),
    ('EQ',           r'=='),
    ('NEQ',          r'!='),
    ('LEQ',          r'<='),
    ('GEQ',          r'>='),
    ('SHL',          r'<<'),
    ('SHR',          r'>>'),
    ('AND',          r'&&'),
    ('OR',           r'\|\|'),
    ('NOT',          r'!'),
    ('LT',           r'<'),
    ('GT',           r'>'),
    ('ASSIGN',       r'='),
    ('PLUS',         r'\+'),
    ('MINUS',        r'-'),
    ('TIMES',        r'\*'),
    ('DIVIDE',       r'/'),
    ('MOD',          r'%'),

    # Punctuation
    ('SEMI',         r';'),
    ('COMMA',        r','),
    ('LBRACE',       r'\{'),
    ('RBRACE',       r'\}'),
    ('LPAREN',       r'\('),
    ('RPAREN',       r'\)'),
    ('LBRACKET',     r'\['),
    ('RBRACKET',     r'\]'),
    ('COLON',        r':'),
    ('SCOPE',        r'::'),

    ('LEXICAL_ERROR', r'.')
]

# ------------------------------------------------------------------
# Display-category mapping
# Maps every internal token type -> the category shown in Phase 1 output.
# The parser still uses the original internal types unchanged.
# ------------------------------------------------------------------
TOKEN_CATEGORIES = {
    # Preprocessor
    'PREPROCESSOR': 'PREPROCESSOR',

    # Keywords
    'USING':    'KEYWORD', 'NAMESPACE': 'KEYWORD', 'STD':    'IDENTIFIER',
    'VOID':     'KEYWORD', 'INT':       'KEYWORD', 'FLOAT':  'KEYWORD',
    'DOUBLE':   'KEYWORD', 'CHAR':      'KEYWORD', 'BOOL':   'KEYWORD',
    'CONST':    'KEYWORD', 'FOR':       'KEYWORD', 'WHILE':  'KEYWORD',
    'DO':       'KEYWORD', 'IF':        'KEYWORD', 'ELSE':   'KEYWORD',
    'BREAK':    'KEYWORD', 'CONTINUE':  'KEYWORD', 'RETURN': 'KEYWORD',
    'TRUE':     'KEYWORD', 'FALSE':     'KEYWORD',

    # Identifier
    'IDENTIFIER': 'IDENTIFIER',
    'MAIN':       'IDENTIFIER', 'CIN':      'IDENTIFIER', 
    'COUT':       'IDENTIFIER', 'ENDL':     'IDENTIFIER',

    # Operators  (arithmetic, relational, logical, assignment, stream)
    'PLUS':         'OPERATOR', 'MINUS':        'OPERATOR',
    'TIMES':        'OPERATOR', 'DIVIDE':       'OPERATOR',
    'MOD':          'OPERATOR', 'ASSIGN':       'OPERATOR',
    'EQ':           'OPERATOR', 'NEQ':          'OPERATOR',
    'LT':           'OPERATOR', 'GT':           'OPERATOR',
    'LEQ':          'OPERATOR', 'GEQ':          'OPERATOR',
    'AND':          'OPERATOR', 'OR':           'OPERATOR',
    'NOT':          'OPERATOR', 'INC':          'OPERATOR',
    'DEC':          'OPERATOR', 'PLUS_ASSIGN':  'OPERATOR',
    'MINUS_ASSIGN': 'OPERATOR', 'TIMES_ASSIGN': 'OPERATOR',
    'DIV_ASSIGN':   'OPERATOR', 'SHL':          'OPERATOR',
    'SHR':          'OPERATOR',

    # Literals
    'NUMBER':   'LITERAL', 'FLOAT_NUM': 'LITERAL',
    'STRING':   'LITERAL', 'CHAR_LIT':  'LITERAL',

    # Punctuation / Delimiters
    'SEMI':     'PUNCTUATION', 'COMMA':    'PUNCTUATION',
    'LBRACE':   'PUNCTUATION', 'RBRACE':   'PUNCTUATION',
    'LPAREN':   'PUNCTUATION', 'RPAREN':   'PUNCTUATION',
    'LBRACKET': 'PUNCTUATION', 'RBRACKET': 'PUNCTUATION',
    'COLON':    'PUNCTUATION', 'SCOPE':    'PUNCTUATION',

    # End-of-file
    'EOF': 'EOF',
}

def get_display_type(internal_kind):
    """Return the display category for a token type."""
    return TOKEN_CATEGORIES.get(internal_kind, internal_kind)


# Dictionary of reserved words to their token types
KEYWORDS = {
    'using': 'USING', 'namespace': 'NAMESPACE', 'std': 'STD',
    'void': 'VOID', 'int': 'INT', 'float': 'FLOAT', 'double': 'DOUBLE',
    'char': 'CHAR', 'bool': 'BOOL', 'true': 'TRUE', 'false': 'FALSE',
    'const': 'CONST', 'for': 'FOR', 'if': 'IF', 'else': 'ELSE',
    'while': 'WHILE', 'do': 'DO', 'break': 'BREAK', 'continue': 'CONTINUE',
    'return': 'RETURN', 'main': 'MAIN', 'cin': 'CIN', 'cout': 'COUT', 'endl': 'ENDL'
}

def lex(code):
    tokens = []
    combined_regex = '|'.join(f'(?P<{name}>{pattern})' for name, pattern in TOKEN_TYPES)

    for match in re.finditer(combined_regex, code):
        kind = match.lastgroup
        value = match.group()

        if kind in ('WHITESPACE', 'COMMENT'):
            continue

        if kind == 'LEXICAL_ERROR':
            line_num = code.count('\n', 0, match.start()) + 1
            col_num  = match.start() - code.rfind('\n', 0, match.start())
            raise LexicalError(
                f"LEXICAL ERROR at Line {line_num}, Column {col_num}: "
                f"Unrecognized character '{value}'"
            )

        # If it matched IDENTIFIER, check if it's actually a keyword!
        if kind == 'IDENTIFIER' and value in KEYWORDS:
            kind = KEYWORDS[value]

        line_num = code.count('\n', 0, match.start()) + 1
        tokens.append((kind, value, line_num))

    tokens.append(('EOF', '$', tokens[-1][2] if tokens else 1))
    return tokens


if __name__ == '__main__':
    input_file = 'test_program.cpp'
    if len(sys.argv) > 1:
        input_file = sys.argv[1]

    try:
        with open(input_file, 'r') as f:
            code = f.read()
    except FileNotFoundError:
        print(f"Error: {input_file} not found.")
        sys.exit(1)

    output_file = 'tokens_output.txt'
    try:
        tokens = lex(code)
    except LexicalError as e:
        with open(output_file, 'w') as out_f:
            out_f.write(str(e) + '\n')
        print(str(e))
        sys.exit(1)

    disp = tokens[:-1]
    with open(output_file, 'w') as out_f:
        for kind, value, line_num in disp:
            cat = get_display_type(kind)
            out_f.write(f'<{cat}, {value}, Line: {line_num}>\n')

    print('================== LEXICAL ANALYZER ==================')
    print(f'Successfully processed: {input_file}')
    print(f'Total tokens identified: {len(disp)}')
    print(f'Output saved to: {output_file}')
    print('======================================================')
    for kind, value, line_num in disp:
        cat = get_display_type(kind)
        print(f'<{cat}, {value}, Line: {line_num}>')
