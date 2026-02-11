import os
import json
 
read_file_definition = {
    "name": "read_file",
    "description": "Reads a file and returns its contents.",
    "parameters": {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the file to read.",
            }
        },
        "required": ["file_path"],
    },
}
 
list_dir_definition = {
    "name": "list_dir",
    "description": "Lists the contents of a directory.",
    "parameters": {
        "type": "object",
        "properties": {
            "directory_path": {
                "type": "string",
                "description": "Path to the directory to list.",
            }
        },
        "required": ["directory_path"],
    },
}
 
write_file_definition = {
    "name": "write_file",
    "description": "Writes a file with the given contents.",
    "parameters": {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the file to write.",
            },
            "contents": {
                "type": "string",
                "description": "Contents to write to the file.",
            },
        },
        "required": ["file_path", "contents"],
    },
}
 
def read_file(file_path: str) -> dict:
    with open(file_path, "r") as f:
        return f.read()
 
def write_file(file_path: str, contents: str) -> bool:
    """Writes a file with the given contents."""
    with open(file_path, "w") as f:
        f.write(contents)
    return True
 
def list_dir(directory_path: str) -> list[str]:
    """Lists the contents of a directory."""
    full_path = os.path.expanduser(directory_path)
    return os.listdir(full_path)
 
file_tools = {
    "read_file": {"definition": read_file_definition, "function": read_file},
    "write_file": {"definition": write_file_definition, "function": write_file},
    "list_dir": {"definition": list_dir_definition, "function": list_dir},
}