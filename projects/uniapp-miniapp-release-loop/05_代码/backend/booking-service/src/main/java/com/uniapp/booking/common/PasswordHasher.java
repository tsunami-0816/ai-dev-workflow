package com.uniapp.booking.common;

import javax.crypto.SecretKeyFactory;
import javax.crypto.spec.PBEKeySpec;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Base64;

/**
 * 口令哈希（PBKDF2WithHmacSHA256）。格式：pbkdf2$<iter>$<saltB64>$<hashB64>。
 * 与 db/gen_hash.py 同参数，种子账号可直接复用。
 */
public final class PasswordHasher {

    private static final String ALGO = "PBKDF2WithHmacSHA256";
    private static final int DEFAULT_ITER = 120000;
    private static final int KEY_BITS = 256;

    private PasswordHasher() {
    }

    /**
     * 校验口令。
     *
     * @param raw    明文口令（入参）
     * @param stored 数据库中的哈希串（入参）
     * @return true=匹配；false=不匹配或哈希格式非法（出参）
     * @throws RuntimeException 仅当 JDK 不支持 PBKDF2（正常环境不会发生）
     */
    public static boolean matches(String raw, String stored) {
        if (raw == null || stored == null) {
            return false;
        }
        String[] parts = stored.split("\\$");
        if (parts.length != 4 || !"pbkdf2".equals(parts[0])) {
            return false;
        }
        try {
            int iter = Integer.parseInt(parts[1]);
            byte[] salt = Base64.getDecoder().decode(parts[2]);
            byte[] expected = Base64.getDecoder().decode(parts[3]);
            byte[] actual = pbkdf2(raw, salt, iter);
            return MessageDigest.isEqual(expected, actual);
        } catch (RuntimeException ex) {
            return false;
        }
    }

    /** 生成哈希（运维/测试造数用）。入参：明文 + 随机盐；出参：可入库的哈希串。 */
    public static String hash(String raw, byte[] salt) {
        byte[] dk = pbkdf2(raw, salt, DEFAULT_ITER);
        return "pbkdf2$" + DEFAULT_ITER + "$" + Base64.getEncoder().encodeToString(salt)
                + "$" + Base64.getEncoder().encodeToString(dk);
    }

    private static byte[] pbkdf2(String raw, byte[] salt, int iter) {
        try {
            PBEKeySpec spec = new PBEKeySpec(raw.toCharArray(), salt, iter, KEY_BITS);
            return SecretKeyFactory.getInstance(ALGO).generateSecret(spec).getEncoded();
        } catch (Exception ex) {
            throw new IllegalStateException("PBKDF2 不可用: " + ALGO, ex);
        }
    }
}
