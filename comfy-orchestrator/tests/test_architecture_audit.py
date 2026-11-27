"""Static integration boundaries for the entire package, without services."""
import ast
from pathlib import Path
import unittest

PACKAGE = Path(__file__).resolve().parents[1] / "comfy_orchestrator"


def eager_imports(tree, modules):
    """Only top-level unconditional imports, not intentionally deferred imports."""
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            if node.level == 1:
                if node.module:
                    yield node.module.split(".")[0]
                else:
                    yield from (alias.name for alias in node.names)
            elif node.module == "comfy_orchestrator":
                yield from (alias.name for alias in node.names)
            elif node.module and node.module.startswith("comfy_orchestrator."):
                yield node.module.split(".")[1]
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("comfy_orchestrator."):
                    yield alias.name.split(".")[1]


def import_graph():
    modules = {p.stem: ast.parse(p.read_text(encoding="utf-8"))
               for p in PACKAGE.glob("*.py")}
    return {name: set(eager_imports(tree, modules)) & modules.keys()
            for name, tree in modules.items()}


class ArchitectureAuditTests(unittest.TestCase):
    def test_no_eager_package_import_cycles(self):
        graph = import_graph()
        visited = set()
        def visit(name, stack):
            self.assertNotIn(name, stack, " -> ".join([*stack, name]))
            if name in visited:
                return
            for dependency in sorted(graph[name]):
                visit(dependency, [*stack, name])
            visited.add(name)
        for name in sorted(graph):
            visit(name, [])

    def test_no_backend_imports_tk_or_ui_modules(self):
        backends = ("core", "configuration", "workflow_registry", "http_api",
                    "comfy_client", "ollama_client", "lmstudio", "generation_runtime",
                    "generation_controller", "long_video", "long_video_plan",
                    "project_store", "project_draft", "prompt_inference", "prompt_edit",
                    "prompt_review", "history_refresh", "task_controller", "result_state", "single_prompt", "llm_usage",
                    "material_transfer")
        for name in backends:
            tree = ast.parse((PACKAGE / f"{name}.py").read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    imports = [node.module or "", *(alias.name for alias in node.names)]
                elif isinstance(node, ast.Import):
                    imports = [alias.name for alias in node.names]
                else:
                    continue
                for imported in imports:
                    base = imported.split(".")[-1]
                    self.assertFalse(base == "tkinter" or imported.startswith("tkinter.")
                                     or base == "gui" or base.endswith("_ui")
                                     or base.endswith("_view") or base == "output_views",
                                     (name, imported))

    def test_literal_worker_events_have_registered_handlers(self):
        gui_tree = ast.parse((PACKAGE / "gui.py").read_text(encoding="utf-8"))
        application = next(node for node in gui_tree.body
                           if isinstance(node, ast.ClassDef) and node.name == "Application")
        router = next(node for node in application.body
                      if isinstance(node, ast.FunctionDef) and node.name == "_build_event_router")
        route_dict = next(node for node in ast.walk(router) if isinstance(node, ast.Dict))
        keys = [key.value for key in route_dict.keys if isinstance(key, ast.Constant)]
        self.assertEqual(len(keys), len(set(keys)), "duplicate event registration")
        registered = set(keys)
        emitted = {"done", "idle", "long_project_done"}
        for filename in ("gui.py", "task_controller.py", "timing.py", "history_refresh.py"):
            tree = ast.parse((PACKAGE / filename).read_text(encoding="utf-8"))
            for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
                function = call.func
                name = function.attr if isinstance(function, ast.Attribute) else (
                    function.id if isinstance(function, ast.Name) else "")
                if name in ("put", "emit", "sink") and call.args:
                    event = call.args[0]
                    if (isinstance(event, ast.Tuple) and event.elts
                            and isinstance(event.elts[0], ast.Constant)
                            and isinstance(event.elts[0].value, str)):
                        emitted.add(event.elts[0].value)
                for kw in call.keywords:
                    if kw.arg == "done_event" and isinstance(kw.value, ast.Constant):
                        emitted.add(kw.value.value)
        self.assertFalse(emitted - registered, sorted(emitted - registered))


if __name__ == "__main__":
    unittest.main()
