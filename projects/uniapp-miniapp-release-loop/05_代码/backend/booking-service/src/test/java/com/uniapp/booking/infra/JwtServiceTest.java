package com.uniapp.booking.infra;

import com.uniapp.booking.config.BookingProperties;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ValueOperations;

import java.time.Duration;
import java.time.Instant;
import java.util.Date;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/** L1 单元测试：JWT 签发/解析/黑名单 TTL（D-24），Redis 用 Mockito 隔离。 */
class JwtServiceTest {

    private BookingProperties props;
    private StringRedisTemplate redis;
    private ValueOperations<String, String> valueOps;
    private JwtService service;

    @BeforeEach
    @SuppressWarnings("unchecked")
    void setUp() {
        props = new BookingProperties();
        props.getJwt().setSecret("unit-test-jwt-secret-at-least-32-bytes!!");
        props.getJwt().setTtlHours(2);
        redis = Mockito.mock(StringRedisTemplate.class);
        valueOps = Mockito.mock(ValueOperations.class);
        when(redis.opsForValue()).thenReturn(valueOps);
        service = new JwtService(props, redis);
        service.init();
    }

    @Test
    void issueThenParseCarriesSubjectAndJti() {
        String token = service.issue(7L);
        assertNotNull(token);
        assertEquals(3, token.split("\\.").length);
        Claims claims = service.parse(token);
        assertEquals("7", claims.getSubject());
        assertNotNull(claims.getId());
        assertTrue(claims.getExpiration().after(new Date()));
    }

    @Test
    void tamperedTokenRejected() {
        String token = service.issue(7L);
        String tampered = token.substring(0, token.length() - 2) + "xx";
        assertThrows(JwtException.class, () -> service.parse(tampered));
    }

    @Test
    void blacklistWritesKeyWithRemainingTtl() {
        Date expiration = Date.from(Instant.now().plusSeconds(3600));
        service.blacklist("jti-1", expiration);
        verify(valueOps).set(eq("ub:jwt:blacklist:jti-1"), eq("1"), any(Duration.class));
    }

    @Test
    void expiredOrNullBlacklistSkipsWrite() {
        service.blacklist("jti-2", Date.from(Instant.now().minusSeconds(10)));
        service.blacklist(null, Date.from(Instant.now().plusSeconds(10)));
        verify(valueOps, never()).set(eq("ub:jwt:blacklist:jti-2"), anyString(), any(Duration.class));
    }

    @Test
    void isBlacklistedReadsRedisFlag() {
        when(redis.hasKey("ub:jwt:blacklist:jti-3")).thenReturn(true);
        when(redis.hasKey("ub:jwt:blacklist:jti-4")).thenReturn(false);
        assertTrue(service.isBlacklisted("jti-3"));
        assertFalse(service.isBlacklisted("jti-4"));
        assertFalse(service.isBlacklisted(null));
    }
}
