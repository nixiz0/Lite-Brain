def get_loader(file_ext, file_path, SUPPORTED_FILE_TYPES):
    """
    Return the loader instance for the given file extension.

    Args:
        file_ext (str): File extension (e.g. 'pdf', 'json').
        file_path (str): Path to the file.
        SUPPORTED_FILE_TYPES (dict): Mapping extension -> loader class.

    Returns:
        Loader instance or None if extension is not supported.
    """
    loader_cls = SUPPORTED_FILE_TYPES.get(file_ext)
    if not loader_cls:
        # Unsupported file type
        return None
    if file_ext == "json":
        # For JSON, pass jq_schema argument
        return loader_cls(file_path, jq_schema=".text")
    
    # For other types, just pass file_path
    return loader_cls(file_path)
