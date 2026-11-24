package com.uniapp.booking.common;

import org.junit.jupiter.api.Test;

import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** L1 单元测试：口令哈希（PBKDF2）正反向与边界（T-205 / D-08）。 */
class PasswordHasherTest {

    /** init.sql 种子：demo / welcome1，同一盐。 */
    private static final String SEED_HASH =
            "pbkdf2$120000$dW5pYXBwZGVtbzIwMjYhIQ==$QC0Fbhfw0NbrONnFmeLjXwxfmqZKFFAUMW1IBG0Y3s4=";

    @Test
    void seedHashMatchesWelcome1() {
        assertTrue(PasswordHasher.matches("welcome1", SEED_HASH));
    }

    @Test
    void wrongPasswordRejected() {
        assertFalse(PasswordHasher.matches("welcome2", SEED_HASH));
    }

    @Test
    void malformedHashRejectedWithoutThrow() {
        assertFalse(PasswordHasher.matches("welcome1", "not-a-pbkdf2-hash"));
        assertFalse(PasswordHasher.matches("welcome1", "pbkdf2$abc$!!$??"));
    }

    @Test
    void nullInputsRejected() {
        assertFalse(PasswordHasher.matches(null, SEED_HASH));
        assertFalse(PasswordHasher.matches("welcome1", null));
    }

    @Test
    void hashRoundTripWithRandomSalt() {
        byte[] salt = new byte[16];
        new SecureRandom().nextBytes(salt);
        String stored = PasswordHasher.hash("welcome1", salt);
        assertTrue(stored.startsWith("pbkdf2$120000$"));
        assertTrue(PasswordHasher.matches("welcome1", stored));
        assertFalse(PasswordHasher.matches("wrong", stored));
        // 同口令 + 异盐 → 不同哈希，证明盐生效
        byte[] salt2 = "another-salt-16b".getBytes(StandardCharsets.UTF_8);
        assertNotEquals(stored, PasswordHasher.hash("welcome1", salt2));
    }
}
