package com.uniapp.booking.infra;

import com.uniapp.booking.config.BookingProperties;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import jakarta.annotation.PostConstruct;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.util.Date;
import java.util.UUID;

/**
 * JWT 签发/解析/黑名单（D-24 / R-08）。
 * HS256 + jti；登出写 ub:jwt:blacklist:{jti}，TTL = 剩余有效期。
 */
@Component
public class JwtService {

    private static final String BLACKLIST_PREFIX = "ub:jwt:blacklist:";

    private final BookingProperties props;
    private final StringRedisTemplate redis;
    private SecretKey key;

    public JwtService(BookingProperties props, StringRedisTemplate redis) {
        this.props = props;
        this.redis = redis;
    }

    @PostConstruct
    void init() {
        String secret = props.getJwt().getSecret();
        if (secret == null || secret.getBytes(StandardCharsets.UTF_8).length < 32) {
            throw new IllegalStateException("JWT_SECRET 长度不足 32 字节，拒绝启动");
        }
        this.key = Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8));
    }

    /**
     * 签发令牌。
     *
     * @param userId 用户主键（入参）
     * @return token 串（出参），有效期 booking.jwt.ttl-hours
     */
    public String issue(long userId) {
        Instant now = Instant.now();
        Duration ttl = Duration.ofHours(props.getJwt().getTtlHours());
        return Jwts.builder()
                .id(UUID.randomUUID().toString())
                .subject(String.valueOf(userId))
                .issuedAt(Date.from(now))
                .expiration(Date.from(now.plus(ttl)))
                .signWith(key)
                .compact();
    }

    /**
     * 解析令牌。
     *
     * @param token JWT（入参）
     * @return Claims（出参）
     * @throws JwtException 签名非法/结构错误；ExpiredJwtException 表示过期
     */
    public Claims parse(String token) {
        return Jwts.parser().verifyWith(key).build().parseSignedClaims(token).getPayload();
    }

    /** 是否已登出（入参 jti；出参 true=已拉黑）。 */
    public boolean isBlacklisted(String jti) {
        if (jti == null) {
            return false;
        }
        Boolean exists = redis.hasKey(BLACKLIST_PREFIX + jti);
        return Boolean.TRUE.equals(exists);
    }

    /**
     * 登出拉黑（入参 jti + 过期时刻）。
     * TTL 取剩余秒数，≤0 不写（已过期无需拉黑）。
     */
    public void blacklist(String jti, Date expiration) {
        if (jti == null || expiration == null) {
            return;
        }
        long remain = (expiration.getTime() - System.currentTimeMillis()) / 1000;
        if (remain > 0) {
            redis.opsForValue().set(BLACKLIST_PREFIX + jti, "1", Duration.ofSeconds(remain));
        }
    }
}
