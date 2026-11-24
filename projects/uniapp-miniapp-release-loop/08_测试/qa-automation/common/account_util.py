#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""账号兜底：与后端 PasswordHasher 同参数（PBKDF2-HmacSHA256 / 120000 / 32B / 标准 Base64）。

本项目无注册接口，账号来自 init.sql 种子；硬规则要求「不依赖人工准备口令」，
因此登录失败时由测试侧按同一哈希格式直接补种账号，再重试登录。
"""
import base64
import hashlib
import secrets


def hash_password(raw, salt=None):
    salt = salt or secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", raw.encode("utf-8"), salt, 120000, dklen=32)
    return (f"pbkdf2$120000${base64.b64encode(salt).decode()}"
            f"${base64.b64encode(dk).decode()}")


def ensure_account(mysql, account, password, nickname):
    """INSERT ... ON DUPLICATE KEY UPDATE：缺号补种、口令被改则纠正。"""
    mysql.execute(
        "INSERT INTO `user` (account,password_hash,nickname) VALUES "
        f"({MysqlQuote(account)},{MysqlQuote(hash_password(password))},{MysqlQuote(nickname)}) "
        "ON DUPLICATE KEY UPDATE password_hash=VALUES(password_hash), nickname=VALUES(nickname)")


def delete_account(mysql, account):
    user_id = mysql.scalar(f"SELECT id FROM `user` WHERE account={MysqlQuote(account)}")
    if not user_id:
        return
    mysql.execute(f"DELETE FROM notify_log WHERE booking_id IN "
                  f"(SELECT id FROM booking WHERE user_id={user_id})")
    mysql.execute(f"DELETE FROM booking WHERE user_id={user_id}")
    mysql.execute(f"DELETE FROM `user` WHERE id={user_id}")


def MysqlQuote(value):  # noqa: N802 - 与 Mysql.quote 同口径，避免循环导入
    return "'" + str(value).replace("'", "''") + "'"
