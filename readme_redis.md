## Хранение в Redis

### 1. Кэш пользователя
**Ключ:** `auth:user:{user_id}`  
**Значение:**  
```json
{
  "user_id": "int", 
  "username": "str",
  "hashed_password": "str",
  "created_at": "str"
}
```
**TTL:** 30 минут (config.tokens.access_token_expire_minutes)

### 2. Блокировки входа
**Ключ:** `auth:login_block:{ip}:{username}`  
**Значение:** `1`  (метка)  
**Назначение:** Блокировка при превышении попыток входа.  
**TTL:** `LOGIN_BLOCK_TIME` (300 сек.)  

### 3. Счетчик попыток
**Ключ:** `auth:login_attempt:{ip}:{username}`  
**Значение:** `3` (количество попыток)  
**TTL:** `LOGIN_BLOCK_TIME` (300 сек.) 