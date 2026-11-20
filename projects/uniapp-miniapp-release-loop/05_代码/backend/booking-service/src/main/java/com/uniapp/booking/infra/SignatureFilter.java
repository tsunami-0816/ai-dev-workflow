package com.uniapp.booking.infra;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.uniapp.booking.common.ErrorCode;
import com.uniapp.booking.common.Result;
import com.uniapp.booking.config.BookingProperties;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.core.annotation.Order;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Duration;
import java.util.HexFormat;

/**
 * HMAC + 防重放 Filter（D-25 / T-204 / R-08）。
 *
 * 规则（只作用于 /api/**）：
 * 1. 云函数通道（X-Client: cloud）必须带 X-Sign / X-Timestamp / X-Nonce；
 * 2. H5 直连未带任何签名头时放行（浏览器端不能持有 APP_SECRET）；
 * 3. 只要出现任一签名头，就必须三者齐全且全部校验通过，否则 40102；
 * 4. X-Sign = hex(HMAC-SHA256(rawBody + "|" + X-Timestamp, APP_SECRET))，小写；
 * 5. X-Timestamp 与服务器时间差 ≤ 60s；X-Nonce 8–64 位，Redis SETNX 120s 去重；
 * 6. 验签通过 → request 属性 {@link #ATTR_VERIFIED_CLOUD}=true；H5 无签名直连 = false。
 *    openid 登录据此拒绝非云函数来源（Q-004），避免任意 openid 建号/冒充。
 */
@Component
@Order(1)
public class SignatureFilter extends OncePerRequestFilter {

    /** 验签通过时写进 request 属性；业务层用它区分「云函数通道」与「H5 直连」（Q-004）。 */
    public static final String ATTR_VERIFIED_CLOUD = "ub.verifiedCloud";

    private static final String NONCE_PREFIX = "ub:nonce:";

    private final BookingProperties props;
    private final StringRedisTemplate redis;
    private final ObjectMapper objectMapper;

    public SignatureFilter(BookingProperties props, StringRedisTemplate redis, ObjectMapper objectMapper) {
        this.props = props;
        this.redis = redis;
        this.objectMapper = objectMapper;
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        return !request.getRequestURI().startsWith("/api/");
    }

    /**
     * 校验签名与 nonce。
     *
     * @param request  入参：headers + body
     * @param response 出参：40102 统一包装
     * @throws ServletException 过滤器链异常
     * @throws IOException      读 body/写响应失败
     */
    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                    FilterChain chain) throws ServletException, IOException {
        String sign = request.getHeader("X-Sign");
        String ts = request.getHeader("X-Timestamp");
        String nonce = request.getHeader("X-Nonce");
        boolean cloud = "cloud".equalsIgnoreCase(request.getHeader("X-Client"));
        boolean anySign = sign != null || ts != null || nonce != null;

        if (!cloud && !anySign) {
            request.setAttribute(ATTR_VERIFIED_CLOUD, Boolean.FALSE);
            chain.doFilter(request, response);
            return;
        }
        if (sign == null || ts == null || nonce == null) {
            writeError(response, ErrorCode.BAD_SIGNATURE);
            return;
        }
        if (!validTimestamp(ts) || !validNonce(nonce)) {
            writeError(response, ErrorCode.BAD_SIGNATURE);
            return;
        }

        byte[] body = request.getInputStream().readAllBytes();
        String expected = hmacHex(body, ts);
        if (!MessageDigest.isEqual(expected.getBytes(StandardCharsets.UTF_8),
                sign.toLowerCase().getBytes(StandardCharsets.UTF_8))) {
            writeError(response, ErrorCode.BAD_SIGNATURE);
            return;
        }
        Boolean firstUse = redis.opsForValue()
                .setIfAbsent(NONCE_PREFIX + nonce, "1", Duration.ofSeconds(120));
        if (!Boolean.TRUE.equals(firstUse)) {
            writeError(response, ErrorCode.BAD_SIGNATURE);
            return;
        }
        request.setAttribute(ATTR_VERIFIED_CLOUD, Boolean.TRUE);
        chain.doFilter(new CachedBodyRequest(request, body), response);
    }

    private boolean validTimestamp(String ts) {
        try {
            long t = Long.parseLong(ts);
            long diff = Math.abs(System.currentTimeMillis() / 1000 - t);
            return diff <= props.getHmac().getWindowSeconds();
        } catch (NumberFormatException ex) {
            return false;
        }
    }

    private boolean validNonce(String nonce) {
        return nonce.matches("[A-Za-z0-9_-]{8,64}");
    }

    private String hmacHex(byte[] body, String ts) {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(props.getHmac().getSecret().getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
            byte[] payload = (new String(body, StandardCharsets.UTF_8) + "|" + ts).getBytes(StandardCharsets.UTF_8);
            return HexFormat.of().formatHex(mac.doFinal(payload));
        } catch (Exception ex) {
            throw new IllegalStateException("HMAC 计算失败", ex);
        }
    }

    private void writeError(HttpServletResponse response, ErrorCode code) throws IOException {
        response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
        response.setCharacterEncoding(StandardCharsets.UTF_8.name());
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.getWriter().write(objectMapper.writeValueAsString(Result.fail(code)));
    }
}
