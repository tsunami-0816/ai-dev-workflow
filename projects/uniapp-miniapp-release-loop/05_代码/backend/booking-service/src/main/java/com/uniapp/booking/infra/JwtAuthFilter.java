package com.uniapp.booking.infra;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.uniapp.booking.common.ErrorCode;
import com.uniapp.booking.common.Result;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.ExpiredJwtException;
import io.jsonwebtoken.JwtException;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.core.annotation.Order;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.nio.charset.StandardCharsets;

/**
 * JWT 鉴权 Filter（D-24 / T-203）。
 * 保护 /api/bookings* 与 /api/auth/logout；其余接口按设计匿名可读。
 * 无 token → 40101；过期 → 40103；登出后旧 token → 40103。
 */
@Component
@Order(2)
public class JwtAuthFilter extends OncePerRequestFilter {

    public static final String ATTR_USER_ID = "userId";
    public static final String ATTR_JTI = "jti";

    private final JwtService jwtService;
    private final ObjectMapper objectMapper;

    public JwtAuthFilter(JwtService jwtService, ObjectMapper objectMapper) {
        this.jwtService = jwtService;
        this.objectMapper = objectMapper;
    }

    private boolean isProtected(String path) {
        return path.startsWith("/api/bookings") || path.equals("/api/auth/logout");
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        // CORS 预检不带 Authorization，必须在鉴权之前放行，否则浏览器拿不到 CORS 头
        if ("OPTIONS".equalsIgnoreCase(request.getMethod())) {
            return true;
        }
        return !isProtected(request.getRequestURI());
    }

    /**
     * 校验 Authorization: Bearer <JWT>。
     *
     * @param request  入参：请求头
     * @param response 出参：40101/40103 统一包装
     * @throws ServletException 过滤器链异常
     * @throws IOException      写响应失败
     */
    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                    FilterChain chain) throws ServletException, IOException {
        String header = request.getHeader("Authorization");
        if (header == null || !header.startsWith("Bearer ")) {
            writeError(response, ErrorCode.UNAUTHORIZED);
            return;
        }
        String token = header.substring(7).trim();
        try {
            Claims claims = jwtService.parse(token);
            if (jwtService.isBlacklisted(claims.getId())) {
                writeError(response, ErrorCode.TOKEN_EXPIRED);
                return;
            }
            request.setAttribute(ATTR_USER_ID, Long.valueOf(claims.getSubject()));
            request.setAttribute(ATTR_JTI, claims.getId());
            chain.doFilter(request, response);
        } catch (ExpiredJwtException ex) {
            writeError(response, ErrorCode.TOKEN_EXPIRED);
        } catch (JwtException | IllegalArgumentException ex) {
            writeError(response, ErrorCode.UNAUTHORIZED);
        }
    }

    private void writeError(HttpServletResponse response, ErrorCode code) throws IOException {
        response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
        response.setCharacterEncoding(StandardCharsets.UTF_8.name());
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.getWriter().write(objectMapper.writeValueAsString(Result.fail(code)));
    }
}
