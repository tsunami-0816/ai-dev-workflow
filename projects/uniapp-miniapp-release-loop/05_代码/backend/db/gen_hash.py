# -*- coding: utf-8 -*-
"""生成种子账号 PBKDF2 口令哈希（与 PasswordHasher.java 同参数：SHA256 / 120000 / 32B）。
用法：python gen_hash.py welcome1
"""
import base64
import hashlib
import sys

SALT = b"uniappdemo2026!!"
ITER = 120000


def hash_pwd(pwd: str, salt: bytes = SALT) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", pwd.encode(), salt, ITER, dklen=32)
    return "pbkdf2${}${}${}".format(ITER, base64.b64encode(salt).decode(), base64.b64encode(dk).decode())


if __name__ == "__main__":
    for p in (sys.argv[1:] or ["welcome1", "admin123"]):
        print(p, "=", hash_pwd(p))
