from typing import Any, Optional

def success_response(message: str, data: Optional[Any] = None) -> dict:
    """
    Generate a success response dictionary.

    Parameters:
        - message (str): The success message to include in the response.
        - data (Optional[Any]): Optional additional data to include in the response. Can be of any type.

    Returns:
        - dict: A dictionary containing the success status, message, and optionally the data if provided.
    """
    if data is None:
        return {"success": True, "message": message}

    return {"success": True, "message": message, "data": data}
