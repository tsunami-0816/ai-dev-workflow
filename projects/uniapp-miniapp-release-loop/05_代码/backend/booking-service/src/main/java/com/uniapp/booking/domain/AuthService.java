package com.uniapp.booking.domain;

import com.uniapp.booking.common.BizException;
import com.uniapp.booking.common.ErrorCode;
import com.uniapp.booking.common.PasswordHasher;
import com.uniapp.booking.config.BookingProperties;
import com.uniapp.booking.infra.JwtService;
import com.uniapp.booking.web.dto.LoginRequest;
import com.uniapp.booking.web.dto.LoginResponse;
import io.jsonwebtoken.Claims;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.time.Duration;

/**
 * 登录/登出（D-08 / T-205）。
 * 两种形态：H5 account+password（种子账号）、小程序 openid（首见建号）。
 */
@Service
public class AuthService {

    private final UserRepository users;
    private final JwtService jwtService;
    private final BookingProperties props;

    public AuthService(UserRepository users, JwtService jwtService, BookingProperties props) {
        this.users = users;
        this.jwtService = jwtService;
        this.props = props;
    }

    /**
     * 登录并签发 JWT。
     *
     * @param req           入参：account+password 或 openid（至少一个）
     * @param verifiedCloud 入参：本请求是否通过云函数 HMAC 验签（SignatureFilter 写入）
     * @return token/expiresIn/userId/nickname（出参）
     * @throws BizException 40101 凭证错误；40102 openid 登录非云函数来源；40001 两种形态都未提供
     */
    public LoginResponse login(LoginRequest req, boolean verifiedCloud) {
        if (StringUtils.hasText(req.getAccount())) {
            return loginByAccount(req.getAccount().trim(), req.getPassword());
        }
        if (StringUtils.hasText(req.getOpenid())) {
            // Q-004：openid 只能由小程序云函数（已验签）带进来，H5 直连不得凭 openid 建号
            if (!verifiedCloud) {
                throw new BizException(ErrorCode.BAD_SIGNATURE, "openid 登录仅允许经小程序云函数发起");
            }
            return loginByOpenid(req.getOpenid().trim(), req.getNickname());
        }
        throw new BizException(ErrorCode.PARAM_INVALID, "account 或 openid 至少填一个");
    }

    private LoginResponse loginByAccount(String account, String password) {
        UserRepository.UserRow row = users.findByAccount(account)
                .orElseThrow(() -> new BizException(ErrorCode.UNAUTHORIZED, "账号或密码不正确"));
        if (!PasswordHasher.matches(password, row.getPasswordHash())) {
            throw new BizException(ErrorCode.UNAUTHORIZED, "账号或密码不正确");
        }
        return issue(row.getId(), row.getNickname());
    }

    private LoginResponse loginByOpenid(String openid, String nickname) {
        UserRepository.UserRow row = users.findByOpenid(openid).orElseGet(() -> {
            long id = users.insertOpenidUser(openid, StringUtils.hasText(nickname) ? nickname : "微信用户");
            return new UserRepository.UserRow(id, null, null, openid,
                    StringUtils.hasText(nickname) ? nickname : "微信用户");
        });
        return issue(row.getId(), row.getNickname());
    }

    private LoginResponse issue(long userId, String nickname) {
        String token = jwtService.issue(userId);
        return new LoginResponse(token, Duration.ofHours(props.getJwt().getTtlHours()).toSeconds(), userId, nickname);
    }

    /**
     * 登出：把当前 token 的 jti 写入黑名单，TTL 取剩余有效期。
     *
     * @param token 入参：Bearer 后面的原始 token
     * @throws BizException 40103 token 已过期/非法
     */
    public void logout(String token) {
        try {
            Claims claims = jwtService.parse(token);
            jwtService.blacklist(claims.getId(), claims.getExpiration());
        } catch (Exception ex) {
            throw new BizException(ErrorCode.TOKEN_EXPIRED);
        }
    }
}
