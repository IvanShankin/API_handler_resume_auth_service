from passlib.context import CryptContext
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_hash_password(password: str) -> str:
    """Преобразует пароль в хеш
    :return: хэш пароля"""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Проверяет, совпадает ли пароль с хешем
    :param plain_password: простой пароль (qwerty)
    :param hashed_password: хэш пароля (gfdjkjvzvxccxa)
    :return: результат совпадения
    """
    return pwd_context.verify(plain_password, hashed_password)