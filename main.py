import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3, random, os

DB_FILE = "recipes.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # recipes -> contains dishes, the days they belong to and if they're currently in rotation
    c.execute('''
        CREATE TABLE IF NOT EXISTS recipes (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            day TEXT NOT NULL,
            active INTEGER DEFAULT 1
        )
    ''')

    # ingredients -> database of ingredients
    c.execute('''
        CREATE TABLE IF NOT EXISTS ingredients (
            id INTEGER PRIMARY KEY,
            ingredient_name TEXT
        )
    ''')

    # ingredients_included -> connects recipes to the ingredients
    c.execute('''
        CREATE TABLE IF NOT EXISTS ingredients_included (
            id INTEGER PRIMARY KEY,
            recipe_id INTEGER,
            ingredient_id INTEGER,
            FOREIGN KEY(recipe_id) REFERENCES recipes(id),
            FOREIGN KEY(ingredient_id) REFERENCES ingredients(id)
        )
    ''')

    # upgrade schema if needed
    c.execute("PRAGMA table_info(recipes)")
    cols = [col[1] for col in c.fetchall()]
    if "active" not in cols:
        c.execute("ALTER TABLE recipes ADD COLUMN active INTEGER DEFAULT 1")

    conn.commit()
    conn.close()

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# colors
BG_COLOR = "#f6f5f3"
FG_COLOR = "#333333"
ACCENT = "#88b04b"
ACCENT_DARK = "#5f7a37"
DELETE_RED = "#b14b4b"


class MealPlannerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Weekly Meal Planner")
        self.geometry("680x600")
        self.configure(bg=BG_COLOR)

        self.week_plan = {}
        self.day_vars = {}
        self.editing_recipe_id = None  # track if editing an existing recipe

        self._build_ui()

    def _build_ui(self):
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self.frame_planner = tk.Frame(notebook, bg=BG_COLOR)
        self.frame_recipes = tk.Frame(notebook, bg=BG_COLOR)
        self.frame_shopping = tk.Frame(notebook, bg=BG_COLOR)

        notebook.add(self.frame_planner, text="Weekly Planner")
        notebook.add(self.frame_shopping, text="Shopping List")
        notebook.add(self.frame_recipes, text="Recipes")

        self._build_planner_tab()
        self._build_recipes_tab()
        self._build_shopping_tab()

    # First Tab: Weekly Planner
    def _build_planner_tab(self):
        lbl = tk.Label(self.frame_planner, text="Weekly Meal Plan", font=("Arial", 16, "bold"), bg=BG_COLOR,
                       fg=FG_COLOR)
        lbl.pack(pady=10)

        days_frame = tk.Frame(self.frame_planner, bg=BG_COLOR)
        days_frame.pack(pady=10)

        for day in DAYS:
            var = tk.BooleanVar(value=True)
            cb = tk.Checkbutton(days_frame, text=day, variable=var, bg=BG_COLOR, fg=FG_COLOR, selectcolor=BG_COLOR)
            cb.pack(anchor="w")
            self.day_vars[day] = var

        tk.Button(self.frame_planner, text="Generate Plan for Selected Days", bg=ACCENT, fg="white",
                  command=self.randomize_selected_days).pack(pady=10)

        self.plan_text = tk.Text(self.frame_planner, width=60, height=12, wrap="word", bg="white", fg=FG_COLOR)
        self.plan_text.pack(pady=10)

    def randomize_selected_days(self):
        self.plan_text.delete("1.0", "end")
        self.week_plan = {}

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()

        for day in DAYS:
            if self.day_vars[day].get():
                c.execute("SELECT id, name FROM recipes WHERE day=? AND active=1", (day,))
                recipes = c.fetchall()
                if recipes:
                    rid, name = random.choice(recipes)
                    self.week_plan[day] = (rid, name)
                else:
                    self.week_plan[day] = None
            else:
                self.week_plan[day] = None

        conn.close()
        self._update_plan_text()

    def _update_plan_text(self):
        self.plan_text.delete("1.0", "end")
        for day in DAYS:
            if day in self.week_plan and self.week_plan[day]:
                self.plan_text.insert("end", f"{day}: {self.week_plan[day][1]}\n")
            else:
                self.plan_text.insert("end", f"{day}: (No recipe assigned)\n")

    # Second Tab: Shopping List
    def _build_shopping_tab(self):
        self.shopping_text = tk.Text(self.frame_shopping, width=60, height=30, wrap="word", bg="white", fg=FG_COLOR)
        self.shopping_text.pack(pady=10, padx=10)
        tk.Button(self.frame_shopping, text="Update Shopping List", bg=ACCENT, fg="white",
                  command=self.update_shopping_list).pack(pady=5)

    def update_shopping_list(self):
        if not self.week_plan:
            self.shopping_text.delete("1.0", "end")
            self.shopping_text.insert("end", "No recipes assigned to the weekly plan.")
            return

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        ingredient_map = {}

        for day, recipe_data in self.week_plan.items():
            if recipe_data:
                rid, name = recipe_data
                c.execute("""
                    SELECT ingredient_name
                    FROM ingredients
                    JOIN ingredients_included ON ingredients.id = ingredients_included.ingredient_id
                    WHERE ingredients_included.recipe_id=?
                """, (rid,))
                for (ing,) in c.fetchall():
                    ingredient_map.setdefault(ing, set()).add(name)
        conn.close()

        self.shopping_text.delete("1.0", "end")
        self.shopping_text.insert("end", "Shopping List:\n\n")
        for ing in sorted(ingredient_map.keys()):
            recipes_str = ", ".join(sorted(ingredient_map[ing]))
            self.shopping_text.insert("end", f"- {ing} (Used in: {recipes_str})\n")

    # Third Tab: Recipe Book (connects to database, adds new recipes and edits old ones)
    def _build_recipes_tab(self):
        # form for adding and editing recipes
        form_frame = tk.Frame(self.frame_recipes, bg=BG_COLOR)
        form_frame.pack(fill="x", pady=5)

        tk.Label(form_frame, text="Recipe Name:", bg=BG_COLOR, fg=FG_COLOR).grid(row=0, column=0, sticky="w", padx=5)
        self.recipe_name_var = tk.StringVar()
        self.recipe_name_entry = tk.Entry(form_frame, textvariable=self.recipe_name_var, width=30)
        self.recipe_name_entry.grid(row=0, column=1, padx=5, pady=2)

        tk.Label(form_frame, text="Day:", bg=BG_COLOR, fg=FG_COLOR).grid(row=0, column=2, sticky="w", padx=5)
        self.recipe_day_var = tk.StringVar()
        self.recipe_day_combo = ttk.Combobox(form_frame, textvariable=self.recipe_day_var, values=DAYS, width=12)
        self.recipe_day_combo.grid(row=0, column=3, padx=5, pady=2)

        self.recipe_active_var = tk.BooleanVar(value=True)
        tk.Checkbutton(form_frame, text="Active", variable=self.recipe_active_var, bg=BG_COLOR).grid(row=0, column=4, padx=5)

        tk.Label(form_frame, text="Ingredients (comma separated):", bg=BG_COLOR, fg=FG_COLOR).grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.recipe_ingredients_var = tk.StringVar()
        self.recipe_ingredients_entry = tk.Entry(form_frame, textvariable=self.recipe_ingredients_var, width=60)
        self.recipe_ingredients_entry.grid(row=1, column=1, columnspan=3, padx=5, pady=2)

        tk.Button(form_frame, text="Save Recipe", bg=ACCENT, fg="white", command=self.save_recipe).grid(row=1, column=4, padx=5)

        # Filter
        filter_frame = tk.Frame(self.frame_recipes, bg=BG_COLOR)
        filter_frame.pack(fill="x", pady=5)

        tk.Label(filter_frame, text="Filter by Day:", bg=BG_COLOR, fg=FG_COLOR).pack(side="left", padx=5)
        self.filter_day_var = tk.StringVar(value="All")
        ttk.Combobox(filter_frame, textvariable=self.filter_day_var, values=["All"] + DAYS, width=12).pack(side="left", padx=5)
        tk.Button(filter_frame, text="Apply Filter", bg=ACCENT, fg="white", command=self.show_all_recipes).pack(side="left", padx=5)

        # Scrollable recipes list setup
        container = tk.Frame(self.frame_recipes, bg=BG_COLOR)
        container.pack(fill="both", expand=True, pady=5)

        canvas = tk.Canvas(container, bg=BG_COLOR, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        self.recipes_scroll = tk.Frame(canvas, bg=BG_COLOR)

        self.recipes_scroll.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )

        canvas.create_window((0, 0), window=self.recipes_scroll, anchor="nw")

        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def _on_mousewheel(event):
            if os.name == 'nt':  # Windows
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            else:  # MacOS or others
                canvas.yview_scroll(int(-1 * event.delta), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        self.show_all_recipes()

    def save_recipe(self):
        name = self.recipe_name_var.get().strip()
        day = self.recipe_day_var.get()
        active = 1 if self.recipe_active_var.get() else 0
        ingredients = [ing.strip() for ing in self.recipe_ingredients_var.get().split(",") if ing.strip()]

        if not name or day not in DAYS:
            messagebox.showerror("Error", "Please provide a valid recipe name and select a day.")
            return

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()

        if self.editing_recipe_id:
            c.execute("UPDATE recipes SET name=?, day=?, active=? WHERE id=?", (name, day, active, self.editing_recipe_id))
            rid = self.editing_recipe_id
            c.execute("DELETE FROM ingredients_included WHERE recipe_id=?", (rid,))
        else:
            c.execute("INSERT INTO recipes (name, day, active) VALUES (?, ?, ?)", (name, day, active))
            rid = c.lastrowid

        for ing in ingredients:
            c.execute("INSERT OR IGNORE INTO ingredients (ingredient_name) VALUES (?)", (ing,))
            c.execute("SELECT id FROM ingredients WHERE ingredient_name=?", (ing,))
            ing_id = c.fetchone()[0]
            c.execute("INSERT INTO ingredients_included (recipe_id, ingredient_id) VALUES (?, ?)", (rid, ing_id))

        conn.commit()
        conn.close()

        self.editing_recipe_id = None
        self.recipe_name_var.set("")
        self.recipe_day_var.set("")
        self.recipe_ingredients_var.set("")
        self.recipe_active_var.set(True)
        self.show_all_recipes()
        messagebox.showinfo("Success", "Recipe saved successfully!")

    def show_all_recipes(self):
        for widget in self.recipes_scroll.winfo_children():
            widget.destroy()

        selected_day = self.filter_day_var.get()
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        order_by_day = """
            CASE day
                WHEN 'Monday' THEN 1
                WHEN 'Tuesday' THEN 2
                WHEN 'Wednesday' THEN 3
                WHEN 'Thursday' THEN 4
                WHEN 'Friday' THEN 5
                WHEN 'Saturday' THEN 6
                WHEN 'Sunday' THEN 7
            END
        """
        if selected_day == "All":
            c.execute(f"SELECT id, name, day, active FROM recipes ORDER BY {order_by_day}, name")
        else:
            c.execute("SELECT id, name, day, active FROM recipes WHERE day=? ORDER BY name", (selected_day,))
        rows = c.fetchall()
        conn.close()

        for idx, (rid, name, day, active) in enumerate(rows):
            self._add_recipe_row(idx, rid, name, day, active)

    def _add_recipe_row(self, idx, rid, name, day, active):
        row = tk.Frame(self.recipes_scroll, bg="white", relief="solid", bd=1)
        row.pack(fill="x", pady=2, padx=2)

        tk.Label(row, text=name, font=("Arial", 12, "bold"), bg="white", fg=FG_COLOR, width=30, anchor="w").pack(side="left", padx=5)
        tk.Label(row, text=day, bg="white", fg="#555555", width=12).pack(side="left")

        var = tk.BooleanVar(value=bool(active))
        chk = tk.Checkbutton(row, variable=var, command=lambda: self._toggle_active_by_id(rid, var.get()), bg="white")
        chk.pack(side="left", padx=5)

        tk.Button(row, text="Edit", command=lambda: self._load_recipe_into_form(rid), bg=ACCENT, fg="white", width=8).pack(side="left", padx=5)
        tk.Button(row, text="Delete", command=lambda: self._delete_recipe_by_id(rid), bg=DELETE_RED, fg="white", width=8).pack(side="left", padx=5)

    def _toggle_active_by_id(self, rid, new_state):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("UPDATE recipes SET active=? WHERE id=?", (1 if new_state else 0, rid))
        conn.commit()
        conn.close()

    def _load_recipe_into_form(self, rid):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT name, day, active FROM recipes WHERE id=?", (rid,))
        row = c.fetchone()
        if not row:
            conn.close()
            messagebox.showerror("Error", f"Recipe with ID {rid} not found.")
            return
        name, day, active = row

        c.execute("""
            SELECT ingredient_name
            FROM ingredients
            JOIN ingredients_included ON ingredients.id = ingredients_included.ingredient_id
            WHERE ingredients_included.recipe_id=?
        """, (rid,))
        ingredients = ", ".join([r[0] for r in c.fetchall()])
        conn.close()

        self.recipe_name_var.set(name)
        self.recipe_day_var.set(day)
        self.recipe_active_var.set(bool(active))
        self.recipe_ingredients_var.set(ingredients)

        self.editing_recipe_id = rid
        self.recipe_name_entry.focus_set()

    def _delete_recipe_by_id(self, rid):
        if messagebox.askyesno("Delete", "Are you sure you want to delete this recipe?"):
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("DELETE FROM recipes WHERE id=?", (rid,))
            c.execute("DELETE FROM ingredients_included WHERE recipe_id=?", (rid,))
            conn.commit()
            self.show_all_recipes()
            conn.close()

if __name__ == "__main__":
    init_db()
    app = MealPlannerApp()
    app.mainloop()
