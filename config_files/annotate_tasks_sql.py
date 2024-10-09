import json
import tkinter as tk
from tkinter import messagebox
import argparse

def load_config():
    try:
        with open('config_files/test_annotated.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        messagebox.showerror("Error", "config_files/test_annotated.json not found")
        return []

def save_config(config):
    with open('config_files/test_annotated.json', 'w') as f:
        json.dump(config, f, indent=2)

class AnnotationApp:
    def __init__(self, config, review_mode=False, genre_filter=None, evaluatable_filter=None):
        self.root = tk.Tk()
        self.root.title("Annotate Task Intents")
        self.config = config
        self.review_mode = review_mode
        self.genre_filter = genre_filter
        self.evaluatable_filter = evaluatable_filter
        self.current_index = 0

        self.setup_ui()

    def setup_ui(self):
        self.progress_label = tk.Label(self.root, text="")
        self.progress_label.pack(pady=5)

        self.intent_label = tk.Label(self.root, text="", wraplength=400)
        self.intent_label.pack(pady=5)

        self.url_label = tk.Label(self.root, text="", wraplength=400)
        self.url_label.pack(pady=5)

        self.eval_types_label = tk.Label(self.root, text="", wraplength=400)
        self.eval_types_label.pack(pady=5)

        self.reference_answers_label = tk.Label(self.root, text="", wraplength=400)
        self.reference_answers_label.pack(pady=5)

        self.current_annotation_label = tk.Label(self.root, text="", wraplength=400)
        self.current_annotation_label.pack(pady=5)

        self.genre_frame = tk.Frame(self.root)
        tk.Button(self.genre_frame, text="Modification", command=lambda: self.mark_task_genre("Modification")).pack(side=tk.LEFT, padx=5)
        tk.Button(self.genre_frame, text="Information", command=lambda: self.mark_task_genre("Information")).pack(side=tk.LEFT, padx=5)
        tk.Button(self.genre_frame, text="Navigation", command=lambda: self.mark_task_genre("Navigation")).pack(side=tk.LEFT, padx=5)

        self.sql_frame = tk.Frame(self.root)
        tk.Button(self.sql_frame, text="SQL Evaluatable", command=lambda: self.mark_sql_evaluatable(True)).pack(side=tk.LEFT, padx=10)
        tk.Button(self.sql_frame, text="Not SQL Evaluatable", command=lambda: self.mark_sql_evaluatable(False)).pack(side=tk.RIGHT, padx=10)

        self.skip_button = tk.Button(self.root, text="Skip", command=self.skip_intent)
        self.skip_button.pack(pady=10)

    def mark_task_genre(self, genre):
        self.config[self.current_index]['task_genre'] = genre
        if genre == "Navigation":
            self.config[self.current_index]['sql_evaluatable'] = False
            self.next_intent()
        else:
            self.sql_frame.pack()

    def mark_sql_evaluatable(self, is_evaluatable):
        self.config[self.current_index]['sql_evaluatable'] = is_evaluatable
        self.next_intent()

    def skip_intent(self):
        self.next_intent()

    def next_intent(self):
        save_config(self.config)
        self.current_index += 1
        while self.current_index < len(self.config):
            if self.matches_filters(self.config[self.current_index]):
                self.show_task_details()
                return
            self.current_index += 1
        messagebox.showinfo("Completed", "All matching intents have been reviewed")
        self.root.quit()

    def matches_filters(self, task):
        if not self.review_mode and ('task_genre' in task or 'sql_evaluatable' in task):
            return False
        if self.genre_filter and task.get('task_genre') != self.genre_filter:
            return False
        if self.evaluatable_filter is not None:
            task_evaluatable = task.get('sql_evaluatable', None)
            if task_evaluatable != self.evaluatable_filter:
                return False
        return True

    def show_task_details(self):
        task = self.config[self.current_index]
        self.progress_label.config(text=f"Progress: {self.current_index + 1}/{len(self.config)}")
        self.intent_label.config(text=f"Intent: {task['intent']}")
        self.url_label.config(text=f"URL: {task.get('start_url', 'N/A')}")
        self.eval_types_label.config(text=f"Eval Types: {', '.join(task['eval'].get('eval_types', []))}")
        
        reference_answers = task['eval'].get('reference_answers', {})
        if isinstance(reference_answers, dict):
            ref_answers_text = ', '.join(f"{k}: {v}" for k, v in reference_answers.items())
        else:
            ref_answers_text = str(reference_answers)
        self.reference_answers_label.config(text=f"Reference Answers: {ref_answers_text}")

        if self.review_mode and 'task_genre' in task and 'sql_evaluatable' in task:
            current_annotation = f"Current annotation: Genre: {task['task_genre']}, SQL Evaluatable: {task['sql_evaluatable']}"
            self.current_annotation_label.config(text=current_annotation)
        else:
            self.current_annotation_label.config(text="")

        self.genre_frame.pack()
        if task.get('task_genre') != "Navigation":
            self.sql_frame.pack()
        else:
            self.sql_frame.pack_forget()

    def run(self):
        if self.current_index < len(self.config):
            self.show_task_details()
            self.root.mainloop()
        else:
            messagebox.showinfo("Completed", "No tasks match the specified criteria")

def annotate_intent(config, review_mode=False, genre_filter=None, evaluatable_filter=None):
    app = AnnotationApp(config, review_mode, genre_filter, evaluatable_filter)
    app.run()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Annotate task intents")
    parser.add_argument("--review", action="store_true", help="Review all tasks")
    parser.add_argument("--genre", choices=["navigation", "modification", "information"], help="Filter tasks by genre")
    parser.add_argument("--evaluatable", choices=["true", "false"], help="Filter tasks by SQL evaluability")
    args = parser.parse_args()

    config = load_config()
    if config:
        genre_filter = args.genre.capitalize() if args.genre else None
        evaluatable_filter = None
        if args.evaluatable:
            evaluatable_filter = args.evaluatable.lower() == "true"
        
        annotate_intent(config, review_mode=args.review, genre_filter=genre_filter, evaluatable_filter=evaluatable_filter)
