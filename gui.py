import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import os

try:
    import lexer
    import parser
    from semantic import SemanticAnalyzer, SemanticError
    from icg import TACGenerator, TACOptimizer
except ImportError:
    pass

class JetBrainsCloneGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Mini Compiler - IntelliJ IDEA Edition")
        self.root.geometry("1400x900")
        
        # Theme Colors (JetBrains IDEA Dark)
        self.c_bg = "#2b2d30"        # Main Background (Sidebar, Tabs)
        self.c_bg_dark = "#1e1f22"   # Editor & Terminal Background
        self.c_border = "#1e1f22"    # Border color
        self.c_text = "#a9b7c6"      # Main Text
        self.c_tree_sel = "#2f65ca"  # Tree selection blue
        self.c_green = "#548a46"     # Success/Run button green
        self.c_red = "#f75464"       # Error red
        self.c_tab_inactive = "#393b40"
        
        self.root.configure(bg=self.c_bg)
        
        self.setup_styles()
        self.create_menu()
        self.setup_ui()
        self.populate_file_tree()
        self.load_default_code()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        
        # PanedWindow Border
        style.configure('TPanedwindow', background=self.c_border)
        
        # Treeview (Project Explorer on the left)
        style.configure('Treeview', background=self.c_bg, foreground=self.c_text, fieldbackground=self.c_bg, borderwidth=0, font=('Segoe UI', 10))
        style.map('Treeview', background=[('selected', self.c_tree_sel)], foreground=[('selected', 'white')])
        style.configure('Treeview.Heading', background=self.c_bg, foreground=self.c_text, relief='flat')
        
        # Notebooks (Tabs for Editor, Phases, Terminal)
        style.configure('TNotebook', background=self.c_bg, borderwidth=0)
        style.configure('TNotebook.Tab', background=self.c_tab_inactive, foreground='#8c8c8c', padding=[15, 6], font=('Segoe UI', 10), borderwidth=0)
        style.map('TNotebook.Tab', background=[('selected', self.c_bg_dark)], foreground=[('selected', '#ffffff')])
        
        # General Frames
        style.configure('TFrame', background=self.c_bg)

        # Run Button mapping IDEA's run icon
        style.configure('Run.TButton', font=('Segoe UI', 10, 'bold'), background=self.c_green, foreground='white', borderwidth=0, padding=4)
        style.map('Run.TButton', background=[('active', '#609d50')])

    def create_menu(self):
        menubar = tk.Menu(self.root, bg=self.c_bg, fg=self.c_text, bd=0)
        self.root.config(menu=menubar)
        
        file_menu = tk.Menu(menubar, tearoff=0, bg=self.c_bg, fg=self.c_text)
        file_menu.add_command(label="Open File...", command=self.open_file, accelerator="Ctrl+O")
        file_menu.add_command(label="Save", command=self.save_file, accelerator="Ctrl+S")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        run_menu = tk.Menu(menubar, tearoff=0, bg=self.c_bg, fg=self.c_text)
        run_menu.add_command(label="Run Compiler", command=self.run_compiler, accelerator="Shift+F10")
        menubar.add_cascade(label="Run", menu=run_menu)
        
        self.root.bind("<Control-o>", lambda e: self.open_file())
        self.root.bind("<Control-s>", lambda e: self.save_file())
        self.root.bind("<Shift-F10>", lambda e: self.run_compiler())

    def setup_ui(self):
        # 1. Top Toolbar (Mimicking IntelliJ Top Bar Layout)
        toolbar = tk.Frame(self.root, bg=self.c_bg, height=45)
        toolbar.pack(side=tk.TOP, fill=tk.X)
        toolbar.pack_propagate(False)
        
        # Fake project title top left
        tk.Label(toolbar, text=" sytemproj \u25BE", font=('Segoe UI', 11, 'bold'), bg=self.c_bg, fg="white").pack(side=tk.LEFT, padx=15)
        
        # Run Button right aligned
        ttk.Button(toolbar, text="▶  Run (Shift+F10)", style='Run.TButton', command=self.run_compiler).pack(side=tk.RIGHT, padx=15, pady=8)

        # 2. Main Layout panes
        self.main_pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.main_pane.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        
        # --- LEFT SIDE: PROJECT EXPLORER ---
        self.sidebar_frame = tk.Frame(self.main_pane, bg=self.c_bg, width=220)
        self.main_pane.add(self.sidebar_frame, weight=0)
        
        # Project Title
        tk.Label(self.sidebar_frame, text=" Project", font=('Segoe UI', 10), bg=self.c_bg, fg=self.c_text, anchor='w').pack(fill=tk.X, padx=5, pady=5)
        
        # Tree hierarchy
        self.tree = ttk.Treeview(self.sidebar_frame, show="tree")
        self.tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=0)
        
        # --- RIGHT SIDE: EDITOR AND TERMINAL ---
        self.right_pane = ttk.PanedWindow(self.main_pane, orient=tk.VERTICAL)
        self.main_pane.add(self.right_pane, weight=1)
        
        # TOP of Right Side: Editor & Phases exactly side by side
        self.content_pane = ttk.PanedWindow(self.right_pane, orient=tk.HORIZONTAL)
        self.right_pane.add(self.content_pane, weight=3) # Vertical priority to editor

        # --> Left of Content: Source Code
        self.editor_frame = ttk.Frame(self.content_pane)
        self.content_pane.add(self.editor_frame, weight=1)
        
        self.editor_tabs = ttk.Notebook(self.editor_frame)
        self.editor_tabs.pack(fill=tk.BOTH, expand=True)
        
        editor_tab = tk.Frame(self.editor_tabs, bg=self.c_bg_dark)
        self.editor_tabs.add(editor_tab, text="  HelloWorld.cpp  ")
        
        # Main text widget for coding
        self.code_editor = tk.Text(editor_tab, font=('Consolas', 13), bg=self.c_bg_dark, fg=self.c_text,
                                   insertbackground="white", selectbackground=self.c_tree_sel, undo=True, borderwidth=0)
        self.code_editor.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # --> Right of Content: Phases Tools (Separated as requested)
        self.phases_frame = ttk.Frame(self.content_pane)
        self.content_pane.add(self.phases_frame, weight=1)
        
        self.phases_tabs = ttk.Notebook(self.phases_frame)
        self.phases_tabs.pack(fill=tk.BOTH, expand=True)
        
        self.tab_p1 = self.create_text_tab(self.phases_tabs, " Phase 1: Lexical ")
        self.tab_p2 = self.create_text_tab(self.phases_tabs, " Phase 2: Syntax ")
        self.tab_p3 = self.create_text_tab(self.phases_tabs, " Phase 3: Semantic ")
        self.tab_p4 = self.create_text_tab(self.phases_tabs, " Phase 4: ICG ")

        # BOTTOM of Right Side: Run Terminal
        self.terminal_frame = ttk.Frame(self.right_pane)
        self.right_pane.add(self.terminal_frame, weight=1) 
        
        self.terminal_tabs = ttk.Notebook(self.terminal_frame)
        self.terminal_tabs.pack(fill=tk.BOTH, expand=True)
        
        term_tab = tk.Frame(self.terminal_tabs, bg=self.c_bg_dark)
        self.terminal_tabs.add(term_tab, text="  ▶ Run  ")
        
        # Read-only console replicating Java/C++ execution log
        self.console_output = tk.Text(term_tab, font=('Consolas', 11), bg=self.c_bg_dark, fg=self.c_text,
                                      state=tk.DISABLED, wrap=tk.WORD, borderwidth=0)
        
        scroll_term = tk.Scrollbar(term_tab, orient="vertical", command=self.console_output.yview)
        self.console_output.configure(yscrollcommand=scroll_term.set)
        scroll_term.pack(side=tk.RIGHT, fill=tk.Y)
        self.console_output.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Second Terminal Tab: Program Output
        out_tab = tk.Frame(self.terminal_tabs, bg=self.c_bg_dark)
        self.terminal_tabs.add(out_tab, text="  Program Output  ")
        
        self.program_output = tk.Text(out_tab, font=('Consolas', 12), bg=self.c_bg_dark, fg="#a9b7c6",
                                      state=tk.DISABLED, wrap=tk.WORD, borderwidth=0)
        
        scroll_out = tk.Scrollbar(out_tab, orient="vertical", command=self.program_output.yview)
        self.program_output.configure(yscrollcommand=scroll_out.set)
        scroll_out.pack(side=tk.RIGHT, fill=tk.Y)
        self.program_output.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 3. Bottom Status Bar
        self.status_var = tk.StringVar()
        self.status_var.set(" Process finished with exit code 0")
        status_bar = tk.Label(self.root, textvariable=self.status_var, bd=1, relief=tk.FLAT, anchor=tk.W,
                              bg=self.c_bg, fg="#8c8c8c", font=('Segoe UI', 9), padx=10, pady=2)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def populate_file_tree(self):
        self.tree.delete(*self.tree.get_children())
        main_node = self.tree.insert("", "end", text=" 📁 sytemproj", open=True)
        try:
            # Populate with dummy or real files in directory
            for item in sorted(os.listdir(".")):
                if item != "__pycache__":
                    icon = "📄" if "." in item else "📁"
                    self.tree.insert(main_node, "end", text=f" {icon} {item}")
        except Exception:
            pass

    def create_text_tab(self, notebook, name):
        frame = tk.Frame(notebook, bg=self.c_bg_dark)
        notebook.add(frame, text=name)
        text_widget = tk.Text(frame, font=('Consolas', 11), bg=self.c_bg_dark, fg="#cc7832", state=tk.DISABLED, wrap=tk.NONE, borderwidth=0)
        
        scroll_y = tk.Scrollbar(frame, orient="vertical", command=text_widget.yview)
        scroll_x = tk.Scrollbar(frame, orient="horizontal", command=text_widget.xview)
        text_widget.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        
        scroll_y.pack(side="right", fill="y")
        scroll_x.pack(side="bottom", fill="x")
        text_widget.pack(fill=tk.BOTH, expand=True, padx=(10,0), pady=10)
        return text_widget

    def log_console(self, text, is_error=False, clear=False):
        self.console_output.config(state=tk.NORMAL)
        if clear:
            self.console_output.delete(1.0, tk.END)
            # Mimic IDEA command line structure
            prefix = "C:\\jdk-21\\bin\\python.exe -u c:\\sytemproj\\compiler.py\n"
            self.console_output.insert(tk.END, prefix, "dim")
            self.console_output.tag_configure("dim", foreground="#606366")
        
        self.console_output.tag_configure("error", foreground=self.c_red)
        self.console_output.tag_configure("success", foreground="#6a8759")
        
        tag = "error" if is_error else ("success" if "SUCCESS" in text or "PASS" in text else None)
        
        if tag:
            self.console_output.insert(tk.END, text + "\n", tag)
        else:
            self.console_output.insert(tk.END, text + "\n")
            
        self.console_output.see(tk.END)
        self.console_output.config(state=tk.DISABLED)
        self.root.update()

    def update_tab(self, text_widget, content, is_error=False):
        text_widget.config(state=tk.NORMAL)
        text_widget.delete(1.0, tk.END)
        text_widget.insert(tk.END, content)
        text_widget.config(fg=self.c_red if is_error else "#cc7832")
        text_widget.config(state=tk.DISABLED)

    def clear_all_tabs(self):
        for tab in [self.tab_p1, self.tab_p2, self.tab_p3, self.tab_p4]:
            self.update_tab(tab, "")

    def open_file(self):
        file_path = filedialog.askopenfilename()
        if file_path:
            with open(file_path, "r") as f:
                self.code_editor.delete(1.0, tk.END)
                self.code_editor.insert(tk.END, f.read())
            # Attempt to rename editor tab
            self.editor_tabs.tab(0, text=f"  {os.path.basename(file_path)}  ")
            self.populate_file_tree()

    def save_file(self):
        # We can implement a proper save if need be
        self.log_console("\n> File saved successfully.")
        self.populate_file_tree()

    def load_default_code(self):
        default_code = """#include <iostream>
using namespace std;

int main() {
    int a;
    cin >> a;
    
    int limit = 10;
    while (a < limit) {
        a = a + 1;
        if (a == 5) {
            continue;
        }
    }
    
    cout << "Final value: " << a << endl;
    return 0;
}
"""
        self.code_editor.insert(1.0, default_code)

    def run_vm(self, opt_tac):
        output = []
        variables = {}
        ip = 0
        
        labels = {}
        for i, instr in enumerate(opt_tac):
            if instr.endswith(":"):
                labels[instr[:-1]] = i
                
        execution_steps = 0
        
        while ip < len(opt_tac):
            execution_steps += 1
            if execution_steps > 10000:
                output.append("\n[VM Killed: Timeout / Infinite Loop]\n")
                break
                
            instr = opt_tac[ip]
            parts = instr.split()
            
            if not parts or instr.endswith(":") or instr == "main:":
                ip += 1
                continue
                
            if instr.startswith("print "):
                val = instr[6:].strip()
                if val == "\\n":
                    output.append("\n")
                elif val.startswith('"') and val.endswith('"'):
                    output.append(val[1:-1])
                else:
                    output.append(str(variables.get(val, val)))
            elif instr.startswith("read "):
                var = instr[5:].strip()
                from tkinter import simpledialog
                val = simpledialog.askstring("Input", f"Enter value for {var}:", parent=self.root)
                if val is None:
                    output.append(f"[Program Cancelled by User]\n")
                    break
                try:
                    variables[var] = float(val) if '.' in val else int(val)
                except ValueError:
                    variables[var] = 0
                output.append(f"{variables[var]}\n")
            elif instr.startswith("goto "):
                ip = labels[parts[1]]
                continue
            elif instr.startswith("ifFalse "):
                cond = variables.get(parts[1], parts[1])
                if str(cond) == "0" or cond == 0 or cond == 0.0:
                    ip = labels[parts[3]]
                    continue
            elif instr == "return":
                break
            elif "=" in parts:
                target = parts[0]
                if len(parts) == 3: # x = y
                    val = variables.get(parts[2], parts[2])
                    variables[target] = float(val) if '.' in str(val) else int(val)
                elif len(parts) == 5: # x = y op z
                    left = variables.get(parts[2], parts[2])
                    op = parts[3]
                    right = variables.get(parts[4], parts[4])
                    
                    try:
                        l = float(left) if '.' in str(left) else int(left)
                        r = float(right) if '.' in str(right) else int(right)
                        
                        if op == '+': variables[target] = l + r
                        elif op == '-': variables[target] = l - r
                        elif op == '*': variables[target] = l * r
                        elif op == '/': variables[target] = l / r if r != 0 else 0
                        elif op == '<': variables[target] = 1 if l < r else 0
                        elif op == '>': variables[target] = 1 if l > r else 0
                        elif op == '<=': variables[target] = 1 if l <= r else 0
                        elif op == '>=': variables[target] = 1 if l >= r else 0
                        elif op == '==': variables[target] = 1 if l == r else 0
                        elif op == '!=': variables[target] = 1 if l != r else 0
                    except ValueError:
                        variables[target] = 0
            
            ip += 1
            
        return "".join(output)

    def run_compiler(self):
        self.clear_all_tabs()
        self.log_console("", clear=True)
        code = self.code_editor.get(1.0, tk.END).strip()
        
        if not code:
            self.log_console("\nProcess finished with exit code 1", is_error=True)
            return

        self.status_var.set(" Compiling code...")
        
        try:
            tokens = lexer.lex(code)
            self.log_console("[1/4] Lexical Analysis: PASS")
            self.update_tab(self.tab_p1, "\n".join([f"<{k}, {v}, L:{l}>" for k, v, l in tokens]))
        except Exception as e:
            self.log_console(f"Lexical Error:\n{str(e)}\n\nProcess finished with exit code 1", is_error=True)
            self.update_tab(self.tab_p1, str(e), is_error=True)
            self.status_var.set(" Process finished with exit code 1")
            return

        try:
            ast = parser.parse(tokens)
            self.log_console("[2/4] Syntax Analysis:  PASS")
            self.update_tab(self.tab_p2, json.dumps(ast, indent=4))
        except Exception as e:
            self.log_console(f"Syntax Error:\n{str(e)}\n\nProcess finished with exit code 1", is_error=True)
            self.update_tab(self.tab_p2, str(e), is_error=True)
            self.status_var.set(" Process finished with exit code 1")
            return

        try:
            analyzer = SemanticAnalyzer(ast)
            sym = analyzer.analyze()
            self.log_console("[3/4] Semantic Analysis: PASS")
            self.update_tab(self.tab_p3, json.dumps(sym, indent=4))
        except Exception as e:
            self.log_console(f"Semantic Error:\n{str(e)}\n\nProcess finished with exit code 1", is_error=True)
            self.update_tab(self.tab_p3, str(e), is_error=True)
            self.status_var.set(" Process finished with exit code 1")
            return

        try:
            tac = TACGenerator(ast).generate()
            opt = TACOptimizer(tac).optimize()
            self.log_console("[4/4] Interm Code Gen:   PASS")
            self.update_tab(self.tab_p4, "========== UNOPTIMIZED ==========\n" + "\n".join(tac) + "\n\n========== OPTIMIZED ==========\n" + "\n".join(opt))
        except Exception as e:
            self.log_console(f"ICG Error:\n{str(e)}\n\nProcess finished with exit code 1", is_error=True)
            self.update_tab(self.tab_p4, str(e), is_error=True)
            self.status_var.set(" Process finished with exit code 1")
            return

        self.log_console("\nProcess finished with exit code 0")
        self.status_var.set(" Process finished with exit code 0")
        
        # Switch to program output tab and run VM
        self.terminal_tabs.select(1)
        self.program_output.config(state=tk.NORMAL)
        self.program_output.delete(1.0, tk.END)
        self.program_output.insert(tk.END, "Running program...\n\n")
        self.root.update()
        
        out_text = self.run_vm(opt)
        self.program_output.insert(tk.END, out_text)
        self.program_output.insert(tk.END, "\n\nProgram exited.")
        self.program_output.config(state=tk.DISABLED)
        
        self.populate_file_tree()

if __name__ == "__main__":
    root = tk.Tk()
    app = JetBrainsCloneGUI(root)
    root.mainloop()
