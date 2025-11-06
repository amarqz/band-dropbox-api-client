def remove_library_suffix(entry: str, suffix: str) -> str:
    """ Remove the instrument + extension suffix in the file name.
    
        Useful if files come with an instrument suffix:
        e.g.: "file_altsax.pdf"
    """
    
    return entry.replace(suffix, '')