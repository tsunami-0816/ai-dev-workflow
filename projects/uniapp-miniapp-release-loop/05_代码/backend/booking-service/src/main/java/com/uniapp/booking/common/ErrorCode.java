package com.uniapp.booking.common;

/**
 * 错误码表（D-23）。4xxxx = 客户端问题；5xxxx = 服务端问题。
 * 50000 专用于「未知异常兜底」（T-202 口径），50001/50002 为显式服务错误（架构 §6.2）。
 */
public enum ErrorCode {
    PARAM_INVALID(40001, "参数不合法"),
    DATE_OUT_OF_RANGE(40002, "预约日期超出可预约范围"),
    UNAUTHORIZED(40101, "未登录或登录态无效"),
    BAD_SIGNATURE(40102, "签名校验失败"),
    TOKEN_EXPIRED(40103, "登录已过期，请重新登录"),
    FORBIDDEN(40301, "无权访问该数据"),
    NOT_FOUND(40400, "接口不存在"),
    PACKAGE_NOT_FOUND(40401, "套餐不存在"),
    RATE_LIMITED(42901, "请勿重复提交"),
    SERVER_ERROR(50000, "服务器开小差了，请稍后重试"),
    SERVICE_ERROR(50001, "服务开小差了，请稍后重试"),
    UPSTREAM_TIMEOUT(50002, "网络不稳定，请重试");

    private final int code;
    private final String msg;

    ErrorCode(int code, String msg) {
        this.code = code;
        this.msg = msg;
    }

    public int getCode() {
        return code;
    }

    public String getMsg() {
        return msg;
    }
}
