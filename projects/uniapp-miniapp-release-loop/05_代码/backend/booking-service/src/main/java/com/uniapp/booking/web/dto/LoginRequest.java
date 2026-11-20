package com.uniapp.booking.web.dto;

import jakarta.validation.constraints.Size;

/**
 * 登录入参（架构 §6.3 #1）：openid（小程序）与 account+password（H5）二选一。
 */
public class LoginRequest {

    @Size(max = 32, message = "账号过长")
    private String account;

    @Size(max = 64, message = "口令过长")
    private String password;

    @Size(max = 64, message = "openid 过长")
    private String openid;

    @Size(max = 64, message = "昵称过长")
    private String nickname;

    public String getAccount() {
        return account;
    }

    public void setAccount(String account) {
        this.account = account;
    }

    public String getPassword() {
        return password;
    }

    public void setPassword(String password) {
        this.password = password;
    }

    public String getOpenid() {
        return openid;
    }

    public void setOpenid(String openid) {
        this.openid = openid;
    }

    public String getNickname() {
        return nickname;
    }

    public void setNickname(String nickname) {
        this.nickname = nickname;
    }
}
