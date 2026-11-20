package com.uniapp.booking.web.dto;

/**
 * 登录出参（架构 §6.3 #1）：token + 有效期 + 用户身份。
 * expiresIn 单位秒（2h = 7200）。
 */
public class LoginResponse {

    private final String token;
    private final long expiresIn;
    private final long userId;
    private final String nickname;

    public LoginResponse(String token, long expiresIn, long userId, String nickname) {
        this.token = token;
        this.expiresIn = expiresIn;
        this.userId = userId;
        this.nickname = nickname;
    }

    public String getToken() {
        return token;
    }

    public long getExpiresIn() {
        return expiresIn;
    }

    public long getUserId() {
        return userId;
    }

    public String getNickname() {
        return nickname;
    }
}
