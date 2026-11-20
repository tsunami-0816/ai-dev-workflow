package com.uniapp.booking.infra;

import com.uniapp.booking.common.BizException;
import com.uniapp.booking.common.ErrorCode;
import com.uniapp.booking.common.Result;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.validation.FieldError;
import org.springframework.web.HttpMediaTypeNotSupportedException;
import org.springframework.web.HttpRequestMethodNotSupportedException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.servlet.resource.NoResourceFoundException;

/**
 * 全局异常处理（D-23 / T-202）：所有失败都转 {code,msg,data:null}，不回显堆栈。
 */
@RestControllerAdvice
public class GlobalExceptionHandler {
    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    @ExceptionHandler(BizException.class)
    public ResponseEntity<Result<Void>> handleBiz(BizException ex) {
        ErrorCode code = ex.getErrorCode();
        HttpStatus status = switch (code) {
            case UNAUTHORIZED, BAD_SIGNATURE, TOKEN_EXPIRED -> HttpStatus.UNAUTHORIZED;
            case FORBIDDEN -> HttpStatus.FORBIDDEN;
            case PACKAGE_NOT_FOUND -> HttpStatus.NOT_FOUND;
            case RATE_LIMITED -> HttpStatus.TOO_MANY_REQUESTS;
            case UPSTREAM_TIMEOUT -> HttpStatus.GATEWAY_TIMEOUT;
            case SERVICE_ERROR, SERVER_ERROR -> HttpStatus.INTERNAL_SERVER_ERROR;
            default -> HttpStatus.BAD_REQUEST;
        };
        return ResponseEntity.status(status).body(Result.fail(code.getCode(), ex.getMessage()));
    }

    /** 字段级校验失败：返回第一条字段错误，前端据此做字段红字。 */
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<Result<Void>> handleValid(MethodArgumentNotValidException ex) {
        FieldError first = ex.getBindingResult().getFieldErrors().stream().findFirst().orElse(null);
        String msg = first == null ? ErrorCode.PARAM_INVALID.getMsg()
                : first.getField() + " " + first.getDefaultMessage();
        return ResponseEntity.badRequest().body(Result.fail(ErrorCode.PARAM_INVALID.getCode(), msg));
    }

    /** 缺少 query 参数 / 参数类型不对。 */
    @ExceptionHandler({MissingServletRequestParameterException.class,
            org.springframework.web.method.annotation.MethodArgumentTypeMismatchException.class})
    public ResponseEntity<Result<Void>> handleParam(Exception ex) {
        return ResponseEntity.badRequest()
                .body(Result.fail(ErrorCode.PARAM_INVALID.getCode(), "请求参数不合法"));
    }

    /** 请求体不是合法 JSON。 */
    @ExceptionHandler(HttpMessageNotReadableException.class)
    public ResponseEntity<Result<Void>> handleBody(Exception ex) {
        return ResponseEntity.badRequest()
                .body(Result.fail(ErrorCode.PARAM_INVALID.getCode(), "请求体不是合法 JSON"));
    }

    @ExceptionHandler({HttpRequestMethodNotSupportedException.class})
    public ResponseEntity<Result<Void>> handleMethod(Exception ex) {
        return ResponseEntity.status(HttpStatus.METHOD_NOT_ALLOWED)
                .body(Result.fail(ErrorCode.PARAM_INVALID.getCode(), "请求方法不支持"));
    }

    @ExceptionHandler({HttpMediaTypeNotSupportedException.class})
    public ResponseEntity<Result<Void>> handleMediaType(Exception ex) {
        return ResponseEntity.badRequest()
                .body(Result.fail(ErrorCode.PARAM_INVALID.getCode(), "Content-Type 需为 application/json"));
    }

    /** 未注册路径：404 + 40400（P2 收口，避免未知路径落到 50000 兜底）。 */
    @ExceptionHandler(NoResourceFoundException.class)
    public ResponseEntity<Result<Void>> handleNoResource(NoResourceFoundException ex) {
        return ResponseEntity.status(HttpStatus.NOT_FOUND).body(Result.fail(ErrorCode.NOT_FOUND));
    }

    /** 未知异常兜底：code=50000，不回显堆栈（T-202 口径）。 */
    @ExceptionHandler(Exception.class)
    public ResponseEntity<Result<Void>> handleUnknown(Exception ex) {
        log.error("unhandled exception", ex);
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(Result.fail(ErrorCode.SERVER_ERROR));
    }
}
