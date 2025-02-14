import vscode
from pathlib import Path
from ctxclip import ProjectContextExtractor, CodeSelection


@vscode.command("contextExtractor.getContext")
def get_selection_context():
    # Get the active editor
    editor = vscode.window.active_text_editor
    if not editor:
        vscode.window.show_error_message("No active editor")
        return

    # Get the current selection
    selection = editor.selection
    if not selection:
        vscode.window.show_error_message("No text selected")
        return

    # Get the selected text
    document = editor.document
    selected_text = document.get_text(selection)

    try:
        # Create a CodeSelection object
        code_selection = CodeSelection(
            text=selected_text,
            file_path=Path(document.file_name),
            start_line=selection.start.line + 1,
            end_line=selection.end.line + 1,
        )

        # Get the workspace folder as project root
        workspace_folders = vscode.workspace.workspace_folders
        if not workspace_folders:
            vscode.window.show_error_message("No workspace folder open")
            return

        project_root = Path(workspace_folders[0].uri.fsPath)

        # Extract context
        extractor = ProjectContextExtractor(project_root)
        context = extractor.get_context(code_selection, depth=2)

        # Create new document with context
        new_doc = vscode.workspace.create_text_document(
            language="python", content=context
        )
        vscode.window.show_text_document(new_doc)

    except Exception as e:
        vscode.window.show_error_message(f"Error extracting context: {str(e)}")


@vscode.command("contextExtractor.setDepth")
async def set_depth():
    """Command to set the extraction depth"""
    result = await vscode.window.show_input_box(
        prompt="Enter context extraction depth (1-5)", value="2"
    )
    if result and result.isdigit():
        depth = int(result)
        vscode.workspace.configuration.update(
            "contextExtractor.depth", depth, vscode.ConfigurationTarget.GLOBAL
        )


# Extension activation event
@vscode.activate
def activate():
    vscode.window.show_information_message("Context Extractor activated!")
