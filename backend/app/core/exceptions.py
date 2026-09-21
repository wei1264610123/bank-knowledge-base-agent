"""
自定义异常类
"""
from fastapi import HTTPException, status


class AppException(HTTPException):
    """应用基础异常"""
    def __init__(self, status_code: int, detail: str):
        super().__init__(status_code=status_code, detail=detail)


class UserNotFoundException(AppException):
    """用户不存在"""
    def __init__(self, username: str = None):
        detail = f"用户不存在: {username}" if username else "用户不存在"
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class UserAlreadyExistsException(AppException):
    """用户已存在"""
    def __init__(self, username: str = None):
        detail = f"用户名已存在: {username}" if username else "用户已存在"
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class InvalidPasswordException(AppException):
    """密码错误"""
    def __init__(self):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail="密码错误")


class DocumentNotFoundException(AppException):
    """文档不存在"""
    def __init__(self, doc_id: str = None):
        detail = f"文档不存在: {doc_id}" if doc_id else "文档不存在"
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class FileUploadException(AppException):
    """文件上传失败"""
    def __init__(self, detail: str = "文件上传失败"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class SessionNotFoundException(AppException):
    """会话不存在"""
    def __init__(self, session_id: str = None):
        detail = f"会话不存在: {session_id}" if session_id else "会话不存在"
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
