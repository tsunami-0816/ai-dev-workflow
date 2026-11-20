package com.uniapp.booking.web;

import com.uniapp.booking.common.Result;
import com.uniapp.booking.domain.AuthService;
import com.uniapp.booking.infra.SignatureFilter;
import com.uniapp.booking.web.dto.LoginRequest;
import com.uniapp.booking.web.dto.LoginResponse;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 登录/登出（D-08）。登录匿名可调；登出需带有效 JWT（由 JwtAuthFilter 守卫）。
 */
@RestController
@RequestMapping("/api/auth")
public class AuthController {

    private final AuthService authService;

    public AuthController(AuthService authService) {
        this.authService = authService;
    }

    /**
     * 登录。
     *
     * @param req  入参：{account?,password?,openid?,nickname?}
     * @param http 入参：读取 SignatureFilter 写入的「云函数已验签」标记
     * @return {code:0,data:{token,expiresIn,userId,nickname}}；失败 40101/40102/40001
     */
    @PostMapping("/login")
    public Result<LoginResponse> login(@Valid @RequestBody LoginRequest req, HttpServletRequest http) {
        boolean verifiedCloud = Boolean.TRUE.equals(http.getAttribute(SignatureFilter.ATTR_VERIFIED_CLOUD));
        return Result.ok(authService.login(req, verifiedCloud));
    }

    /**
     * 登出：拉黑当前 jti，旧 token 立即失效（40103）。
     *
     * @param authorization 入参：Authorization: Bearer &lt;JWT&gt;
     * @return {code:0,data:null}
     */
    @PostMapping("/logout")
    @SecurityRequirement(name = "bearerAuth")
    public Result<Void> logout(@RequestHeader("Authorization") String authorization) {
        authService.logout(authorization.replaceFirst("Bearer ", "").trim());
        return Result.ok(null);
    }
}
